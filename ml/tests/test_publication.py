"""Seeded fixtures only: exercise the P2 producer with P1's actual readers and HTTP routes."""

from dataclasses import replace
from datetime import timedelta

import httpx
import numpy as np
import pandas as pd
import pytest

from hirup_ml import cli, dataset, insights, predict, publication, raster, train
from hirup_ml.config import load_config
from hirup_pipelines import paths, store
from hirup_pipelines.settings import data_dir
from services.api.main import create_app
from services.api.runtime import Runtime
from services.exposure.advice_aq import HistoricalAQProvider
from services.exposure.aq_provider import AQUnavailableError, CogAQProvider
from services.exposure.aq_service import AQService
from services.exposure.daily_summary import DailySummaryService
from services.exposure.forecast import ForecastService
from services.exposure.geometry import Point
from services.exposure.kelurahan import KelurahanArtifact, KelurahanService
from services.exposure.publication import Publication


@pytest.fixture(autouse=True)
def no_tile_work(monkeypatch):
    monkeypatch.setitem(load_config()["tiles"]["ispu"], "verified_by", None)


def test_observed_history_has_hand_computed_quantiles_and_excludes_today():
    # Two station means, 20 and 50, on consecutive Thursdays at 08:00 WIB.
    ts = pd.to_datetime(
        ["2026-10-01T01:00Z"] * 2 + ["2026-10-08T01:00Z"] * 2 + ["2026-10-15T01:00Z"], utc=True
    )
    frame = pd.DataFrame(
        {
            "station_id": ["test-a", "test-b", "test-a", "test-b", "test-a"],
            "ts": ts,
            "value_cal": [10.0, 30.0, 40.0, 60.0, 999.0],
            "qc_flag": "ok",
        }
    )
    store.write_daily(frame, paths.observations(), ["station_id", "ts"])
    generated = pd.Timestamp("2026-10-15T08:15+07:00").to_pydatetime()
    path = publication.history(data_dir() / "test-run", generated)
    assert path is not None
    historical = HistoricalAQProvider.load(path)
    assert historical.artifact.period_end.isoformat() == "2026-10-08"
    assert historical.artifact.hours["3:08"].model_dump() == pytest.approx(
        {"p10": 23.0, "p50": 35.0, "p90": 47.0}
    )


def test_same_hour_republication_is_immutable_and_failed_publish_keeps_pointer(toy, monkeypatch):
    at = toy["last_hour"].to_pydatetime()
    predict.run(at, now=at + timedelta(minutes=5))
    root = data_dir()
    first = Publication.load(root, root / "aq_publication.json")
    reader = CogAQProvider(root, first.manifests, bounds=Runtime.unavailable().aq.bounds)
    point = Point(106.82, -6.21)
    before = reader.sample((point,), at).p50.copy()
    try:
        predict.run(at, now=at + timedelta(minutes=6))
        second = Publication.load(root, root / "aq_publication.json")
        assert set(first.manifests).isdisjoint(second.manifests)
        assert all(path.is_file() for path in first.manifests)
        assert np.array_equal(reader.sample((point,), at).p50, before)
        saved = (root / "aq_publication.json").read_bytes()

        def fail(*args, **kwargs):
            raise OSError("test-only publication interruption")

        monkeypatch.setattr(insights, "write_daily", fail)
        with pytest.raises(OSError, match="test-only"):
            predict.run(at, now=at + timedelta(minutes=7))
        assert (root / "aq_publication.json").read_bytes() == saved
    finally:
        reader.close()


