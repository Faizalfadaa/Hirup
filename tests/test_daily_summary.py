import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from services.api.main import create_app
from services.api.refresh import refresh
from services.api.runtime import Runtime
from services.api.schemas.aq import DailySummaryResponse
from services.exposure.advice_aq import JAKARTA, HistoricalAQInput, HistoricalAQProvider
from services.exposure.aq_provider import (
    AQUnavailableError,
    CogAQProvider,
    OutOfServiceAreaError,
    Pm25Samples,
    RasterManifest,
)
from services.exposure.aq_service import AQService
from services.exposure.daily_summary import DailySummaryService, daily_mean
from services.exposure.geometry import Point, hour_key
from services.exposure.params import UnverifiedParamsWarning, load_params
from tests.test_aq_provider import BOUNDS
from tests.test_forecast import NOW, POINT, history, history_document
from tests.test_plan_api import FlatAQ

TODAY = NOW.astimezone(JAKARTA).date()


@pytest.fixture
def params():
    with pytest.warns(UnverifiedParamsWarning):
        return load_params()


def manifest(ts, *, kind="nowcast", generated=None, quality="real"):
    generated = generated if generated is not None else ts
    return RasterManifest.model_validate(
        {
            "manifest_version": "1.0",
            "model_version": "unit-test-interface-fake",
            "generated_at": generated,
            "valid_hour": ts,
            "kind": kind,
            "lead_hours": int((ts - hour_key(generated)).total_seconds() // 3600),
            "crs": "EPSG:32748",
            "resolution_m": 100,
            "bbox_wgs84": asdict(BOUNDS),
            "units": "ug/m3",
            "files": {q: f"test/pm25_{ts:%Y%m%d%H}_{q}.tif" for q in ("p10", "p50", "p90")},
            "data_quality": quality,
        }
    )


class HourlyFake:
    """Contract interface fake; production values are never derived from this object."""

    def __init__(self, day, now):
        self.manifests = {}
        self.calls = []
        start = datetime.combine(day, time.min, JAKARTA)
        for h in range(24):
            ts = hour_key(start + timedelta(hours=h))
            future = ts > hour_key(now)
            self.manifests[ts] = manifest(
                ts,
                kind="forecast" if future else "nowcast",
                generated=hour_key(now) if future else ts,
            )

    def manifest(self, ts):
        try:
            return self.manifests[ts]
        except KeyError:
            raise AQUnavailableError("missing hour") from None

    def sample(self, points, ts):
        self.calls.append(ts)
        m = self.manifest(ts)
        value = ts.astimezone(JAKARTA).hour + 1
        return Pm25Samples(
            np.full(1, value - 1),
            np.full(1, value),
            np.full(1, value + 1),
            ts,
            m.data_quality,
            "cog",
            m.model_version,
            m.generated_at,
        )


def test_hand_computed_mean_and_cigarettes_use_contract(params) -> None:
    yesterday = TODAY - timedelta(days=1)
    cog = HourlyFake(yesterday, NOW)
    result = DailySummaryService(BOUNDS, params, cog, now=lambda: NOW).summarize(POINT, yesterday)
    assert result.mean_pm25 == 12.5
    assert result.cig_eq_day == pytest.approx(300 / 528)
    assert result.data_quality == "real"
    assert result.age_s == 86400 + 7 * 3600 + 15 * 60
    assert len(cog.calls) == 24
    assert cog.calls[0].astimezone(JAKARTA).hour == 0
    assert cog.calls[-1].astimezone(JAKARTA).hour == 23
    # Conversion must follow loaded parameters, rather than a hardcoded constant.
    adjusted = replace(params, ugh_m3_per_cigarette=1000)
    changed = DailySummaryService(BOUNDS, adjusted, cog, now=lambda: NOW).summarize(
        POINT, yesterday
    )
    assert changed.cig_eq_day == pytest.approx(0.3)


@pytest.mark.parametrize("quality", ["real", "approximated", "synthetic"])
def test_today_default_forecast_quality_and_oldest_age(params, quality) -> None:
    cog = HourlyFake(TODAY, NOW)
    cog.manifests = {
        ts: m.model_copy(update={"data_quality": quality}) for ts, m in cog.manifests.items()
    }
    result = DailySummaryService(
        BOUNDS, params, cog, allow_synthetic=True, now=lambda: NOW
    ).summarize(POINT)
    assert result.date == TODAY
    assert result.mean_pm25 == 12.5
    assert result.data_quality == ("synthetic" if quality == "synthetic" else "approximated")
    assert result.age_s == 7 * 3600 + 15 * 60


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "future-nowcast",
        "unpublished",
        "wrong-lead",
        "wrong-model",
        "wrong-cycle",
        "wrong-nowcast",
    ],
)
def test_invalid_hour_discards_whole_cog_day(params, case) -> None:
    cog = HourlyFake(TODAY, NOW)
    ts = hour_key(datetime.combine(TODAY, time(12), JAKARTA))
    m = cog.manifests[ts]
    changes = {
        "future-nowcast": {"kind": "nowcast", "lead_hours": 0},
        "unpublished": {"generated_at": NOW + timedelta(hours=1)},
        "wrong-lead": {"lead_hours": 2},
        "wrong-model": {"model_version": "other"},
        "wrong-cycle": {"generated_at": hour_key(NOW) - timedelta(hours=1), "lead_hours": 6},
        "wrong-nowcast": {"kind": "nowcast", "lead_hours": 4},
    }
    if case == "missing":
        del cog.manifests[ts]
    else:
        cog.manifests[ts] = m.model_copy(update=changes[case])
    service = DailySummaryService(BOUNDS, params, cog, history(), now=lambda: NOW)
    result = service.summarize(POINT)
    assert result.mean_pm25 == 31.5  # all 24 historical P50s (20..43), no mixture
    assert result.cig_eq_day == pytest.approx(756 / 528)
    assert result.data_quality == "approximated"
    assert result.age_s == 1235700
    service.historical = None
    with pytest.raises(AQUnavailableError, match="complete"):
        service.summarize(POINT)


