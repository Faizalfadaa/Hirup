import asyncio
from dataclasses import replace
from datetime import timedelta

import numpy as np
import pytest

from services.exposure.aq_provider import AQUnavailableError, Pm25Samples
from services.exposure.engine import Mode
from services.exposure.geometry import Point, hour_key
from services.routing.models import Candidate, Query, RouteLeg
from tests.test_plan_api import POINTS, TS, FixedRouter, runtime


class CountingAQ:
    def __init__(self, unavailable_point=None):
        self.calls = []
        self.unavailable_point = unavailable_point

    def sample(self, points, ts):
        self.calls.append((points, ts))
        if points[0] == self.unavailable_point:
            raise AQUnavailableError("Test coverage gap")
        values = np.full(len(points), 60.0)
        return Pm25Samples(
            values / 2, values, values * 2, hour_key(ts), "real", "test source", "test-v1"
        )


def route(mode=Mode.BUS, duration=600, points=POINTS, ts=TS):
    return Candidate((RouteLeg(mode, duration, 1000, points),), ts, "approximated")


def test_shared_geometry_and_time_keep_per_mode_duration_and_provenance() -> None:
    planner = runtime().planner
    provider = CountingAQ()
    planner.aq = provider
    candidates = (route(), route(Mode.MOTORCYCLE, 3000), route(Mode.BUS, 1200))
    scored = planner._score_many(candidates)
    assert len(provider.calls) == 1
    assert [item.exposure.dose_ug.p50 for item in scored] == pytest.approx([3.25, 39, 6.5])
    assert all(item.aq_sources == ("test source",) for item in scored)
    assert all(item.model_version == "test-v1" for item in scored)
    assert all(item.data_quality == "approximated" for item in scored)
    assert all(item.exposure.dose_ug.p10 == item.exposure.dose_ug.p50 / 2 for item in scored)
    assert all(item.exposure.dose_ug.p90 == item.exposure.dose_ug.p50 * 2 for item in scored)
    planner._score_many(candidates)
    assert len(provider.calls) == 2  # Request-owned samples do not survive on Planner.


def test_exact_times_and_geometries_do_not_alias() -> None:
    planner = runtime().planner
    provider = CountingAQ()
    planner.aq = provider
    variants = (
        route(),
        route(ts=TS + timedelta(seconds=1)),
        route(ts=TS + timedelta(hours=1)),
        route(points=(POINTS[0], Point(106.802, -6.201))),
    )
    scored = planner._score_many(variants)
    assert len(scored) == 4
    assert len(provider.calls) == 4


def test_road_selection_skips_uncovered_fastest_and_retains_stable_ties() -> None:
    planner = runtime().planner
    gap = Point(106.803, -6.201)
    provider = CountingAQ(unavailable_point=gap)
    planner.aq = provider
    fastest = route(Mode.CAR, 10, (gap, POINTS[1]))
    first_tie = route(Mode.CAR, 20)
    second_tie = replace(first_tie, legs=(replace(first_tie.legs[0], from_name="Other"),))
    slow = route(Mode.CAR, 30)
    comparisons = [
        planner._best_road((slow, fastest, first_tie, second_tie)),
        planner._best_road((fastest,)),
    ]
    assert comparisons[0].candidate == first_tie
    assert comparisons[1] is None
    assert len(provider.calls) == 3  # Slow/tied covered alternatives are not scored.


async def test_road_scoring_starts_before_transit_generation_finishes() -> None:
    planner = runtime().planner
    loop, scored = asyncio.get_running_loop(), asyncio.Event()
    road_points = (Point(106.803, -6.201), POINTS[1])

    class SignallingAQ(CountingAQ):
        def sample(self, points, ts):
            result = super().sample(points, ts)
            if points[0] == road_points[0]:
                loop.call_soon_threadsafe(scored.set)
            return result

    class HoldingTransit(FixedRouter):
        async def candidates(self, query):
            await asyncio.wait_for(scored.wait(), timeout=2)
            return await super().candidates(query)

    planner.aq = SignallingAQ()
    planner.transit = HoldingTransit(planner.transit.items)
    planner.motorcycle = FixedRouter((route(Mode.MOTORCYCLE, points=road_points),))
    result = await planner.plan(Query(*POINTS, TS))
    assert result.options
    assert result.motorcycle is not None
