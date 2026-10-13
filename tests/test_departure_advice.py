import asyncio
from dataclasses import replace
from datetime import UTC, timedelta

import httpx
import pytest

from services.api.main import create_app
from services.api.schemas.routes import DepartureAdviceResponse
from services.exposure.advice_aq import HistoricalAQInput, HistoricalAQProvider
from services.exposure.aq_provider import AQUnavailableError
from services.exposure.engine import Quantiles
from services.routing.departure_advice import DepartureAdvice, SlotEstimate, compare_slots
from services.routing.models import Query
from tests.test_advice_aq import artifact
from tests.test_plan_api import POINTS, TS, FixedRouter, FlatAQ, runtime


def estimates(dose: float = 100) -> tuple[SlotEstimate, ...]:
    return tuple(
        SlotEstimate(
            TS + timedelta(minutes=15 * i),
            600 + 10 * i,
            Quantiles(dose + 10 * i, dose + 10 * i, dose + 10 * i),
            "real",
        )
        for i in range(-6, 7)
    )


def test_hand_computed_deltas_and_complete_window() -> None:
    result = compare_slots(estimates(), TS)
    assert result.slots[0].delta_dose_pct == pytest.approx(-60)
    assert result.slots[0].delta_duration_s == -60
    assert result.slots[6].delta_dose_pct == 0
    assert result.slots[-1].delta_dose_pct == pytest.approx(60)
    assert result.best_slot == TS - timedelta(minutes=90)
    assert result.data_quality == "real"


def test_zero_dose_ties_prefer_requested_time_and_never_divide_by_zero() -> None:
    slots = tuple(replace(slot, dose=Quantiles(0, 0, 0), duration_s=600) for slot in estimates())
    result = compare_slots(slots, TS)
    assert result.best_slot == TS
    assert all(slot.delta_dose_pct == 0 for slot in result.slots)
    positive = (replace(slots[0], dose=Quantiles(1, 1, 1)), *slots[1:])
    with pytest.raises(AQUnavailableError, match="undefined"):
        compare_slots(positive, TS)


def test_missing_baseline_or_duplicate_slot_cannot_produce_advice() -> None:
    with pytest.raises(AQUnavailableError, match="complete"):
        compare_slots(estimates()[:6] + estimates()[7:], TS)
    with pytest.raises(AQUnavailableError, match="complete"):
        compare_slots((estimates()[0], *estimates()[1:-1], estimates()[0]), TS)
    mixed = (*estimates()[:-1], replace(estimates()[-1], data_quality="approximated"))
    assert compare_slots(mixed, TS).data_quality == "approximated"


def test_non_finite_delta_cannot_escape_as_json() -> None:
    slots = tuple(replace(slot, dose=Quantiles(1, 1, 1)) for slot in estimates())
    tiny = replace(slots[6], dose=Quantiles(1e-320, 1e-320, 1e-320))
    with pytest.raises(AQUnavailableError, match="finite"):
        compare_slots((*slots[:6], tiny, *slots[7:]), TS)


class DepartingRouter:
    def __init__(self) -> None:
        self.candidate = runtime().planner.transit.items[0]
        self.peak = self.active = self.calls = 0
        self.profiles: set[str] = set()
        self.modes: set[str] = set()

    async def candidates(self, query: Query):
        self.calls += 1
        self.profiles.add(query.profile)
        self.modes.add(query.mode)
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0)
        self.active -= 1
        return (replace(self.candidate, depart_at=query.anchor),)


async def test_routing_is_recomputed_per_slot_and_shared_capacity_is_bounded() -> None:
    configured = runtime()
    router = DepartingRouter()
    configured.planner.transit = router
    configured.planner.car = configured.planner.motorcycle = FixedRouter()
    configured.configure_advice(demo=True)
    await asyncio.gather(
        configured.advice.advise(Query(*POINTS, TS)),
        configured.advice.advise(Query(*POINTS, TS, profile="rentan")),
    )
    assert router.calls == 26
    assert router.peak <= 2
    assert router.profiles == {"umum", "rentan"}
    assert router.modes == {"transit"}
    assert router.active == 0