@pytest.mark.parametrize(
    "field", ["source", "generated_at", "model_version", "quality", "hour", "count"]
)
def test_sample_provenance_mismatch_rejects_day(params, monkeypatch, field) -> None:
    cog = HourlyFake(TODAY, NOW)
    original = cog.sample

    def corrupted(points, ts):
        s = original(points, ts)
        changes = {
            "source": {"source": "cams"},
            "generated_at": {"generated_at": None},
            "model_version": {"model_version": "other"},
            "quality": {"data_quality": "approximated"},
            "hour": {"valid_hour": ts + timedelta(hours=1)},
            "count": {"p10": np.zeros(2), "p50": np.ones(2), "p90": np.full(2, 2)},
        }
        return replace(s, **changes[field])

    monkeypatch.setattr(cog, "sample", corrupted)
    with pytest.raises(AQUnavailableError):
        DailySummaryService(BOUNDS, params, cog, now=lambda: NOW).summarize(POINT)


def test_refresh_between_hour_reads_rejects_mixed_publications(params, monkeypatch) -> None:
    cog = HourlyFake(TODAY, NOW)
    original = cog.sample

    def reloading(points, ts):
        s = original(points, ts)
        if len(cog.calls) == 24:
            first = min(cog.manifests)
            cog.manifests[first] = cog.manifests[first].model_copy(update={"model_version": "new"})
        return s

    monkeypatch.setattr(cog, "sample", reloading)
    with pytest.raises(AQUnavailableError):
        DailySummaryService(BOUNDS, params, cog, now=lambda: NOW).summarize(POINT)


@pytest.mark.parametrize("case", ["missing-hour", "future-period", "overlap", "uncovered"])
def test_incomplete_historical_day_cannot_return_summary(params, case) -> None:
    document = history_document()
    target = TODAY
    if case == "missing-hour":
        del document["hours"]["2:23"]
    elif case == "future-period":
        document["period_end"] = TODAY.isoformat()
    elif case == "overlap":
        target = date(2026, 9, 30)
    else:
        document["bbox_wgs84"]["min_lon"] = 106.84
    historical = HistoricalAQProvider(HistoricalAQInput.model_validate(document))
    with pytest.raises(AQUnavailableError):
        DailySummaryService(BOUNDS, params, None, historical, now=lambda: NOW).summarize(
            POINT, target
        )


