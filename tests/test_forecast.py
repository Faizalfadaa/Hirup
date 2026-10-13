import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from services.api.main import create_app
from services.api.refresh import refresh
from services.api.runtime import Runtime
from services.api.schemas.aq import AqForecastResponse
from services.exposure.advice_aq import HistoricalAQInput, HistoricalAQProvider
from services.exposure.aq_provider import AQUnavailableError, CogAQProvider
from services.exposure.aq_service import AQService
from services.exposure.forecast import ForecastService
from services.exposure.geometry import hour_key, unproject
from services.exposure.params import UnverifiedParamsWarning
from tests.test_aq_provider import BOUNDS, TS
from tests.test_plan_api import FlatAQ

NOW = TS - timedelta(minutes=45)
GENERATED = hour_key(NOW)
POINT = unproject(699050, 9313950)


def history_document():
    return {
        "source": "hand-computed unit test observations, not production data",
        "data_quality": "approximated",
        "units": "ug/m3",
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "bbox_wgs84": asdict(BOUNDS),
        "hours": {
            f"{day}:{hour:02d}": {"p10": 10 + hour, "p50": 20 + hour, "p90": 30 + hour}
            for day in range(7)
            for hour in range(24)
        },
    }


def history():
    return HistoricalAQProvider(HistoricalAQInput.model_validate(history_document()))


def forecast_files(root: Path, count=2):
    paths = []
    for lead in range(1, count + 1):
        ts = GENERATED + timedelta(hours=lead)
        folder = root / ts.strftime("%Y%m%d%H")
        folder.mkdir()
        files = {}
        for quantile, offset in (("p10", -5), ("p50", 0), ("p90", 5)):
            path = folder / f"pm25_{ts:%Y%m%d%H}_{quantile}.tif"
            # Explicit synthetic, deterministic hand-computed 2x2 rasters.
            pixels = np.array([[10, 20], [30, 40]], dtype="float32") + (lead - 1) * 10 + offset
            with rasterio.open(
                path,
                "w",
                driver="COG",
                height=2,
                width=2,
                count=1,
                dtype="float32",
                crs="EPSG:32748",
                transform=from_origin(699000, 9314000, 100, 100),
                nodata=-9999,
            ) as writer:
                writer.write(pixels, 1)
            files[quantile] = path.relative_to(root).as_posix()
        manifest = {
            "manifest_version": "1.0",
            "model_version": "synthetic-test-only",
            "generated_at": GENERATED.isoformat(),
            "valid_hour": ts.isoformat(),
            "kind": "forecast",
            "lead_hours": lead,
            "crs": "EPSG:32748",
            "resolution_m": 100,
            "bbox_wgs84": asdict(BOUNDS),
            "units": "ug/m3",
            "files": files,
            "data_quality": "synthetic",
        }
        path = folder / "manifest.json"
        path.write_text(json.dumps(manifest))
        paths.append(path)
    return paths


def test_corrected_window_reads_each_hour_and_reports_publication_age(tmp_path: Path) -> None:
    cog = CogAQProvider(tmp_path, forecast_files(tmp_path), bounds=BOUNDS, allow_synthetic=True)
    try:
        service = ForecastService(BOUNDS, cog, allow_synthetic=True, now=lambda: NOW)
        result = service.forecast(POINT, 2)
        assert result.source == "model_corrected"
        assert result.data_quality == "synthetic"
        assert result.age_s == 900
        assert [item.valid_hour for item in result.hours] == [TS, TS + timedelta(hours=1)]
        assert [(h.pm25.p10, h.pm25.p50, h.pm25.p90) for h in result.hours] == [
            (5, 10, 15),
            (15, 20, 25),
        ]
        with pytest.raises(AQUnavailableError, match="complete"):
            ForecastService(BOUNDS, cog, now=lambda: NOW).forecast(POINT, 2)
    finally:
        cog.close()


def test_complete_24_hour_corrected_window(tmp_path: Path) -> None:
    cog = CogAQProvider(tmp_path, forecast_files(tmp_path, 24), bounds=BOUNDS, allow_synthetic=True)
    try:
        result = ForecastService(BOUNDS, cog, allow_synthetic=True, now=lambda: NOW).forecast(
            POINT, 24
        )
        assert len(result.hours) == 24
        assert result.hours[-1].valid_hour == TS + timedelta(hours=23)
        assert result.hours[-1].pm25.p50 == 240
        assert result.data_quality == "synthetic"
    finally:
        cog.close()


def test_same_cycle_files_can_publish_seconds_apart_and_age_uses_oldest(tmp_path: Path) -> None:
    paths = forecast_files(tmp_path)
    first = json.loads(paths[0].read_text())
    first["generated_at"] = (GENERATED + timedelta(seconds=20)).isoformat()
    paths[0].write_text(json.dumps(first))
    cog = CogAQProvider(tmp_path, paths, bounds=BOUNDS, allow_synthetic=True)
    try:
        result = ForecastService(BOUNDS, cog, allow_synthetic=True, now=lambda: NOW).forecast(
            POINT, 2
        )
        assert result.age_s == 900  # Second-hour file is older than the first-hour file.
        assert [h.pm25.p50 for h in result.hours] == [10, 20]
    finally:
        cog.close()


