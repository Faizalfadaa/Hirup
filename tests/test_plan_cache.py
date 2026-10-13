import asyncio
import json
from dataclasses import replace
from datetime import UTC, timedelta
from pathlib import Path

import httpx
import pytest

from services.api.main import create_app
from services.api.refresh import refresh
from services.api.schemas.routes import PlanResponse
from services.exposure.aq_provider import AQUnavailableError, OutOfServiceAreaError
from services.exposure.engine import Mode
from services.exposure.geometry import Point, project_points, unproject
from services.routing.models import Query
from services.routing.plan_cache import PlanCache, approximate
from tests.test_departure_advice import DepartingRouter
from tests.test_plan_api import BOUNDS, POINTS, TS, FixedRouter, request, runtime


class CountingPlanner:
    def __init__(self) -> None:
        self.calls = 0
        self.queries: list[Query] = []
        self.configured = runtime()

    async def plan(self, query: Query):
        self.calls += 1
        self.queries.append(query)
        for router in (
            self.configured.planner.transit,
            self.configured.planner.motorcycle,
            self.configured.planner.car,
        ):
            if isinstance(router, FixedRouter):
                router.items = tuple(
                    replace(
                        item,
                        depart_at=query.anchor,
                        legs=tuple(
                            replace(leg, points=(query.origin, query.destination))
                            for leg in item.legs
                        ),
                    )
                    for item in router.items
                )
        return await self.configured.planner.plan(query)


def cache(**kwargs):
    planner = CountingPlanner()
    return PlanCache(planner, BOUNDS, **kwargs), planner


def query(**kwargs) -> Query:
    return Query(*POINTS, TS, **kwargs)


async def test_ttl_uses_monotonic_time_and_expires_at_ten_minutes() -> None:
    now = [0.0]
    cached, planner = cache(clock=lambda: now[0])
    first = await cached.plan(query())
    now[0] = 599.999
    assert await cached.plan(query()) is first
    now[0] = 600
    await cached.plan(query())
    assert planner.calls == 2
    assert cached.stats()["hits"] == 1


async def test_lru_is_bounded_and_hit_updates_recency() -> None:
    cached, planner = cache(capacity=2)
    a, b, c = (replace(query(), anchor=TS + timedelta(minutes=i)) for i in range(3))
    await cached.plan(a)
    await cached.plan(b)
    await cached.plan(a)
    await cached.plan(c)
    assert cached.stats()["entries"] == 2
    await cached.plan(b)
    assert planner.calls == 4


def test_public_representatives_and_exact_time_are_independent_of_user_coordinates() -> None:
    cached, _ = cache()
    key, canonical = cached.normalize(query())
    x, y = project_points((canonical.origin, canonical.destination))
    assert (float(x[0]) % 100, float(y[0]) % 100) == pytest.approx((50, 50))
    assert canonical.origin != POINTS[0]
    assert canonical.destination != POINTS[1]
    nearby = replace(query(), origin=unproject(float(x[0]) + 1, float(y[0]) + 1))
    other_key, other_canonical = cached.normalize(nearby)
    assert key == other_key
    assert canonical == other_canonical
    assert POINTS[0].lon not in key.origin_cell
    assert canonical.anchor == TS.astimezone(UTC)


@pytest.mark.parametrize(
    "change",
    [
        {"mode": "walk"},
        {"profile": "rentan"},
        {"max_walk_m": 500},
        {"excluded_modes": (Mode.BUS,)},
        {"avoid_transfers": True},
        {"arrive_by": True},
        {"include_comparison": False},
        {"anchor": TS + timedelta(seconds=1)},
        {"anchor": TS + timedelta(days=1)},
    ],
)
def test_all_preferences_and_exact_departure_are_separate(change: dict[str, object]) -> None:
    cached, _ = cache()
    assert cached.normalize(query())[0] != cached.normalize(replace(query(), **change))[0]


def test_equivalent_exclusion_sets_and_timezone_share_key() -> None:
    cached, _ = cache()
    a = query(excluded_modes=(Mode.WALK, Mode.BUS, Mode.WALK))
    b = replace(a, anchor=TS.astimezone(UTC), excluded_modes=(Mode.BUS, Mode.WALK))
    assert cached.normalize(a)[0] == cached.normalize(b)[0]


def test_outside_area_naive_timestamp_and_border_handling() -> None:
    cached, _ = cache()
    with pytest.raises(OutOfServiceAreaError):
        cached.normalize(replace(query(), origin=Point(0, 0)))
    with pytest.raises(ValueError, match="timezone"):
        cached.normalize(replace(query(), anchor=TS.replace(tzinfo=None)))
    _, canonical = cached.normalize(replace(query(), origin=Point(BOUNDS.min_lon, BOUNDS.min_lat)))
    assert BOUNDS.contains(canonical.origin)


async def test_concurrent_requests_share_one_plan_and_cancelled_caller_does_not_cancel_it() -> None:
    cached, planner = cache()
    original = planner.plan
    started, finish = asyncio.Event(), asyncio.Event()

    async def waiting(q):
        started.set()
        await finish.wait()
        return await original(q)

    planner.plan = waiting
    first = asyncio.create_task(cached.plan(query()))
    await started.wait()
    second = asyncio.create_task(cached.plan(query()))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    finish.set()
    result = await second
    assert await cached.plan(query()) is result
    assert planner.calls == 1
    assert cached.stats()["joins"] == 1
    assert cached.stats()["in_flight"] == 0


