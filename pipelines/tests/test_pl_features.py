import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from hirup_pipelines.features import dynamic
from hirup_pipelines.features.static import Layers, compute_static, feature_columns
from hirup_pipelines.grid import CRS, Grid
from hirup_pipelines.ingest.osm import OsmLayers, _polygons, junctions_of, tiles
from hirup_pipelines.ingest.rasters import tile_urls
from hirup_pipelines.settings import BBox, load_config


def layers_for(grid, roads, buildings=None, transit=None):
    margin = int(load_config()["features"]["margin_cells"])
    work = grid.expand(margin)
    fine = work.refine(10)
    cover = np.full(fine.shape, 50, dtype=np.float32)  # built-up everywhere...
    cover[:, : fine.width // 2] = 10  # ...except trees on the western half
    empty = gpd.GeoDataFrame(geometry=[], crs=CRS)
    return Layers(
        osm=OsmLayers(
            roads=roads,
            junctions=np.array([[grid.west + 550.0, grid.north - 550.0]]),
            buildings=buildings if buildings is not None else empty,
        ),
        worldcover=cover,
        ndvi=np.full(fine.shape, 0.4, dtype=np.float32),
        population=np.full(work.shape, 12_000.0, dtype=np.float32),
        transit=transit,
    )


def test_static_features_on_a_known_layout():
    grid = Grid(700_000.0, 9_310_000.0, 11, 11)
    y = grid.north - 550.0  # a trunk road through the centre row, west to east
    line = LineString([(grid.west - 2000, y), (grid.east + 2000, y)])
    roads = gpd.GeoDataFrame({"road_class": ["trunk"]}, geometry=[line], crs=CRS)
    building = gpd.GeoDataFrame(
        geometry=[box(grid.west + 500, grid.north - 600, grid.west + 600, grid.north - 500)],
        crs=CRS,
    )
    transit = gpd.GeoDataFrame(
        {"is_brt": [True], "trips_per_hour": [12.0]}, geometry=[line], crs=CRS
    )
    frame = compute_static(grid, layers_for(grid, roads, building, transit))
    frame = frame.set_index(["row", "col"])
    centre, far = frame.loc[(5, 5)], frame.loc[(0, 5)]
    # A straight road through the centre of a disk of radius r has length 2r inside it.
    for radius in (100, 300, 500):
        assert centre[f"road_trunk_{radius}m"] == pytest.approx(2 * radius, rel=0.12)
    assert far["road_trunk_300m"] == 0
    assert far["road_trunk_500m"] > 0  # 500 m away: the 500 m buffer just reaches it
    assert centre["road_primary_500m"] == 0
    assert centre["dist_major_road_m"] == pytest.approx(0, abs=20)
    assert far["dist_major_road_m"] == pytest.approx(500, abs=20)  # capped at 500
    assert centre["bldg_frac_100m"] == pytest.approx(1.0)
    assert 0 < centre["bldg_frac_300m"] < 0.1
    assert centre["bldg_count_300m"] == pytest.approx(1)
    assert centre["junction_density_300m"] == pytest.approx(1 / (np.pi * 0.09), rel=0.01)
    assert frame.loc[(5, 0), "wc_frac_tree_100m"] == 1.0
    assert frame.loc[(5, 10), "wc_frac_built_100m"] == 1.0
    assert centre["ndvi_mean_300m"] == pytest.approx(0.4, abs=1e-5)
    assert centre["pop_density"] == pytest.approx(12_000)
    assert centre["dist_brt_m"] == pytest.approx(0, abs=1)
    assert far["dist_brt_m"] == pytest.approx(500, abs=1)
    assert centre["bus_trips_per_hour"] == 12.0
    assert far["bus_trips_per_hour"] == 0.0
    assert "cell_id" not in feature_columns(frame.reset_index())


def test_patch_and_grid_agree_for_the_same_cell():
    grid = Grid(700_000.0, 9_310_000.0, 11, 11)
    roads = gpd.GeoDataFrame(
        {"road_class": ["primary"]},
        geometry=[LineString([(700_420.0, 9_300_000.0), (700_480.0, 9_320_000.0)])],
        crs=CRS,
    )
    whole = compute_static(grid, layers_for(grid, roads))
    patch = Grid.around(700_450.0, 9_309_450.0, cells=1)
    small = compute_static(patch, layers_for(patch, roads))
    cell = small.iloc[4]["cell_id"]
    expected = whole[whole["cell_id"] == cell].iloc[0]
    for name in ("road_primary_100m", "road_primary_500m", "dist_major_road_m"):
        assert small.iloc[4][name] == pytest.approx(expected[name], rel=1e-6, abs=1e-6)


def test_pbf_index_serves_layers_inside_its_area_only(tmp_path):
    import osmium

    from hirup_pipelines.ingest import osm

    path = tmp_path / "toy.osm.pbf"
    lon, lat = 106.80, -6.20
    step = 0.001
    nodes = {
        1: (lon, lat),
        2: (lon + step, lat),
        3: (lon + 2 * step, lat),
        4: (lon + step, lat + step),
        5: (lon + step, lat - step),
        6: (lon + step, lat + 2 * step),
        10: (lon, lat + step),
        11: (lon, lat + 1.2 * step),
        12: (lon + 0.2 * step, lat + 1.2 * step),
        13: (lon + 0.2 * step, lat + step),
        20: (100.0, 0.0),  # Sumatra: far outside the index area
        21: (100.001, 0.0),
    }
    with osmium.SimpleWriter(str(path)) as writer:
        for node_id, (x, y) in nodes.items():
            writer.add_node(osmium.osm.mutable.Node(id=node_id, location=(x, y)))
        ways = [
            (1, [1, 2, 3], {"highway": "primary"}),
            (2, [5, 2, 4], {"highway": "residential"}),  # crosses way 1 at node 2
            (3, [4, 6], {"highway": "footway"}),  # not a road class
            (4, [10, 11, 12, 13, 10], {"building": "yes"}),
            (5, [20, 21], {"highway": "trunk"}),
        ]
        for way_id, refs, tags in ways:
            writer.add_way(osmium.osm.mutable.Way(id=way_id, nodes=refs, tags=tags))

    meta = osm.build_index(path)
    assert (meta["roads"], meta["buildings"]) == (2, 1)
    layers = osm.fetch_layers(BBox(lat - 0.005, lat + 0.005, lon - 0.005, lon + 0.005))
    assert sorted(layers.roads["road_class"]) == ["minor", "primary"]
    assert len(layers.buildings) == 1
    assert len(layers.junctions) == 1  # node 2, where four segments meet
    assert layers.roads.crs.to_epsg() == 32748
    assert osm.from_index(BBox(-1.0, 1.0, 99.0, 101.0)) is None  # outside: Overpass is used


def test_osm_helpers():
    square = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    way = {"type": "way", "id": 1, "geometry": [{"lon": x, "lat": y} for x, y in square]}
    relation = {
        "type": "relation",
        "id": 2,
        "members": [
            {"type": "way", "role": "outer", "geometry": way["geometry"][:3]},
            {"type": "way", "role": "outer", "geometry": way["geometry"][2:]},
        ],
    }
    polygons = _polygons([way, relation])
    assert [round(geometry.area, 6) for _, geometry in polygons] == [1.0, 1.0]
    cross = [[(0, 0), (1, 0), (2, 0)], [(1, -1), (1, 0), (1, 1)], [(5, 5), (6, 6)]]
    assert junctions_of(cross) == [(1, 0)]
    assert len(tiles(BBox(-6.30, -6.13, 106.76, 106.85), 0.05)) == 4 * 2


def test_worldcover_tile_names():
    area = BBox(-6.30, -6.13, 106.76, 106.85)
    assert tile_urls("{tile}", area, 3) == ["S09E105"]
    assert tile_urls("{lat}/{tile}", area, 1) == ["S07/S07E106"]


def test_idw_is_leave_one_out_and_ignores_missing_sources():
    xy = np.array([[0.0, 0.0], [1000.0, 0.0], [0.0, 1000.0]])
    weights = dynamic.idw_weights(xy, xy)
    assert np.diag(weights).tolist() == [0, 0, 0]
    values = np.array([[10.0, 20.0, 30.0], [10.0, np.nan, 30.0], [np.nan, np.nan, np.nan]])
    out, count = dynamic.idw(values, weights)
    assert out[0, 0] == pytest.approx(25.0)  # equidistant neighbours 20 and 30
    assert out[1, 0] == pytest.approx(30.0)  # only station 2 reports
    assert count[1].tolist() == [1, 2, 1]
    assert np.isnan(out[2]).all()
    block = dynamic.idw_block(values, weights)
    assert block["idw_pm25_lag1"][1, 0] == pytest.approx(25.0)
    assert np.isnan(block["idw_pm25_lag1"][0]).all()
    assert dynamic.nearest_source_distance(xy, xy).tolist() == [1000, 1000, 1000]


def test_time_features_use_jakarta_time_and_the_configured_calendar():
    hours = pd.DatetimeIndex(["2026-08-16T17:00Z", "2026-10-13T00:00Z"])  # 17 Aug 00:00 WIB
    features = dynamic.time_features(hours)
    assert features["is_holiday"].tolist() == [1.0, 0.0]
    assert features["hour_sin"].iloc[0] == pytest.approx(0.0)
    assert features["hour_cos"].iloc[1] == pytest.approx(np.cos(2 * np.pi * 7 / 24))
    assert features["is_weekend"].tolist() == [0.0, 0.0]