@pytest.mark.parametrize("hours", [1, 24])
def test_historical_horizon_quality_age_and_day_transition(hours) -> None:
    result = ForecastService(BOUNDS, None, history(), now=lambda: NOW).forecast(POINT, hours)
    assert len(result.hours) == hours
    assert result.hours[0].valid_hour == TS
    assert result.hours[-1].valid_hour == TS + timedelta(hours=hours - 1)
    assert result.hours[0].pm25.p50 == 28
    assert result.source == "historical_mean"
    assert result.data_quality == "approximated"
    assert result.age_s == 14 * 86400 + 7 * 3600 + 15 * 60


def test_local_midnight_and_week_boundary_use_jakarta_hours() -> None:
    now = datetime.fromisoformat("2026-10-18T23:45:00+07:00")  # Sunday
    document = history_document()
    document["hours"]["0:00"] = {"p10": 1, "p50": 2, "p90": 3}
    historical = HistoricalAQProvider(HistoricalAQInput.model_validate(document))
    result = ForecastService(BOUNDS, None, historical, now=lambda: now).forecast(POINT, 24)
    assert result.hours[0].valid_hour == datetime.fromisoformat("2026-10-19T00:00:00+07:00")
    assert result.hours[0].pm25.p50 == 2
    assert result.hours[-1].valid_hour == datetime.fromisoformat("2026-10-19T23:00:00+07:00")


def test_incomplete_model_uses_whole_historical_window_not_a_mixture(tmp_path: Path) -> None:
    cog = CogAQProvider(tmp_path, forecast_files(tmp_path, 1), bounds=BOUNDS, allow_synthetic=True)
    try:
        result = ForecastService(
            BOUNDS, cog, history(), allow_synthetic=True, now=lambda: NOW
        ).forecast(POINT, 2)
        assert result.source == "historical_mean"
        assert result.data_quality == "approximated"
        assert [h.pm25.p50 for h in result.hours] == [28, 29]
    finally:
        cog.close()


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "nowcast"},
        {"lead_hours": 1},
        {"generated_at": (TS + timedelta(hours=1)).isoformat()},
        {"model_version": "different-model"},
        {"generated_at": (GENERATED - timedelta(hours=1)).isoformat(), "lead_hours": 3},
    ],
)
def test_mismatched_or_unpublished_forecast_cannot_feed_response(tmp_path: Path, change) -> None:
    paths = forecast_files(tmp_path)
    raw = json.loads(paths[1].read_text())
    paths[1].write_text(json.dumps({**raw, **change}))
    cog = CogAQProvider(tmp_path, paths, bounds=BOUNDS, allow_synthetic=True)
    try:
        with pytest.raises(AQUnavailableError, match="complete"):
            ForecastService(BOUNDS, cog, allow_synthetic=True, now=lambda: NOW).forecast(POINT, 2)
    finally:
        cog.close()


def test_publication_change_during_read_discards_complete_window(
    tmp_path: Path, monkeypatch
) -> None:
    paths = forecast_files(tmp_path)
    cog = CogAQProvider(tmp_path, paths, bounds=BOUNDS, allow_synthetic=True)
    original, calls = cog.sample, []

    def reloading(points, ts):
        samples = original(points, ts)
        calls.append(ts)
        if len(calls) == 2:
            for path in paths:
                raw = json.loads(path.read_text())
                path.write_text(json.dumps({**raw, "model_version": "changed-publication"}))
            cog.reload(paths)
        return samples

    monkeypatch.setattr(cog, "sample", reloading)
    try:
        with pytest.raises(AQUnavailableError, match="complete"):
            ForecastService(BOUNDS, cog, allow_synthetic=True, now=lambda: NOW).forecast(POINT, 2)
    finally:
        cog.close()


@pytest.mark.parametrize(
    "field", ["source", "generated_at", "model_version", "quality", "hour", "count"]
)
def test_sample_provenance_or_shape_mismatch_is_rejected(
    tmp_path: Path, monkeypatch, field
) -> None:
    cog = CogAQProvider(tmp_path, forecast_files(tmp_path, 1), bounds=BOUNDS, allow_synthetic=True)
    original = cog.sample

    def corrupted(points, ts):
        samples = original(points, ts)
        changes = {
            "source": {"source": "cams"},
            "generated_at": {"generated_at": None},
            "model_version": {"model_version": "other"},
            "quality": {"data_quality": "approximated"},
            "hour": {"valid_hour": ts + timedelta(hours=1)},
            "count": {"p10": np.full(2, 5), "p50": np.full(2, 10), "p90": np.full(2, 15)},
        }
        return replace(samples, **changes[field])

    monkeypatch.setattr(cog, "sample", corrupted)
    try:
        with pytest.raises(AQUnavailableError, match="complete"):
            ForecastService(BOUNDS, cog, allow_synthetic=True, now=lambda: NOW).forecast(POINT, 1)
    finally:
        cog.close()