async def test_endpoint_contract_slot_quantiles_profile_and_time_zone() -> None:
    configured = runtime()
    configured.planner.transit = DepartingRouter()
    configured.configure_advice(demo=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        result = await client.get(
            "/v1/routes/departure-advice",
            params={
                "origin_lat": POINTS[0].lat,
                "origin_lon": POINTS[0].lon,
                "destination_lat": POINTS[1].lat,
                "destination_lon": POINTS[1].lon,
                "around": TS.astimezone(UTC).isoformat(),
                "sensitivity": "rentan",
            },
        )
    assert result.status_code == 200
    body = DepartureAdviceResponse.model_validate(result.json())
    assert len(body.slots) == 13
    assert body.requested_depart_at.utcoffset() == timedelta(hours=7)
    assert body.sensitivity == "rentan"
    assert body.data_quality == "synthetic"
    assert body.slots[6].delta_dose_pct == 0
    assert body.slots[6].duration_s == 900
    assert all(s.dose_ug_p10 <= s.dose_ug <= s.dose_ug_p90 for s in body.slots)


@pytest.mark.parametrize(
    ("extra", "status"),
    [({"origin_lat": 0, "origin_lon": 0}, 404), ({"around": "2026-10-14T07:00:00"}, 400)],
)
async def test_advice_http_validation_and_area_errors(
    extra: dict[str, object], status: int
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        result = await client.get(
            "/v1/routes/departure-advice",
            params={
                "origin_lat": -6.2,
                "origin_lon": 106.8,
                "destination_lat": -6.21,
                "destination_lon": 106.81,
                **extra,
            },
        )
    assert result.status_code == status
    assert result.headers["content-type"] == "application/problem+json"


async def test_production_refuses_synthetic_and_finishes_all_slot_tasks() -> None:
    configured = runtime()
    router = DepartingRouter()
    configured.planner.transit = router
    configured.configure_advice()  # Unit synthetic primary is forbidden without explicit demo.
    with pytest.raises(AQUnavailableError):
        await configured.advice.advise(Query(*POINTS, TS))
    assert router.calls == 13
    assert router.active == 0


async def test_one_missing_aq_hour_returns_503_for_whole_window() -> None:
    class MissingHourAQ(FlatAQ):
        def sample(self, points, ts):
            if ts.hour == (TS + timedelta(minutes=90)).hour:
                raise AQUnavailableError("Test gap in one hour")
            return super().sample(points, ts)

    configured = runtime()
    configured.aq.provider = MissingHourAQ()
    configured.planner.transit = DepartingRouter()
    configured.configure_advice(demo=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        result = await client.get(
            "/v1/routes/departure-advice",
            params={
                "origin_lat": POINTS[0].lat,
                "origin_lon": POINTS[0].lon,
                "destination_lat": POINTS[1].lat,
                "destination_lon": POINTS[1].lon,
                "around": TS.isoformat(),
            },
        )
    assert result.status_code == 503
    assert result.json()["type"] == "data_unavailable"


async def test_sourced_history_to_advice_has_hand_computed_relative_dose() -> None:
    historical = HistoricalAQProvider(
        HistoricalAQInput.model_validate(
            {
                **artifact(),
                "hours": {
                    f"2:{hour:02d}": {"p10": value / 2, "p50": value, "p90": value * 2}
                    for hour, value in ((5, 10), (6, 20), (7, 30), (8, 40))
                },
            }
        )
    )
    configured = runtime()
    configured.planner.transit = DepartingRouter()
    configured.configure_advice(historical=historical)
    result = await configured.advice.advise(Query(*POINTS, TS))
    assert result.data_quality == "approximated"
    # All 05:xx slots tie on dose/duration; prefer the one nearest the requested time.
    assert result.best_slot == TS - timedelta(minutes=45)
    assert result.slots[0].delta_dose_pct == pytest.approx(-50)
    assert result.slots[6].delta_dose_pct == 0
    assert result.slots[-1].delta_dose_pct == pytest.approx(100)
    assert result.slots[6].estimate.dose.p10 == result.slots[6].estimate.dose.p50 / 2


def test_invalid_concurrency_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        DepartureAdvice(runtime().planner, concurrency=0)