async def test_error_is_not_cached_and_next_request_can_retry() -> None:
    cached, planner = cache()
    original = planner.plan

    async def fail_once(q):
        planner.plan = original
        raise AQUnavailableError("Unit test unavailable hour")

    planner.plan = fail_once
    with pytest.raises(AQUnavailableError):
        await cached.plan(query())
    await cached.plan(query())
    assert cached.stats()["entries"] == 1
    assert cached.stats()["misses"] == 2


async def test_refresh_invalidates_in_flight_result_and_replans() -> None:
    cached, planner = cache()
    original = planner.plan
    started, finish = asyncio.Event(), asyncio.Event()
    calls = 0

    async def changed(q):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await finish.wait()
        return await original(q)

    planner.plan = changed
    task = asyncio.create_task(cached.plan(query()))
    await started.wait()
    await asyncio.to_thread(cached.invalidate)
    finish.set()
    result = await task
    assert calls == 2
    assert await cached.plan(query()) is result
    assert cached.stats()["entries"] == 1


async def test_in_flight_capacity_rejects_unique_jobs_but_allows_same_key_join() -> None:
    cached, planner = cache(max_in_flight=1)
    original = planner.plan
    started, finish = asyncio.Event(), asyncio.Event()

    async def waiting(q):
        started.set()
        await finish.wait()
        return await original(q)

    planner.plan = waiting
    first = asyncio.create_task(cached.plan(query()))
    await started.wait()
    with pytest.raises(AQUnavailableError, match="capacity"):
        await cached.plan(replace(query(), profile="rentan"))
    second = asyncio.create_task(cached.plan(query()))
    await asyncio.sleep(0)
    finish.set()
    await asyncio.gather(first, second)
    assert planner.calls == 1
    assert cached.stats()["in_flight"] == 0


async def test_cache_worker_and_entries_contain_only_canonical_queries() -> None:
    cached, planner = cache()
    await cached.plan(query())
    assert all(q.origin != POINTS[0] and q.destination != POINTS[1] for q in planner.queries)
    for entry in cached._entries.values():
        routes = [option.scored for option in entry.result.options]
        routes.extend(r for r in (entry.result.motorcycle, entry.result.car) if r is not None)
        points = [point for route in routes for leg in route.candidate.legs for point in leg.points]
        assert POINTS[0] not in points
        assert POINTS[1] not in points
    assert cached.stats()["in_flight"] == 0


async def test_http_responses_have_new_request_ids_and_cache_does_not_store_http_models() -> None:
    configured = runtime()
    configured.planner.transit = DepartingRouter()
    configured.configure_plan_cache()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        first = await client.post("/v1/routes/plan", json=request())
        second = await client.post("/v1/routes/plan", json=request())
    assert first.status_code == second.status_code == 200
    a, b = (PlanResponse.model_validate(reply.json()) for reply in (first, second))
    assert a.request_id != b.request_id
    assert "sel 100 m" in a.disclaimer
    assert a.options == b.options
    assert configured.plan_cache.stats()["hits"] == 1
    assert "rq_" not in repr(configured.plan_cache._entries)


async def test_runtime_refresh_clears_plan_and_advice_caches() -> None:
    configured = runtime()
    configured.planner.transit = DepartingRouter()
    configured.configure_plan_cache()
    configured.configure_advice(demo=True)
    await configured.plan(query())
    await configured.advice.advise(query())
    assert configured.plan_cache.stats()["entries"] == 1
    assert configured.advice_cache.stats()["entries"] == 13
    refresh(configured, TS, (), None, None)
    assert configured.plan_cache.stats()["entries"] == 0
    assert configured.advice_cache.stats()["entries"] == 0


async def test_failed_publication_cannot_leave_cached_results(tmp_path: Path) -> None:
    configured = runtime()
    configured.planner.transit = DepartingRouter()
    configured.configure_plan_cache()
    await configured.plan(query())
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"source": "unit test", "data_quality": "synthetic"}))
    with pytest.raises(ValueError, match="provenance"):
        refresh(configured, TS, (), invalid, None)
    assert configured.plan_cache.stats()["entries"] == 0


async def test_grid_quality_is_at_least_approximated_without_downgrading_synthetic() -> None:
    configured = runtime()
    result = await configured.planner.plan(query())
    assert approximate(result).data_quality == "synthetic"
    selected = result.options[0]
    real_scored = replace(
        selected.scored,
        data_quality="real",
        candidate=replace(selected.scored.candidate, data_quality="real"),
    )
    real_result = replace(
        result,
        options=(replace(selected, scored=real_scored),),
        motorcycle=real_scored,
        car=real_scored,
        data_quality="real",
    )
    updated = approximate(real_result)
    assert updated.data_quality == "approximated"
    assert updated.options[0].scored.data_quality == "approximated"
    assert updated.motorcycle.data_quality == "approximated"
    assert updated.car.data_quality == "approximated"
    assert updated.options[0].scored.exposure is real_scored.exposure
    assert real_result.data_quality == "real"


@pytest.mark.parametrize("settings", [{"ttl_s": 0}, {"capacity": 0}, {"ttl_s": float("inf")}])
def test_invalid_cache_bounds_are_rejected(settings: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="positive"):
        cache(**settings)
