from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from services.exposure.aq_provider import AQUnavailableError, Pm25Samples
from services.exposure.geometry import BoundingBox, Point, hour_key, unproject
from services.routing.active_graph import GraphData, RoadEdge, load_graph, save_graph
from services.routing.active_params import load_active_params
from services.routing.active_router import ActiveRouter, NoActiveRouteError

TS = datetime.fromisoformat("2026-10-14T08:00:00+07:00")
BOUNDS = BoundingBox(-6.3, -6.13, 106.76, 106.85)


class FakeAQ:
    def __init__(self) -> None:
        self.calls = 0
        self.bad_count = False
        self.flip = False

    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
        self.calls += 1
        # Edge cells below use x=699050 (dirty) versus x=699150 (clean).
        from services.exposure.geometry import project_points

        x, _ = project_points(points)
        values = np.where(x < 699100, 80.0, 20.0)
        if self.flip:
            values = 100 - values
        if self.bad_count:
            values = np.array([], dtype=np.float64)
        return Pm25Samples(values - 5, values, values + 5, hour_key(ts), "synthetic", "test")


def graph(clean_length: float = 240, *, highway: str = "residential") -> GraphData:
    nodes = tuple(unproject(x, 9313900) for x in (699000, 699100, 699200, 699300))
    edges = (
        RoadEdge(0, 1, 100, (nodes[0], nodes[1]), highway, True, True, ((6990, 93139),)),
        RoadEdge(1, 3, 100, (nodes[1], nodes[3]), highway, True, True, ((6990, 93139),)),
        RoadEdge(
            0,
            2,
            clean_length / 2,
            (nodes[0], nodes[2]),
            "residential",
            True,
            True,
            ((6991, 93139),),
        ),
        RoadEdge(
            2,
            3,
            clean_length / 2,
            (nodes[2], nodes[3]),
            "residential",
            True,
            True,
            ((6991, 93139),),
        ),
    )
    return GraphData(nodes, edges, BOUNDS, 100, 25, "synthetic")


def router_for(data: GraphData, aq: FakeAQ | None = None) -> ActiveRouter:
    router = ActiveRouter(data, load_active_params(), aq or FakeAQ(), trunk_penalty_factor=2)
    router.refresh_aq(TS, 40)
    return router


def test_hand_computed_pollution_weight_and_duplicate_paths() -> None:
    data = graph()
    router = router_for(data)
    routes = router.plan(data.nodes[0], data.nodes[3], TS)
    assert len(routes) == 2
    # lambda 0: costs 200/1.2 and 240/1.2. lambda .5: dirty 400/1.2, clean 300/1.2.
    assert routes[0].edge_indices == (0, 1)
    assert routes[0].lambdas == (0,)
    assert routes[0].duration_s == pytest.approx(200 / 1.2)
    assert routes[1].edge_indices == (2, 3)
    assert routes[1].lambdas == (0.5, 1.5, 3)
    assert routes[1].data_quality == "synthetic"
    bike = router.plan(data.nodes[0], data.nodes[3], TS, "BICYCLE")
    assert bike[0].duration_s == pytest.approx(200 / 4.2)


def test_fractional_detour_rejected() -> None:
    data = graph(301)
    assert len(router_for(data).plan(data.nodes[0], data.nodes[3], TS)) == 1


def test_absolute_detour_rejected_independently() -> None:
    data = graph(2400)
    scaled = replace(
        data,
        edges=tuple(
            replace(e, length_m=e.length_m * 10) if i < 2 else e for i, e in enumerate(data.edges)
        ),
    )
    # 400 m = 333 s: retained at <50% and <480 s.
    assert len(router_for(scaled).plan(scaled.nodes[0], scaled.nodes[3], TS)) == 2
    long = replace(
        scaled,
        edges=tuple(replace(e, length_m=1400) if i >= 2 else e for i, e in enumerate(scaled.edges)),
    )
    # 800 m = 667 s, still <50%, rejected by the 480 s limit.
    assert len(router_for(long).plan(long.nodes[0], long.nodes[3], TS)) == 1


