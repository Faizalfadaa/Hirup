"""Offline OSMnx graph conversion; no network or graph construction per request."""

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

import osmnx as ox

from services.exposure.aq_provider import DataQuality
from services.exposure.geometry import BoundingBox, Point, distance_m
from services.routing.active_graph import GraphData, RoadEdge, edge_cells, save_graph
from services.routing.active_params import ActiveParams, load_active_params

ROOT = Path(__file__).resolve().parents[2]
DENIED = {"no", "private"}
ALLOWED = {"yes", "designated", "permissive"}
REVERSE = {"-1", "reverse", "T"}
ONEWAY = {"yes", "true", "1", "-1", "reverse", "T", "F"}


def load_bounds(path: Path = ROOT / "contracts/golden_od.json") -> BoundingBox:
    return BoundingBox(**json.loads(path.read_text(encoding="utf-8"))["bbox"])


def _directions(value: str, car_reversed: bool) -> tuple[bool, bool]:
    if value not in ONEWAY:
        return True, True
    reverse = (value in REVERSE) != car_reversed
    return not reverse, reverse


def allowed_directions(tags: Mapping[str, object]) -> tuple[bool, bool, bool, bool]:
    """Directions are relative to OSMnx's edge, including its reversed OSM ways."""
    highway = str(tags.get("highway", ""))
    if highway in {"construction", "proposed", "motorway", "motorway_link", "raceway"}:
        return False, False, False, False
    access = str(tags.get("access", ""))
    foot, bicycle = str(tags.get("foot", "")), str(tags.get("bicycle", ""))
    walk = (
        foot not in DENIED and foot != "use_sidepath" and (access not in DENIED or foot in ALLOWED)
    )
    bike = (
        bicycle not in DENIED
        and bicycle != "use_sidepath"
        and (access not in DENIED or bicycle in ALLOWED)
    )
    if highway in {"steps", "footway", "pedestrian", "corridor"} and bicycle not in ALLOWED:
        bike = False
    if str(tags.get("motorroad", "")) == "yes" and bicycle not in ALLOWED:
        bike = False
    car_oneway = str(tags.get("oneway", ""))
    car_reversed = car_oneway in REVERSE
    bike_oneway = str(tags.get("oneway:bicycle", car_oneway))
    if "oneway:bicycle" not in tags and str(tags.get("cycleway", "")).startswith("opposite"):
        bike_oneway = "no"
    if not bike_oneway and tags.get("junction") == "roundabout":
        bike_oneway = "yes"
    bike_forward, bike_reverse = _directions(bike_oneway, car_reversed)
    walk_forward, walk_reverse = _directions(str(tags.get("oneway:foot", "")), car_reversed)
    return (
        walk and walk_forward,
        walk and walk_reverse,
        bike and bike_forward,
        bike and bike_reverse,
    )


def _node_allowed(tags: Mapping[str, object], mode: str) -> bool:
    specific = str(tags.get(mode, ""))
    if specific in DENIED:
        return False
    if specific in ALLOWED:
        return True
    return str(tags.get("access", "")) not in DENIED and str(tags.get("barrier", "")) not in {
        "wall",
        "fence",
        "block",
    }


def build_graph(
    xml_path: Path,
    bounds: BoundingBox,
    params: ActiveParams,
    *,
    source_quality: DataQuality = "real",
) -> GraphData:
    original_oneway = ox.settings.all_oneway
    original_tags = ox.settings.useful_tags_way
    original_node_tags = ox.settings.useful_tags_node
    try:
        ox.settings.all_oneway = True
        ox.settings.useful_tags_way = list(
            dict.fromkeys(
                (
                    *original_tags,
                    "foot",
                    "bicycle",
                    "access",
                    "oneway:foot",
                    "oneway:bicycle",
                    "cycleway",
                    "motorroad",
                )
            )
        )
        ox.settings.useful_tags_node = list(
            dict.fromkeys((*original_node_tags, "access", "foot", "bicycle"))
        )
        network = ox.graph_from_xml(xml_path, simplify=False, retain_all=True)
    finally:
        ox.settings.all_oneway = original_oneway
        ox.settings.useful_tags_way = original_tags
        ox.settings.useful_tags_node = original_node_tags
    nodes: list[Point] = []
    indices: dict[int, int] = {}
    edges: list[RoadEdge] = []

    def index(osm_id: int, point: Point) -> int:
        if osm_id not in indices:
            indices[osm_id] = len(nodes)
            nodes.append(point)
        return indices[osm_id]

    for u, v, tags in network.edges(data=True):
        a = Point(float(network.nodes[u]["x"]), float(network.nodes[u]["y"]))
        b = Point(float(network.nodes[v]["x"]), float(network.nodes[v]["y"]))
        if not bounds.contains(a) or not bounds.contains(b) or a == b:
            continue
        walk_forward, walk_reverse, bike_forward, bike_reverse = allowed_directions(tags)
        walk_nodes = _node_allowed(network.nodes[u], "foot") and _node_allowed(
            network.nodes[v], "foot"
        )
        bike_nodes = _node_allowed(network.nodes[u], "bicycle") and _node_allowed(
            network.nodes[v], "bicycle"
        )
        walk_forward, walk_reverse = walk_forward and walk_nodes, walk_reverse and walk_nodes
        bike_forward, bike_reverse = bike_forward and bike_nodes, bike_reverse and bike_nodes
        if not any((walk_forward, walk_reverse, bike_forward, bike_reverse)):
            continue
        source, target = index(int(u), a), index(int(v), b)
        geometry = (a, b)
        cells = edge_cells(geometry, 100, params.sample_spacing_m)
        length = distance_m(a, b)
        highway = str(tags.get("highway", ""))
        if walk_forward or bike_forward:
            edges.append(
                RoadEdge(
                    source, target, length, geometry, highway, walk_forward, bike_forward, cells
                )
            )
        if walk_reverse or bike_reverse:
            edges.append(
                RoadEdge(
                    target,
                    source,
                    length,
                    (b, a),
                    highway,
                    walk_reverse,
                    bike_reverse,
                    tuple(reversed(cells)),
                )
            )
    if not edges:
        raise ValueError("No public active edges inside the pilot bbox")
    return GraphData(
        tuple(nodes), tuple(edges), bounds, 100, params.sample_spacing_m, source_quality
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, default=ROOT / "data/graphs/active.osm")
    parser.add_argument("--output", type=Path, default=ROOT / "data/graphs/active.json.gz")
    args = parser.parse_args()
    graph = build_graph(args.xml, load_bounds(), load_active_params())
    save_graph(graph, args.output)
    print(
        json.dumps(
            {
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "grid_cells": len({cell for edge in graph.edges for cell in edge.cells}),
                "data_quality": graph.data_quality,
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
