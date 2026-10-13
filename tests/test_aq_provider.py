import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from services.exposure.aq_provider import (
    AQUnavailableError,
    CogAQProvider,
    FallbackAQProvider,
    IdwAQProvider,
    OutOfServiceAreaError,
    Pm25Samples,
    StationSample,
    SyntheticAQProvider,
)
from services.exposure.engine import Quantiles
from services.exposure.geometry import BoundingBox, Point, unproject

TS = datetime.fromisoformat("2026-10-14T08:00:00+07:00")
BOUNDS = BoundingBox(-6.3, -6.13, 106.76, 106.85)


def raster_set(tmp_path: Path, *, nodata: bool = False, resolution: int = 100) -> Path:
    (tmp_path / "rasters").mkdir(exist_ok=True)
    files = {}
    for name, offset in (("p10", -5), ("p50", 0), ("p90", 5)):
        filename = f"rasters/pm25_2026101408_{name}.tif"
        files[name] = filename
        pixels = np.array([[10, 20], [30, 40]], dtype="float32") + offset
        if nodata:
            pixels[0, 0] = -9999
        with rasterio.open(
            tmp_path / filename,
            "w",
            driver="COG",
            height=2,
            width=2,
            count=1,
            dtype="float32",
            crs="EPSG:32748",
            transform=from_origin(699000, 9314000, resolution, resolution),
            nodata=-9999,
        ) as writer:
            writer.write(pixels, 1)
    document = {
        "manifest_version": "1.0",
        "model_version": "test-only",
        "generated_at": TS.isoformat(),
        "valid_hour": TS.isoformat(),
        "kind": "nowcast",
        "lead_hours": 0,
        "crs": "EPSG:32748",
        "resolution_m": 100,
        "bbox_wgs84": asdict(BOUNDS),
        "units": "ug/m3",
        "files": files,
        "data_quality": "synthetic",
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document))
    return path


def test_cog_window_quantiles_and_raster_median(tmp_path: Path) -> None:
    manifest = raster_set(tmp_path)
    provider = CogAQProvider(tmp_path, [manifest], bounds=BOUNDS, allow_synthetic=True)
    try:
        values = provider.sample([unproject(699050, 9313950), unproject(699150, 9313850)], TS)
        assert values.p50.tolist() == [10, 40]
        assert values.mean() == Quantiles(20, 25, 30)
        assert values.data_quality == "synthetic"
        assert provider.raster_median(TS) == 25
        with pytest.raises(AQUnavailableError, match="hour"):
            provider.sample([unproject(699050, 9313950)], TS + timedelta(hours=1))
        with pytest.raises(OutOfServiceAreaError):
            provider.sample([Point(0, 0)], TS)
        with pytest.raises(AQUnavailableError, match="grid"):
            provider.sample([Point(106.82, -6.22)], TS)
    finally:
        provider.close()


def test_cog_refuses_synthetic_by_default(tmp_path: Path) -> None:
    with pytest.raises(AQUnavailableError, match="Synthetic"):
        CogAQProvider(tmp_path, [raster_set(tmp_path)], bounds=BOUNDS)


def test_cog_nodata_and_invalid_grid(tmp_path: Path) -> None:
    manifest = raster_set(tmp_path, nodata=True)
    provider = CogAQProvider(tmp_path, [manifest], bounds=BOUNDS, allow_synthetic=True)
    try:
        with pytest.raises(AQUnavailableError, match="no data"):
            provider.sample([unproject(699050, 9313950)], TS)
    finally:
        provider.close()
    manifest = raster_set(tmp_path, resolution=50)
    with pytest.raises(AQUnavailableError, match="grid"):
        CogAQProvider(tmp_path, [manifest], bounds=BOUNDS, allow_synthetic=True)


def test_failed_reload_preserves_previous_hour(tmp_path: Path) -> None:
    manifest = raster_set(tmp_path)
    provider = CogAQProvider(tmp_path, [manifest], bounds=BOUNDS, allow_synthetic=True)
    try:
        invalid = tmp_path / "invalid.json"
        document = json.loads(manifest.read_text())
        document["files"]["p10"] = "../pm25_2026101408_p10.tif"
        invalid.write_text(json.dumps(document))
        with pytest.raises(AQUnavailableError, match="escapes"):
            provider.reload([invalid])
        assert provider.sample([unproject(699050, 9313950)], TS).p50[0] == 10
    finally:
        provider.close()