async def test_http_corrected_cog_fixture_is_synthetic_and_production_refuses_it(
    tmp_path: Path,
) -> None:
    cog = CogAQProvider(tmp_path, forecast_files(tmp_path), bounds=BOUNDS, allow_synthetic=True)
    configured = Runtime(AQService(FlatAQ(), BOUNDS), cog=cog)
    configured.forecast = ForecastService(BOUNDS, cog, allow_synthetic=True, now=lambda: NOW)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
        ) as client:
            query = {"lat": POINT.lat, "lon": POINT.lon, "hours": 2}
            reply = await client.get("/v1/aq/forecast", params=query)
            assert reply.status_code == 200
            body = AqForecastResponse.model_validate(reply.json())
            assert body.source == "model_corrected"
            assert body.data_quality == "synthetic"
            assert [h.pm25.p50 for h in body.hours] == [10, 20]
            assert int(reply.headers["X-Data-Age-Seconds"]) == 900
            configured.forecast.allow_synthetic = False
            unavailable = await client.get("/v1/aq/forecast", params=query)
            assert unavailable.status_code == 503
            assert unavailable.json()["type"] == "data_unavailable"
    finally:
        cog.close()


@pytest.mark.parametrize("case", ["missing-hour", "future-period", "uncovered"])
def test_invalid_historical_coverage_returns_no_partial_result(case) -> None:
    document = history_document()
    point = POINT
    if case == "missing-hour":
        del document["hours"]["2:09"]
    elif case == "future-period":
        document["period_end"] = "2026-10-14"
    else:
        document["bbox_wgs84"]["min_lon"] = 106.84
    historical = HistoricalAQProvider(HistoricalAQInput.model_validate(document))
    with pytest.raises(AQUnavailableError):
        ForecastService(BOUNDS, None, historical, now=lambda: NOW).forecast(point, 2)


@pytest.mark.parametrize("hours", [0, 25, True, 1.5])
def test_invalid_domain_horizon_is_rejected(hours) -> None:
    with pytest.raises(ValueError, match="horizon"):
        ForecastService(BOUNDS, None, now=lambda: NOW).forecast(POINT, hours)


async def test_http_history_contract_timezone_and_problem_errors() -> None:
    configured = Runtime(AQService(FlatAQ(), BOUNDS))
    configured.configure_forecast(history())
    configured.forecast.now = lambda: NOW
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        query = {"lat": POINT.lat, "lon": POINT.lon}
        reply = await client.get("/v1/aq/forecast", params=query)
        assert reply.status_code == 200
        body = AqForecastResponse.model_validate(reply.json())
        assert len(body.hours) == 24
        assert body.source == "historical_mean"
        assert body.data_quality == "approximated"
        assert body.hours[0].valid_hour.utcoffset() == timedelta(hours=7)
        assert int(reply.headers["X-Data-Age-Seconds"]) == 1235700
        one = await client.get("/v1/aq/forecast", params={**query, "hours": 1})
        assert len(one.json()["hours"]) == 1
        for hours in (0, 25):
            invalid = await client.get("/v1/aq/forecast", params={**query, "hours": hours})
            assert invalid.status_code == 400
            assert invalid.headers["content-type"] == "application/problem+json"
        outside = await client.get("/v1/aq/forecast", params={"lat": 0, "lon": 0})
        assert outside.status_code == 404
        assert outside.json()["type"] == "out_of_service_area"
        configured.forecast.historical = None
        absent = await client.get("/v1/aq/forecast", params=query)
        assert absent.status_code == 503
        assert absent.json()["type"] == "data_unavailable"
        assert absent.headers["content-type"] == "application/problem+json"


async def test_history_refresh_updates_forecast_with_no_planner_and_retains_valid_artifact(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.json"
    configured = Runtime(AQService(FlatAQ(), BOUNDS))
    configured.configure_forecast()
    configured.forecast.now = lambda: NOW
    path.write_text(json.dumps(history_document()))
    refresh(configured, NOW, (), None, None, path)
    assert configured.forecast.forecast(POINT, 1).hours[0].pm25.p50 == 28
    path.write_text("{}")
    refresh(configured, NOW, (), None, None, path)
    assert configured.forecast.forecast(POINT, 1).hours[0].pm25.p50 == 28


async def test_startup_history_and_missing_inputs_wire_endpoint_without_demo_substitution(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps(history_document()))
    async with httpx.AsyncClient() as client:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(
                client, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_AQ_HISTORY": str(path)}
            )
        configured.forecast.now = lambda: NOW
        assert len(configured.forecast.forecast(POINT, 24).hours) == 24
        assert configured.forecast.historical is configured.advice_aq.historical
        with pytest.warns(UnverifiedParamsWarning):
            missing = Runtime.from_env(client, {"HIRUP_DATA_DIR": str(tmp_path)})
        missing.forecast.now = lambda: NOW
        with pytest.raises(AQUnavailableError, match="complete"):
            missing.forecast.forecast(POINT, 1)
