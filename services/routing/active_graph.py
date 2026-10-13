"""Immutable road inputs and a reusable 100 m projected edge-to-cell index."""

import gzip
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from services.exposure.aq_provider import DataQuality
from services.exposure.geometry import (
    BoundingBox,
    Point,
    project_points,
    sample_polyline,
    unproject,
)

Cell = tuple[int, int]


@dataclass(frozen=True, slots=True)
class RoadEdge:
    source: int
    target: int
    length_m: float
    geometry: tuple[Point, ...]
    highway: str
    walk: bool
    bike: bool
    cells: tuple[Cell, ...]


@dataclass(frozen=True, slots=True)
class GraphData:
    nodes: tuple[Point, ...]
    edges: tuple[RoadEdge, ...]
    bounds: BoundingBox
    grid_size_m: float
    sample_spacing_m: float
    data_quality: DataQuality = "real"

    def __post_init__(self) -> None:
        if self.data_quality not in {"real", "approximated", "synthetic"}:
            raise ValueError("Invalid graph data quality")
        if (
            not math.isfinite(self.grid_size_m)
            or self.grid_size_m <= 0
            or not math.isfinite(self.sample_spacing_m)
            or self.sample_spacing_m <= 0
        ):
            raise ValueError("Graph grid and sample spacing must be positive")
        if any(not self.bounds.contains(node) for node in self.nodes):
            raise ValueError("Graph node is outside the pilot bbox")
        for edge in self.edges:
            if not (0 <= edge.source < len(self.nodes) and 0 <= edge.target < len(self.nodes)):
                raise ValueError("Graph edge references an unknown node")
            if not math.isfinite(edge.length_m) or edge.length_m <= 0:
                raise ValueError("Graph edge length must be positive")
            if len(edge.geometry) < 2 or not edge.cells:
                raise ValueError("Graph edges require geometry and cached grid cells")
            if (
                edge.geometry[0] != self.nodes[edge.source]
                or edge.geometry[-1] != self.nodes[edge.target]
            ):
                raise ValueError("Graph edge geometry does not match its directed endpoints")
            if any(not self.bounds.contains(point) for point in edge.geometry):
                raise ValueError("Graph geometry leaves the pilot bbox")

    def cell_point(self, cell: Cell) -> Point:
        # Model grids may end inside a cell: keep the representative point in area.
        return self.bounds.clamp(
            unproject((cell[0] + 0.5) * self.grid_size_m, (cell[1] + 0.5) * self.grid_size_m)
        )


def edge_cells(
    geometry: tuple[Point, ...], grid_size_m: float, spacing_m: float
) -> tuple[Cell, ...]:
    if not math.isfinite(grid_size_m) or grid_size_m <= 0:
        raise ValueError("Grid size must be positive")
    x, y = project_points(sample_polyline(geometry, spacing_m))
    return tuple(
        dict.fromkeys(
            (math.floor(a / grid_size_m), math.floor(b / grid_size_m))
            for a, b in zip(x, y, strict=True)
        )
    )


def save_graph(graph: GraphData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "version": 1,
        "nodes": [asdict(point) for point in graph.nodes],
        "edges": [asdict(edge) for edge in graph.edges],
        "bounds": asdict(graph.bounds),
        "grid_size_m": graph.grid_size_m,
        "sample_spacing_m": graph.sample_spacing_m,
        "data_quality": graph.data_quality,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        json.dump(document, stream, separators=(",", ":"), allow_nan=False)
    temporary.replace(path)


def load_graph(path: Path) -> GraphData:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        document = json.load(stream)
    if document.get("version") != 1:
        raise ValueError("Unsupported active graph cache version")
    nodes = tuple(Point(**point) for point in document["nodes"])
    edges = tuple(
        RoadEdge(
            edge["source"],
            edge["target"],
            edge["length_m"],
            tuple(Point(**point) for point in edge["geometry"]),
            edge["highway"],
            edge["walk"],
            edge["bike"],
            tuple((cell[0], cell[1]) for cell in edge["cells"]),
        )
        for edge in document["edges"]
    )
    return GraphData(
        nodes,
        edges,
        BoundingBox(**document["bounds"]),
        document["grid_size_m"],
        document["sample_spacing_m"],
        document["data_quality"],
    )
