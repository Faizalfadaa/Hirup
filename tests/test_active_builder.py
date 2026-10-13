from pathlib import Path

import osmnx as ox
import pytest

from services.exposure.geometry import BoundingBox
from services.routing.active_params import load_active_params
from services.routing.build_active_graph import allowed_directions, build_graph


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"highway": "residential"}, (True, True, True, True)),
        ({"highway": "residential", "oneway": "yes"}, (True, True, True, False)),
        ({"highway": "residential", "oneway": "-1"}, (True, True, True, False)),
        (
            {"highway": "residential", "oneway": "yes", "oneway:bicycle": "no"},
            (True, True, True, True),
        ),
        (
            {"highway": "residential", "oneway": "yes", "cycleway": "opposite_lane"},
            (True, True, True, True),
        ),
        (
            {"highway": "residential", "oneway": "-1", "oneway:bicycle": "yes"},
            (True, True, False, True),
        ),
        ({"highway": "residential", "access": "private"}, (False, False, False, False)),
        (
            {"highway": "residential", "access": "private", "foot": "yes"},
            (True, True, False, False),
        ),
        ({"highway": "steps"}, (True, True, False, False)),
        ({"highway": "footway", "bicycle": "yes"}, (True, True, True, True)),
        ({"highway": "motorway", "bicycle": "yes"}, (False, False, False, False)),
        ({"highway": "construction"}, (False, False, False, False)),
    ],
)
def test_osm_access_and_directions(tags: dict[str, str], expected: tuple[bool, ...]) -> None:
    assert allowed_directions(tags) == expected


def test_offline_osmnx_conversion_preserves_reverse_oneway(tmp_path: Path) -> None:
    xml = tmp_path / "tiny.osm"
    xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
<node id="1" lat="-6.2" lon="106.8"/>
<node id="2" lat="-6.2" lon="106.801"/>
<node id="3" lat="-6.2" lon="106.802"><tag k="access" v="private"/></node>
<way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/>
<tag k="oneway" v="-1"/></way>
<way id="11"><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/></way>
</osm>""")
    before = (
        ox.settings.all_oneway,
        list(ox.settings.useful_tags_way),
        list(ox.settings.useful_tags_node),
    )
    graph = build_graph(
        xml,
        BoundingBox(-6.3, -6.13, 106.76, 106.85),
        load_active_params(),
        source_quality="synthetic",
    )
    assert len(graph.nodes) == 2  # private endpoint excluded
    assert len(graph.edges) == 2
    bike_edges = [e for e in graph.edges if e.bike]
    assert len(bike_edges) == 1
    assert bike_edges[0].geometry[0].lon == 106.801
    assert bike_edges[0].geometry[-1].lon == 106.8
    assert graph.edges[0].cells == tuple(reversed(graph.edges[1].cells))
    assert graph.data_quality == "synthetic"
    assert (
        ox.settings.all_oneway,
        ox.settings.useful_tags_way,
        ox.settings.useful_tags_node,
    ) == before