def test_daily_adapter_requires_every_region_hour_and_preserves_provenance(toy):
    at = toy["last_hour"].to_pydatetime()
    day = at.astimezone(raster.LOCAL).replace(hour=0, minute=0) - timedelta(days=1)
    for hour in range(24):
        valid = day + timedelta(hours=hour)
        values = np.full(toy["grid"].shape, 10.0 + hour)
        insights.record_hour(
            toy["cells"],
            values,
            valid,
            "synthetic",
            manifest={
                "generated_at": valid.isoformat(),
                "kind": "nowcast",
                "model_version": "seeded-test",
            },
        )
    path = insights.write_daily(data_dir() / "test-run", at)
    assert path is not None
    artifact = KelurahanArtifact.model_validate_json(path.read_text())
    assert len(artifact.days) == 1
    assert artifact.days[0].data_quality == "synthetic"
    assert all(item.mean_pm25 == 21.5 for item in artifact.days[0].items)
    assert all(len(item.hours_covered) == 24 for item in artifact.days[0].items)
    frame = store.read_parquet(insights.hourly_path())
    store.write_parquet(frame.iloc[1:], insights.hourly_path())
    assert insights.write_daily(data_dir() / "incomplete", at) is None


@pytest.mark.asyncio
async def test_model_publication_reaches_http_with_explicit_synthetic_labels(toy, monkeypatch):
    train.train(dataset.load(), n_trials=0)
    at = toy["last_hour"].to_pydatetime().astimezone(raster.LOCAL).replace(hour=0)
    now = at + timedelta(minutes=15)
    original = raster.write_set

    def labelled(raster_set, *args, **kwargs):
        return original(replace(raster_set, data_quality="synthetic"), *args, **kwargs)

    monkeypatch.setattr(raster, "write_set", labelled)
    # Complete prior day, with hand-computed mean 21.5; no real model metric is claimed.
    previous = at - timedelta(days=1)
    for hour in range(24):
        valid = previous + timedelta(hours=hour)
        insights.record_hour(
            toy["cells"],
            np.full(toy["grid"].shape, 10.0 + hour),
            valid,
            "synthetic",
            manifest={
                "generated_at": valid.isoformat(),
                "kind": "nowcast",
                "model_version": "seeded-test",
            },
        )
    predict.run(at, now=now)
    root = data_dir()
    pub = Publication.load(root, root / "aq_publication.json")
    assert pub.kelurahan is not None
    assert pub.history is not None
    assert not pub.tiles_available
    async with httpx.AsyncClient() as upstream:
        # The production constructor must refuse the labelled toy rasters.
        production = Runtime.from_env(upstream, cli.api_env())
        assert production.cog is not None
        with pytest.raises(AQUnavailableError):
            production.cog.manifest(at)
        production.cog.close()
    cog = CogAQProvider(
        root, pub.manifests, bounds=Runtime.unavailable().aq.bounds, allow_synthetic=True
    )
    try:
        runtime = Runtime(AQService(cog, cog.bounds), params=production.params, cog=cog)
        runtime.forecast = ForecastService(cog.bounds, cog, allow_synthetic=True, now=lambda: now)
        runtime.daily_summary = DailySummaryService(
            cog.bounds, runtime.params, cog, allow_synthetic=True, now=lambda: now
        )
        runtime.kelurahan = KelurahanService(pub.kelurahan, allow_synthetic=True, now=lambda: now)
        runtime.kelurahan.reload()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(runtime)), base_url="http://test"
        ) as client:
            point = {"lat": -6.21, "lon": 106.82}
            requests = [
                ("/v1/aq/point", {**point, "ts": at.isoformat()}),
                ("/v1/aq/forecast", {**point, "hours": 24}),
                ("/v1/aq/daily-summary", {**point, "date": at.date().isoformat()}),
                (
                    "/v1/insights/kelurahan",
                    {"from": previous.date().isoformat(), "to": previous.date().isoformat()},
                ),
            ]
            for path, query in requests:
                response = await client.get(path, params=query)
                assert response.status_code == 200, response.text
                assert response.json()["data_quality"] == "synthetic"
            items = response.json()["items"]
            assert all(item["mean_pm25"] == 21.5 for item in items)
            assert all(item["inequality_index"] is None for item in items)
    finally:
        cog.close()