def test_bicycle_forbids_motorway_and_penalizes_trunk() -> None:
    for highway in ("motorway", "trunk"):
        data = graph(highway=highway)
        route = router_for(data).plan(data.nodes[0], data.nodes[3], TS, "BICYCLE")[0]
        assert route.edge_indices == (2, 3)
        assert route.duration_s == pytest.approx(240 / 4.2)


def test_direction_is_respected() -> None:
    data = graph()
    with pytest.raises(NoActiveRouteError, match="connected"):
        router_for(data).plan(data.nodes[3], data.nodes[0], TS)


def test_hour_refresh_and_cached_cell_sampling() -> None:
    data, aq = graph(), FakeAQ()
    router = router_for(data, aq)
    assert aq.calls == 1
    router.plan(data.nodes[0], data.nodes[3], TS)
    assert aq.calls == 3  # one refresh + two unique final polylines, not every edge/lambda
    with pytest.raises(AQUnavailableError, match="Refresh"):
        router.plan(data.nodes[0], data.nodes[3], TS + timedelta(hours=1))
    aq.bad_count = True
    with pytest.raises(AQUnavailableError, match="count"):
        router.refresh_aq(TS + timedelta(hours=1), 40)
    # Atomic failed refresh leaves the previous hour available.
    aq.bad_count = False
    assert router.plan(data.nodes[0], data.nodes[3], TS)


def test_bad_route_sample_count_rejected() -> None:
    data, aq = graph(), FakeAQ()
    router = router_for(data, aq)
    aq.bad_count = True
    with pytest.raises(AQUnavailableError, match="count"):
        router.plan(data.nodes[0], data.nodes[3], TS)


def test_refresh_replaces_weighted_graphs_when_aq_changes() -> None:
    data, aq = graph(), FakeAQ()
    router = router_for(data, aq)
    assert len(router.plan(data.nodes[0], data.nodes[3], TS)) == 2
    aq.flip = True
    router.refresh_aq(TS, 40)
    routes = router.plan(data.nodes[0], data.nodes[3], TS)
    assert len(routes) == 1
    assert routes[0].edge_indices == (0, 1)
    assert routes[0].lambdas == (0, 0.5, 1.5, 3)


def test_zero_trip_and_same_snapped_node() -> None:
    data = graph()
    router = router_for(data)
    route = router.plan(data.nodes[0], data.nodes[0], TS)[0]
    assert route.duration_s == 0
    assert route.distance_m == 0
    assert route.points == (data.nodes[0],)
    nearby = unproject(699001, 9313900)
    assert router.plan(data.nodes[0], nearby, TS)[0].distance_m == pytest.approx(1, abs=0.001)


def test_graph_cache_round_trip(tmp_path: Path) -> None:
    data = graph()
    path = tmp_path / "graph.json.gz"
    save_graph(data, path)
    assert load_graph(path) == data


def test_parallel_edges_choose_correct_minimum_cost() -> None:
    data = graph()
    slow_parallel = replace(data.edges[0], length_m=150)
    data = replace(data, edges=(*data.edges, slow_parallel))
    assert router_for(data).plan(data.nodes[0], data.nodes[3], TS)[0].edge_indices == (0, 1)


def test_connectors_mark_real_graph_and_aq_as_approximated() -> None:
    class RealAQ(FakeAQ):
        def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
            return replace(super().sample(points, ts), data_quality="real")

    data = replace(graph(), data_quality="real")
    router = router_for(data, RealAQ())
    assert router.plan(data.nodes[0], data.nodes[3], TS)[0].data_quality == "real"
    assert (
        router.plan(unproject(699001, 9313900), data.nodes[3], TS)[0].data_quality == "approximated"
    )


def test_baseline_geometry_does_not_read_aq_or_use_stale_weights() -> None:
    data, aq = graph(), FakeAQ()
    router = ActiveRouter(data, load_active_params(), aq, trunk_penalty_factor=2)
    points, distance, duration = router.base_path(data.nodes[0], data.nodes[3])
    assert points[0] == data.nodes[0]
    assert points[-1] == data.nodes[3]
    assert distance == 200
    assert duration == pytest.approx(200 / 1.2)
    assert aq.calls == 0
    with pytest.raises(NoActiveRouteError):
        router.base_path(data.nodes[3], data.nodes[0])
