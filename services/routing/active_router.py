"""Exposure-weighted walk/bike paths over a graph loaded once at startup."""

import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from itertools import pairwise
from operator import itemgetter
from typing import Any, Literal

import numpy as np
import rustworkx as rx

from services.exposure.aq_provider import (
    AQProvider,
    AQUnavailableError,
    DataQuality,
    OutOfServiceAreaError,
    Pm25Samples,
)
from services.exposure.engine import Quantiles
from services.exposure.geometry import (
    FloatArray,
    Point,
    distance_m,
    hour_key,
    project_points,
    sample_polyline,
)
from services.routing.active_graph import GraphData
from services.routing.active_params import ActiveParams

ActiveMode = Literal["WALK", "BICYCLE"]


class NoActiveRouteError(ValueError):
    """No connected active route; orchestration may retain other mode candidates."""


@dataclass(frozen=True, slots=True)
class ActiveRoute:
    mode: ActiveMode
    points: tuple[Point, ...]
    distance_m: float
    duration_s: float
    mean_pm25: Quantiles
    data_quality: DataQuality
    lambdas: tuple[float, ...]
    edge_indices: tuple[int, ...]
    valid_hour: datetime


@dataclass(frozen=True)
class _Snapshot:
    valid_hour: datetime
    reference_pm25: float
    concentrations: np.ndarray[Any, np.dtype[np.float64]]
    cell_samples: Pm25Samples
    networks: dict[tuple[ActiveMode, float], Any]
    costs: dict[tuple[ActiveMode, float], FloatArray]


