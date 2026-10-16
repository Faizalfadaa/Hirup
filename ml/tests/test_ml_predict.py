import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio

from hirup_ml import cli, dataset, insights, monitor, predict, raster, registry, train
from hirup_ml.config import FALLBACK_VERSION, manifests_dir, tiles_dir
from hirup_pipelines import paths, store
from hirup_pipelines.grid import map_grid
from hirup_pipelines.settings import data_dir, pilot_bbox
from services.exposure.aq_provider import CogAQProvider
from services.exposure.geometry import BoundingBox, Point


def api_provider():
    """P1's reader, configured exactly as `hirup-ml env` tells the API to be."""
    env = cli.api_env()
    box = pilot_bbox()
    return CogAQProvider(
        Path(env["HIRUP_DATA_DIR"]),
        [Path(p) for p in json.loads(env["HIRUP_AQ_MANIFESTS"])],
        bounds=BoundingBox(box.min_lat, box.max_lat, box.min_lon, box.max_lon),
    )


def test_postprocess_orders_and_clips_quantiles():
    rng = np.random.default_rng(1)
    shape = (20, 30)
    out = raster.postprocess(
        rng.uniform(-50, 700, shape), rng.uniform(-50, 700, shape), rng.uniform(-50, 700, shape)
    )
    assert (out["p10"] <= out["p50"]).all()
    assert (out["p50"] <= out["p90"]).all()
    assert out["p10"].min() >= 0
    assert out["p90"].max() <= 500


