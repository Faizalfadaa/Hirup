import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from services.api.refresh import refresh
from services.api.runtime import Runtime
from services.exposure.advice_aq import AdviceAQProvider, HistoricalAQInput, HistoricalAQProvider
from services.exposure.aq_provider import AQUnavailableError, CogAQProvider, IdwAQProvider
from services.exposure.geometry import Point, unproject
from services.exposure.params import UnverifiedParamsWarning
from tests.test_aq_provider import BOUNDS, TS, raster_set

POINT = Point(106.8, -6.2)
NOW = TS - timedelta(hours=1)


def artifact() -> dict[str, object]:
    return {
        "source": "unit test observations, not production data",
        "data_quality": "approximated",
        "units": "ug/m3",
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "bbox_wgs84": asdict(BOUNDS),
        "hours": {"2:08": {"p10": 10, "p50": 20, "p90": 30}},
    }


def history() -> HistoricalAQProvider:
    return HistoricalAQProvider(HistoricalAQInput.model_validate(artifact()))


def test_regional_historical_means_preserve_quantiles_and_local_weekday() -> None:
    provider = history()
    sample = provider.sample([POINT, POINT], TS)
    assert sample.p50.tolist() == [20, 20]
    assert sample.p10.tolist() == [10, 10]
    assert sample.p90.tolist() == [30, 30]
    assert sample.data_quality == "approximated"
    assert sample.source.startswith("historical:")
    assert provider.sample([POINT], TS.astimezone()).valid_hour == sample.valid_hour
    with pytest.raises(AQUnavailableError, match="hour of the week"):
        provider.sample([POINT], TS + timedelta(hours=1))
    with pytest.raises(AQUnavailableError, match="cover"):
        provider.sample([Point(0, 0)], TS)


@pytest.mark.parametrize(
    "change",
    [
        {"source": " "},
        {"data_quality": "synthetic"},
        {"units": "mg/m3"},
        {"period_end": "2026-08-01"},
        {"hours": {"7:00": {"p10": 1, "p50": 2, "p90": 3}}},
        {"hours": {"2:08": {"p10": 30, "p50": 20, "p90": 10}}},
        {"hours": {"2:08": {"p10": -1, "p50": 2, "p90": 3}}},
        {"hours": {"2:08": {"p10": 1, "p50": float("nan"), "p90": 3}}},
        {"hours": {}},
    ],
)
def test_invalid_historical_artifacts_are_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        HistoricalAQInput.model_validate({**artifact(), **change})


def test_future_advice_requires_corrected_forecast_or_sourced_history() -> None:
    raw_cams = IdwAQProvider([], BOUNDS, cams={TS: history().sample([POINT], TS).mean()})
    advice = AdviceAQProvider(raw_cams, None, None, now=lambda: NOW)
    with pytest.raises(AQUnavailableError, match="coverage"):
        advice.sample([POINT], TS)
    advice.historical = history()
    assert advice.sample([POINT], TS).source.startswith("historical:")
    # The raw sourced current-hour primary remains available; future policy is advice-only.
    current = AdviceAQProvider(raw_cams, None, None, now=lambda: TS)
    assert current.sample([POINT], TS).source == "cams"


def test_historical_period_cannot_include_target_day_or_unobserved_future() -> None:
    future = HistoricalAQProvider(
        HistoricalAQInput.model_validate({**artifact(), "period_end": "2026-10-14"})
    )
    with pytest.raises(AQUnavailableError, match="overlaps"):
        future.sample([POINT], TS)
    advice = AdviceAQProvider(IdwAQProvider([], BOUNDS), None, future, now=lambda: NOW)
    with pytest.raises(AQUnavailableError, match="coverage"):
        advice.sample([POINT], TS + timedelta(days=7))


def test_forecast_cog_quantiles_and_unpublished_generation(tmp_path: Path) -> None:
    path = raster_set(tmp_path)
    raw = json.loads(path.read_text())
    raw.update(
        kind="forecast", lead_hours=1, generated_at=NOW.isoformat(), data_quality="approximated"
    )
    path.write_text(json.dumps(raw))
    cog = CogAQProvider(tmp_path, [path], bounds=BOUNDS)
    advice = AdviceAQProvider(IdwAQProvider([], BOUNDS), cog, None, now=lambda: NOW)
    point = unproject(699050, 9313950)
    try:
        sample = advice.sample([point], TS)
        assert (sample.p10[0], sample.p50[0], sample.p90[0]) == (5, 10, 15)
        assert sample.source == "cog"
        raw["kind"] = "nowcast"
        path.write_text(json.dumps(raw))
        cog.reload([path])
        with pytest.raises(AQUnavailableError, match="coverage"):
            advice.sample([point], TS)
        raw.update(kind="forecast", generated_at=TS.isoformat())
        path.write_text(json.dumps(raw))
        cog.reload([path])
        with pytest.raises(AQUnavailableError, match="coverage"):
            advice.sample([point], TS)
    finally:
        cog.close()


async def test_history_late_publication_reload_retains_prior_valid_data(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "history.json"
    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(
                http, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_AQ_HISTORY": str(path)}
            )
        assert configured.advice_aq.historical is None
        refresh(configured, NOW, (), None, None, path)
        path.write_text(json.dumps(artifact()))
        refresh(configured, NOW, (), None, None, path)
        assert configured.advice_aq.sample([POINT], TS).p50[0] == 20
        path.write_text(json.dumps({**artifact(), "source": ""}))
        inputs = tmp_path / "inputs.json"
        inputs.write_text(
            json.dumps(
                {
                    "source": "unit test",
                    "data_quality": "approximated",
                    "cams": {NOW.isoformat(): {"p10": 13, "p50": 23, "p90": 33}},
                }
            )
        )
        refresh(configured, NOW, (), inputs, None, path)
        assert "retaining prior observations" in caplog.text
        assert configured.advice_aq.sample([POINT], TS).p50[0] == 20
        assert configured.aq.point(POINT, NOW).p50[0] == 23


def test_local_midnight_uses_jakarta_weekday() -> None:
    provider = HistoricalAQProvider(
        HistoricalAQInput.model_validate(
            {**artifact(), "hours": {"3:00": {"p10": 1, "p50": 2, "p90": 3}}}
        )
    )
    utc = datetime.fromisoformat("2026-10-14T17:15:00+00:00")
    assert provider.sample([POINT], utc).p50[0] == 2
