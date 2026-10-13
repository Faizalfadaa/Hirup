from dataclasses import replace
from datetime import timedelta

from services.exposure.aq_provider import AQUnavailableError
from services.exposure.engine import Mode, Quantiles
from services.exposure.geometry import Point, hour_key
from services.routing.active_params import load_active_params
from services.routing.active_router import ActiveRoute
from services.routing.models import Query, RouteLeg
from tests.test_plan_api import POINTS, TS, runtime


class ActiveSearch:
    def __init__(self, unavailable: bool = False) -> None:
        self.params = load_active_params()
        self.calls = 0
        self.unavailable = unavailable

    def plan(self, a, b, clock, mode):
        self.calls += 1
        if self.unavailable:
            raise AQUnavailableError("Unit test unprepared hour")
        return (
            ActiveRoute(
                mode,
                (a, Point(106.8005, -6.2004), b),
                100,
                90,
                Quantiles(10, 20, 30),
                "synthetic",
                (1.5,),
                (),
                hour_key(clock),
            ),
        )


def candidate():
    configured = runtime()
    bus = configured.planner.transit.items[0]
    return replace(bus, legs=(RouteLeg(Mode.WALK, 100, 100, POINTS), *bus.legs))


def test_identical_active_legs_share_search_but_keep_individual_detour_limits() -> None:
    configured = runtime()
    router = ActiveSearch()
    configured.planner.active_router = router
    normal = candidate()
    short = replace(normal, legs=(replace(normal.legs[0], duration_s=10), *normal.legs[1:]))
    results = configured.planner._optimize_many((normal, normal, short), Query(*POINTS, TS))
    assert router.calls == 1
    assert len(results) == 2  # The short leg still fails its own 50% detour bound.
    assert all(result.legs[0].duration_s == 90 for result in results)
    configured.planner._optimize_many((normal,), Query(*POINTS, TS))
    assert router.calls == 2  # No coordinates/search memo retained across requests.


def test_different_hours_and_modes_have_separate_searches() -> None:
    configured = runtime()
    router = ActiveSearch()
    configured.planner.active_router = router
    normal = candidate()
    later = replace(normal, depart_at=TS + timedelta(hours=1))
    bike = replace(normal, legs=(replace(normal.legs[0], mode=Mode.BICYCLE), *normal.legs[1:]))
    configured.planner._optimize_many((normal, later, bike), Query(*POINTS, TS))
    assert router.calls == 3


def test_unavailable_active_search_is_not_repeated_for_identical_legs() -> None:
    configured = runtime()
    router = ActiveSearch(unavailable=True)
    configured.planner.active_router = router
    normal = candidate()
    results = configured.planner._optimize_many((normal, normal), Query(*POINTS, TS))
    assert results == []
    assert router.calls == 1