class ActiveRouter:
    """The caller supplies the sourced city median C_ref on hourly refresh.

    A trunk cost factor is a route preference, not a scientific exposure factor.
    It is explicit and mandatory while the frozen contract has no numeric value.
    No origin/destination or request path is cached after responding.
    """

    def __init__(
        self, graph: GraphData, params: ActiveParams, aq: AQProvider, *, trunk_penalty_factor: float
    ) -> None:
        if not math.isfinite(trunk_penalty_factor) or trunk_penalty_factor <= 1:
            raise ValueError("The bicycle trunk preference must have a factor greater than one")
        if not math.isclose(graph.sample_spacing_m, params.sample_spacing_m):
            raise ValueError("Graph sample spacing does not match the contract")
        self.graph, self.params, self.aq = graph, params, aq
        self.trunk_penalty_factor = trunk_penalty_factor
        self._lock = threading.RLock()
        self._snapshot: _Snapshot | None = None
        self._cells = tuple(sorted({cell for edge in graph.edges for cell in edge.cells}))
        self._cell_indices = {cell: index for index, cell in enumerate(self._cells)}
        self._networks: dict[ActiveMode, Any] = {}
        self._network_edges: dict[ActiveMode, tuple[int, ...]] = {}
        self._node_ids: dict[ActiveMode, tuple[int, ...]] = {}
        self._positions: dict[ActiveMode, tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]] = {}
        self._cost_bases: dict[ActiveMode, FloatArray] = {}
        modes: tuple[ActiveMode, ...] = ("WALK", "BICYCLE")
        for active_mode in modes:
            speed = params.walk_speed_m_s if active_mode == "WALK" else params.bike_speed_m_s
            base = np.asarray(
                [
                    edge.length_m
                    / speed
                    * (
                        trunk_penalty_factor
                        if active_mode == "BICYCLE" and edge.highway in {"trunk", "trunk_link"}
                        else 1.0
                    )
                    for edge in graph.edges
                ],
                dtype=np.float64,
            )
            base.setflags(write=False)
            self._cost_bases[active_mode] = base
            network = rx.PyDiGraph(multigraph=True)
            node_ids = tuple(
                sorted(
                    {
                        node
                        for edge in graph.edges
                        if self._allowed(edge.highway, edge.walk, edge.bike, active_mode)
                        for node in (edge.source, edge.target)
                    }
                )
            )
            self._node_ids[active_mode] = node_ids
            mapping = {node: index for index, node in enumerate(node_ids)}
            network.add_nodes_from(node_ids)
            network_edges: list[int] = []
            for index, edge in enumerate(graph.edges):
                if self._allowed(edge.highway, edge.walk, edge.bike, active_mode):
                    network.add_edge(mapping[edge.source], mapping[edge.target], index)
                    network_edges.append(index)
            self._networks[active_mode] = network
            self._network_edges[active_mode] = tuple(network_edges)
            self._positions[active_mode] = project_points(
                [graph.nodes[index] for index in node_ids]
            )

    @staticmethod
    def _allowed(highway: str, walk: bool, bike: bool, mode: ActiveMode) -> bool:
        if mode == "BICYCLE":
            return bike and highway not in {"motorway", "motorway_link"}
        return walk

    def refresh_aq(self, ts: datetime, reference_pm25: float) -> None:
        if not math.isfinite(reference_pm25) or reference_pm25 <= 0:
            raise ValueError("A positive sourced reference PM2.5 median is required")
        samples = self.aq.sample([self.graph.cell_point(cell) for cell in self._cells], ts)
        if len(samples.p50) != len(self._cells) or samples.valid_hour != hour_key(ts):
            raise AQUnavailableError(
                "AQ sample count or hour differs from the requested graph refresh"
            )
        concentrations = np.asarray(
            [
                np.mean(samples.p50[[self._cell_indices[cell] for cell in edge.cells]])
                for edge in self.graph.edges
            ],
            dtype=np.float64,
        )
        concentrations.setflags(write=False)
        networks: dict[tuple[ActiveMode, float], Any] = {}
        cost_arrays: dict[tuple[ActiveMode, float], FloatArray] = {}
        # Compute immutable weighted graphs hourly. A builtin float callback avoids
        # a Python/numpy lookup on every relaxed edge during each Dijkstra search.
        for mode, base_network in self._networks.items():
            for weight in self.params.lambdas:
                costs = self._cost_bases[mode] * (1 + weight * concentrations / reference_pm25)
                costs.setflags(write=False)
                network = base_network.copy()
                for local_index, edge_index in enumerate(self._network_edges[mode]):
                    network.update_edge_by_index(local_index, float(costs[edge_index]))
                networks[mode, weight] = network
                cost_arrays[mode, weight] = costs
        snapshot = _Snapshot(
            hour_key(ts), reference_pm25, concentrations, samples, networks, cost_arrays
        )
        with self._lock:
            self._snapshot = snapshot

    def _nearest(self, point: Point, mode: ActiveMode) -> int:
        if not self._node_ids[mode]:
            raise NoActiveRouteError("No eligible nodes for the requested mode")
        x, y = project_points([point])
        nx, ny = self._positions[mode]
        return int(np.argmin((nx - x[0]) ** 2 + (ny - y[0]) ** 2))

    def plan(
        self, origin: Point, destination: Point, ts: datetime, mode: ActiveMode = "WALK"
    ) -> tuple[ActiveRoute, ...]:
        if mode not in {"WALK", "BICYCLE"}:
            raise ValueError("Active mode must be WALK or BICYCLE")
        if not self.graph.bounds.contains(origin) or not self.graph.bounds.contains(destination):
            raise OutOfServiceAreaError("Origin or destination is outside the pilot service area")
        with self._lock:
            snapshot = self._snapshot
        if snapshot is None or snapshot.valid_hour != hour_key(ts):
            raise AQUnavailableError("Refresh active graph AQ for this hour before routing")
        start, end = self._nearest(origin, mode), self._nearest(destination, mode)
        base_network = self._networks[mode]
        speed = self.params.walk_speed_m_s if mode == "WALK" else self.params.bike_speed_m_s
        routes: dict[tuple[int, ...], ActiveRoute] = {}
        baseline_duration: float | None = None
        for weight in sorted(self.params.lambdas):
            network = snapshot.networks[mode, weight]
            costs = snapshot.costs[mode, weight]
            paths = (
                {end: [start]}
                if start == end
                else rx.dijkstra_shortest_paths(network, start, target=end, weight_fn=float)
            )
            if end not in paths:
                if weight == 0:
                    raise NoActiveRouteError("No connected path for the requested active mode")
                continue
            node_path: Sequence[int] = paths[end]
            edges = tuple(
                min(
                    (
                        (float(costs[index]), index)
                        for index in base_network.get_all_edge_data(a, b)
                    ),
                    key=itemgetter(0),
                )[1]
                for a, b in pairwise(node_path)
            )
            points: list[Point] = [origin]
            start_point = self.graph.nodes[self._node_ids[mode][start]]
            if points[-1] != start_point:
                points.append(start_point)
            for edge_index in edges:
                points.extend(self.graph.edges[edge_index].geometry[1:])
            if points[-1] != destination:
                points.append(destination)
            connectors = distance_m(origin, start_point) + distance_m(
                self.graph.nodes[self._node_ids[mode][end]], destination
            )
            if origin == destination:
                points, connectors = [origin], 0.0
            length = sum(self.graph.edges[index].length_m for index in edges) + connectors
            duration = length / speed
            if weight == 0:
                baseline_duration = duration
            elif baseline_duration is not None and (
                duration > baseline_duration * (1 + self.params.max_detour_frac)
                or duration > baseline_duration + self.params.max_detour_s
            ):
                continue
            existing = routes.get(edges)
            if existing is not None:
                routes[edges] = replace(existing, lambdas=(*existing.lambdas, weight))
                continue
            sample_points = sample_polyline(points, self.params.sample_spacing_m)
            sampled = self.aq.sample(sample_points, ts)
            if len(sampled.p50) != len(sample_points) or sampled.valid_hour != hour_key(ts):
                raise AQUnavailableError("AQ sample count or hour differs from the requested route")
            qualities = {
                sampled.data_quality,
                snapshot.cell_samples.data_quality,
                self.graph.data_quality,
            }
            if connectors > 1e-6:
                qualities.add("approximated")
            quality: DataQuality = (
                "synthetic"
                if "synthetic" in qualities
                else ("approximated" if "approximated" in qualities else "real")
            )
            routes[edges] = ActiveRoute(
                mode,
                tuple(points),
                length,
                duration,
                sampled.mean(),
                quality,
                (weight,),
                edges,
                snapshot.valid_hour,
            )
        return tuple(routes.values())