def test_default_day_uses_wib_at_utc_date_boundary(params) -> None:
    now = datetime(2026, 10, 18, 18, 30, tzinfo=UTC)  # Monday 01:30 WIB
    document = history_document()
    document["hours"]["0:00"] = {"p10": 0, "p50": 0, "p90": 0}
    h = HistoricalAQProvider(HistoricalAQInput.model_validate(document))
    result = DailySummaryService(BOUNDS, params, None, h, now=lambda: now).summarize(POINT)
    assert result.date == date(2026, 10, 19)
    assert result.mean_pm25 == pytest.approx((756 - 20) / 24)


@pytest.mark.parametrize("values", [[], [1] * 23, [1] * 25, [float("nan")] * 24, [-1] * 24])
def test_pure_daily_mean_rejects_incomplete_or_invalid_values(values) -> None:
    with pytest.raises(AQUnavailableError):
        daily_mean(values)


def test_zero_and_overflow_handling(params) -> None:
    assert daily_mean([0] * 24) == 0
    assert daily_mean([50] * 24) == 50
    document = history_document()
    document["hours"] = {k: {"p10": 1e308, "p50": 1e308, "p90": 1e308} for k in document["hours"]}
    h = HistoricalAQProvider(HistoricalAQInput.model_validate(document))
    with pytest.raises(AQUnavailableError, match="finite"):
        DailySummaryService(BOUNDS, params, None, h, now=lambda: NOW).summarize(POINT)


def test_maximum_finite_values_return_unavailable_instead_of_raw_overflow() -> None:
    with pytest.raises(AQUnavailableError, match="precision"):
        daily_mean([sys.float_info.max] * 24)


async def test_http_contract_date_default_age_and_errors(params) -> None:
    configured = Runtime(AQService(FlatAQ(), BOUNDS), params=params)
    configured.configure_daily_summary(history())
    configured.daily_summary.now = lambda: NOW
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        query = {"lat": POINT.lat, "lon": POINT.lon}
        reply = await client.get("/v1/aq/daily-summary", params=query)
        assert reply.status_code == 200
        body = DailySummaryResponse.model_validate(reply.json())
        assert body.date == TODAY
        assert body.mean_pm25 == 31.5
        assert body.cig_eq_day == pytest.approx(756 / 528)
        assert body.ispu_category is None
        assert body.data_quality == "approximated"
        assert int(reply.headers["X-Data-Age-Seconds"]) == 1235700
        explicit = await client.get("/v1/aq/daily-summary", params={**query, "date": "2026-10-15"})
        assert explicit.json()["date"] == "2026-10-15"
        for invalid in ("invalid", "2026-02-30"):
            response = await client.get("/v1/aq/daily-summary", params={**query, "date": invalid})
            assert response.status_code == 400
            assert response.headers["content-type"] == "application/problem+json"
        outside = await client.get("/v1/aq/daily-summary", params={"lat": 0, "lon": 0})
        assert outside.status_code == 404
        assert outside.json()["type"] == "out_of_service_area"
        configured.daily_summary.historical = None
        missing = await client.get("/v1/aq/daily-summary", params=query)
        assert missing.status_code == 503
        assert missing.json()["type"] == "data_unavailable"
        assert missing.headers["content-type"] == "application/problem+json"
        configured.daily_summary = None
        assert (await client.get("/v1/aq/daily-summary", params=query)).status_code == 503


async def test_startup_and_refresh_share_history_and_retain_valid_input(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps(history_document()))
    async with httpx.AsyncClient() as client:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(
                client, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_AQ_HISTORY": str(path)}
            )
        configured.daily_summary.now = lambda: NOW
        assert configured.daily_summary.historical is configured.forecast.historical
        assert configured.daily_summary.summarize(POINT).mean_pm25 == 31.5
        document = history_document()
        document["hours"] = {k: {"p10": 10, "p50": 50, "p90": 60} for k in document["hours"]}
        path.write_text(json.dumps(document))
        refresh(configured, NOW, (), None, None, path)
        assert configured.daily_summary.historical is configured.advice_aq.historical
        assert configured.daily_summary.summarize(POINT).cig_eq_day == pytest.approx(1200 / 528)
        path.write_text("{}")
        refresh(configured, NOW, (), None, None, path)
        assert configured.daily_summary.summarize(POINT).mean_pm25 == 50
        with pytest.warns(UnverifiedParamsWarning):
            missing = Runtime.from_env(client, {"HIRUP_DATA_DIR": str(tmp_path)})
        with pytest.raises(AQUnavailableError):
            missing.daily_summary.summarize(POINT)