def test_write_cog_rejects_gaps(tmp_path):
    grid = map_grid()
    bad = np.ones(grid.shape)
    bad[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        raster.write_cog(tmp_path / "x.tif", bad, grid)


def test_fallback_run_without_stations_is_labelled_approximated(toy):
    for path in paths.observations().glob("date=*/part.parquet"):
        path.unlink()
    summary = predict.run(toy["last_hour"].to_pydatetime())
    assert summary["data_quality"] == "approximated"
    assert summary["model_version"] == FALLBACK_VERSION
    assert summary["hours_published"] == 25
    assert summary["stations_reporting"] == 0
    manifest = store.read_json(manifests_dir() / "nowcast.json")
    assert manifest["metrics"]["interval_available"] == 0.0
    provider = api_provider()
    try:
        sample = provider.sample([Point(106.8227, -6.2088)], toy["last_hour"].to_pydatetime())
    finally:
        provider.close()
    assert sample.data_quality == "approximated"
    assert sample.p10[0] == sample.p50[0] == sample.p90[0]


def test_model_run_publishes_everything_the_api_reads(toy):
    entry = train.train(dataset.load(), n_trials=0)
    assert entry["is_active"]
    at = toy["last_hour"].to_pydatetime()
    summary = predict.run(at)
    assert summary["data_quality"] == "real"
    assert summary["model_version"] == entry["model_version"]
    assert summary["stations_reporting"] == 8

    # Every slot exists and is a valid contract manifest; hours T .. T+24 are all covered.
    hours = set()
    for name in predict.slot_names():
        manifest = store.read_json(manifests_dir() / name)
        raster.validate_manifest(manifest)
        hours.add(pd.Timestamp(manifest["valid_hour"]))
        for relative in manifest["files"].values():
            with rasterio.open(data_dir() / relative) as src:
                assert src.crs.to_epsg() == 32748
                assert src.transform.a == 100
                assert src.transform.e == -100
                assert src.nodata is None
    assert hours == {toy["last_hour"] + pd.Timedelta(hours=h) for h in range(25)}
    assert store.read_json(manifests_dir() / "forecast_plus_24.json")["kind"] == "forecast"

    # P1's provider accepts the set and returns ordered quantiles for now and for +24 h.
    provider = api_provider()
    try:
        box = pilot_bbox()
        corners = [
            Point(box.min_lon, box.min_lat),
            Point(box.max_lon, box.max_lat),
            Point(106.8227, -6.2088),
        ]
        for lead in (0, 24):
            sample = provider.sample(corners, at + timedelta(hours=lead))
            assert sample.data_quality == "real"
            assert sample.model_version == entry["model_version"]
            assert (sample.p10 <= sample.p50).all()
            assert (sample.p50 <= sample.p90).all()
        east = provider.sample([Point(106.845, -6.2)], at).p50[0]
        west = provider.sample([Point(106.765, -6.2)], at).p50[0]
        assert east > west  # the toy road gradient survives into the raster
        assert provider.raster_median(at) > 0
    finally:
        provider.close()

    # Tiles for the nowcast hour and the next one, at the path the API serves them from.
    local = raster.stamp(at)
    tiles = list((tiles_dir() / local).rglob("*.png"))
    assert tiles
    assert all(t.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for t in tiles[:3])
    assert (tiles_dir() / raster.stamp(at + timedelta(hours=1))).is_dir()

    # Fallback inputs and city medians in the shape services/api/runtime.py parses.
    inputs = store.read_json(data_dir() / "aq_inputs.json")
    assert inputs["data_quality"] == "approximated"
    assert inputs["source"]
    assert len(inputs["stations"]) == 8
    assert set(inputs["stations"][0]) == {"point", "valid_hour", "pm25"}
    assert len(inputs["cams"]) == 25
    medians = store.read_json(data_dir() / "city_medians.json")
    assert len(medians) == 25
    assert all(item["source"] and item["value"] > 0 for item in medians.values())

    # Insight Kota payload.
    payload = store.read_json(data_dir() / "insights" / "kelurahan_latest.json")
    assert payload is None or payload["items"] is not None  # window is relative to today
    day = toy["last_hour"].tz_convert("Asia/Jakarta").date()
    city = insights.summarise(day, day)
    assert city["boundaries_version"] == "kelurahan-toy"
    assert city["data_quality"] == "real"
    assert [item["priority_rank"] for item in city["items"]] == [1, 2]
    by_name = {item["name"]: item for item in city["items"]}
    assert by_name["Timur"]["mean_pm25"] > by_name["Barat"]["mean_pm25"]
    assert by_name["Timur"]["priority_rank"] == 1
    assert all(0 <= item["inequality_index"] <= 1 for item in city["items"])
    assert insights.summarise(day, day, hours=[3])["hours_in_window"] == 0


def test_second_run_rotates_recent_nowcasts_and_keeps_every_slot_valid(toy):
    first = toy["last_hour"].to_pydatetime() - timedelta(hours=1)
    predict.run(first)
    predict.run(toy["last_hour"].to_pydatetime())
    previous = store.read_json(manifests_dir() / "nowcast_minus_01.json")
    assert pd.Timestamp(previous["valid_hour"]) == pd.Timestamp(first)
    assert previous["kind"] == "nowcast"
    provider = api_provider()
    try:
        assert provider.manifest(first).kind == "nowcast"
    finally:
        provider.close()


def test_drift_alarm_switches_to_the_fallback(toy):
    entry = train.train(dataset.load(), n_trials=0)
    at = toy["last_hour"].to_pydatetime()
    model = registry.load_active()
    assert monitor.status(model, at)["alarm"] is False  # nothing recorded yet
    # Record nowcasts that are far off for the last day, as if the model had drifted.
    hours = pd.date_range(end=toy["last_hour"], periods=24, freq="h")
    wrong = pd.DataFrame(
        {
            "station_id": np.repeat(toy["stations"]["station_id"].to_numpy(), 24),
            "ts": np.tile(hours, 8),
            "p50": 400.0,
            "model_version": entry["model_version"],
        }
    )
    from hirup_ml.config import monitor_path

    store.write_parquet(wrong, monitor_path())
    state = monitor.status(model, at + timedelta(hours=1))
    assert state["alarm"] is True
    assert state["rolling_rmse_24h"] > state["threshold"]


def test_tile_geometry_and_colours():
    xs, ys = raster.tile_range(12)
    assert len(xs) * len(ys) <= 9
    # Flat colour per ISPU category; an upper bound still belongs to its own category.
    colours = raster.colourise(np.array([0.0, 15.5, 15.6, 55.4, 55.5, 150.5, 900.0]))
    assert colours.tolist() == [
        [0, 176, 80],
        [0, 176, 80],
        [0, 112, 192],
        [0, 112, 192],
        [255, 192, 0],
        [255, 0, 0],
        [0, 0, 0],
    ]


def test_env_lists_every_manifest_slot():
    env = cli.api_env()
    slots = json.loads(env["HIRUP_AQ_MANIFESTS"])
    assert len(slots) == 3 + 1 + 24
    assert slots[3].endswith("manifests/nowcast.json")


def test_env_command_exports_every_variable(capsys):
    # `eval "$(hirup-ml env)"` must reach child processes such as uvicorn.
    cli.main(["env"])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(cli.api_env())
    assert all(line.startswith("export HIRUP_") for line in lines)