def test_future_forecast_and_quality_propagation(tmp_path: Path) -> None:
    manifest = raster_set(tmp_path)
    document = json.loads(manifest.read_text())
    document.update(
        kind="forecast",
        lead_hours=1,
        valid_hour=(TS + timedelta(hours=1)).isoformat(),
        data_quality="approximated",
    )
    manifest.write_text(json.dumps(document))
    provider = CogAQProvider(tmp_path, [manifest], bounds=BOUNDS)
    try:
        result = provider.sample([unproject(699050, 9313950)], TS + timedelta(hours=1))
        assert result.p50[0] == 10
        assert result.data_quality == "approximated"
        with pytest.raises(AQUnavailableError, match="hour"):
            provider.sample([unproject(699050, 9313950)], TS)
    finally:
        provider.close()


def test_coincident_stations_and_synthetic_input_guard() -> None:
    point = Point(106.8, -6.2)
    stations = [
        StationSample(point, TS, Quantiles(10, 20, 30)),
        StationSample(point, TS, Quantiles(20, 30, 40)),
    ]
    assert IdwAQProvider(stations, BOUNDS).sample([point], TS).p50[0] == 25
    stations.append(StationSample(point, TS, Quantiles(30, 40, 50), "synthetic"))
    with pytest.raises(ValueError, match="Synthetic"):
        IdwAQProvider(stations, BOUNDS)
    assert (
        IdwAQProvider(stations, BOUNDS, allow_synthetic=True).sample([point], TS).data_quality
        == "synthetic"
    )


def test_idw_hand_computed_and_exact_station() -> None:
    a, b, query = (unproject(x, 9313900) for x in (699000, 699300, 699100))
    provider = IdwAQProvider(
        [
            StationSample(a, TS, Quantiles(5, 10, 15)),
            StationSample(b, TS, Quantiles(25, 30, 35)),
        ],
        BOUNDS,
    )
    # Distances 100 and 200 m: normalized weights 1 and 1/4 -> 14 ug/m3.
    result = provider.sample([query, a], TS)
    assert result.p50 == pytest.approx([14, 10], abs=1e-7)
    assert result.p10 == pytest.approx([9, 5], abs=1e-7)
    assert result.data_quality == "approximated"


def test_stale_stations_use_only_supplied_cams() -> None:
    point = Point(106.8, -6.2)
    provider = IdwAQProvider(
        [StationSample(point, TS - timedelta(hours=1), Quantiles(1, 2, 3))],
        BOUNDS,
        cams={TS: Quantiles(10, 20, 30)},
    )
    assert provider.sample([point], TS).source == "cams"
    assert provider.sample([point], TS).p50[0] == 20
    with pytest.raises(AQUnavailableError, match="current"):
        provider.sample([point], TS + timedelta(hours=1))


def test_fallback_never_hides_area_error_or_uses_synthetic() -> None:
    primary = IdwAQProvider([], BOUNDS)
    fallback = IdwAQProvider([], BOUNDS, cams={TS: Quantiles(10, 20, 30)})
    assert FallbackAQProvider(primary, fallback).sample([Point(106.8, -6.2)], TS).source == "cams"
    with pytest.raises(OutOfServiceAreaError):
        FallbackAQProvider(primary, fallback).sample([Point(0, 0)], TS)
    with pytest.raises(AQUnavailableError, match="synthetic"):
        FallbackAQProvider(primary, SyntheticAQProvider(10, 80)).sample([Point(106.8, -6.2)], TS)


def test_synthetic_is_seeded_cell_and_hour_stable() -> None:
    provider = SyntheticAQProvider(10, 80, seed=123)
    points = [Point(106.8, -6.2), Point(106.81, -6.21)]
    first = provider.sample(points, TS)
    reversed_result = provider.sample(list(reversed(points)), TS + timedelta(minutes=20))
    assert first.p50.tolist() == list(reversed(reversed_result.p50.tolist()))
    assert first.data_quality == "synthetic"
    assert np.all(first.p10 <= first.p50)
    assert np.all(first.p50 <= first.p90)
    assert not np.array_equal(first.p50, provider.sample(points, TS + timedelta(hours=1)).p50)


@pytest.mark.parametrize("values", [(20, 10, 30), (-1, 10, 30), (1, float("nan"), 30)])
def test_invalid_quantiles_fail_closed(values: Sequence[float]) -> None:
    with pytest.raises(AQUnavailableError):
        Pm25Samples(*(np.array([v]) for v in values), TS, "real", "test")