def daily_cogs(root):
    paths = []
    start = datetime.combine(TODAY, time.min, JAKARTA)
    for h in range(24):
        ts = hour_key(start + timedelta(hours=h))
        folder = root / ts.strftime("%Y%m%d%H")
        folder.mkdir()
        files = {}
        for q, offset in (("p10", -1), ("p50", 0), ("p90", 1)):
            path = folder / f"pm25_{ts:%Y%m%d%H}_{q}.tif"
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
                writer.write(np.full((2, 2), h + 1 + offset, dtype="float32"), 1)
            files[q] = path.relative_to(root).as_posix()
        future = ts > hour_key(NOW)
        m = manifest(
            ts,
            kind="forecast" if future else "nowcast",
            generated=hour_key(NOW) if future else ts,
            quality="synthetic",
        )
        raw = m.model_dump(mode="json")
        raw["model_version"] = "synthetic-test-only"
        raw["files"] = files
        path = folder / "manifest.json"
        path.write_text(json.dumps(raw))
        paths.append(path)
    return paths


async def test_actual_cog_day_synthetic_http_and_production_rejection(
    tmp_path: Path, params
) -> None:
    cog = CogAQProvider(tmp_path, daily_cogs(tmp_path), bounds=BOUNDS, allow_synthetic=True)
    configured = Runtime(AQService(FlatAQ(), BOUNDS), params=params, cog=cog)
    configured.daily_summary = DailySummaryService(
        BOUNDS, params, cog, allow_synthetic=True, now=lambda: NOW
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
        ) as client:
            query = {"lat": POINT.lat, "lon": POINT.lon}
            reply = await client.get("/v1/aq/daily-summary", params=query)
            assert reply.status_code == 200
            assert reply.json()["mean_pm25"] == 12.5
            assert reply.json()["data_quality"] == "synthetic"
            configured.daily_summary.allow_synthetic = False
            assert (await client.get("/v1/aq/daily-summary", params=query)).status_code == 503
            configured.daily_summary.historical = history()
            fallback = await client.get("/v1/aq/daily-summary", params=query)
            assert fallback.json()["mean_pm25"] == 31.5
            assert fallback.json()["data_quality"] == "approximated"
    finally:
        cog.close()


def test_outside_domain_rejected_before_missing_data(params) -> None:
    with pytest.raises(OutOfServiceAreaError):
        DailySummaryService(BOUNDS, params, None).summarize(Point(0, 0))


@pytest.mark.parametrize("target", [date(1, 1, 1), date(9999, 12, 31)])
def test_extreme_valid_date_returns_data_unavailable_not_overflow(params, target) -> None:
    with pytest.raises(AQUnavailableError):
        DailySummaryService(BOUNDS, params, None, now=lambda: NOW).summarize(POINT, target)


def test_future_day_uses_complete_history_when_forecast_horizon_cannot_cover_it(params) -> None:
    tomorrow = TODAY + timedelta(days=1)
    result = DailySummaryService(BOUNDS, params, None, history(), now=lambda: NOW).summarize(
        POINT, tomorrow
    )
    assert result.date == tomorrow
    assert result.mean_pm25 == 31.5
    assert result.data_quality == "approximated"


def test_archived_past_forecasts_from_completed_cycles_remain_approximated(params) -> None:
    yesterday = TODAY - timedelta(days=1)
    cog = HourlyFake(yesterday, NOW)
    cog.manifests = {
        ts: manifest(ts, kind="forecast", generated=ts - timedelta(hours=1)) for ts in cog.manifests
    }
    result = DailySummaryService(BOUNDS, params, cog, now=lambda: NOW).summarize(POINT, yesterday)
    assert result.mean_pm25 == 12.5
    assert result.data_quality == "approximated"
    assert result.age_s == 86400 + 8 * 3600 + 15 * 60


@pytest.mark.parametrize("change", [{"source": "unsourced"}, {"data_quality": "synthetic"}])
def test_historical_sample_cannot_lose_provenance_or_hide_synthetic(
    params, monkeypatch, change
) -> None:
    historical = history()
    original = historical.sample

    def corrupted(points, ts):
        return replace(original(points, ts), **change)

    monkeypatch.setattr(historical, "sample", corrupted)
    with pytest.raises(AQUnavailableError, match="provenance"):
        DailySummaryService(BOUNDS, params, None, historical, now=lambda: NOW).summarize(POINT)
