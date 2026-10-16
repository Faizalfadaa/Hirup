import numpy as np

from hirup_pipelines.grid import Grid, cell_id, map_grid, to_utm
from hirup_pipelines.settings import pilot_bbox
from services.exposure.geometry import Point, project_points


def test_pilot_grid_is_lattice_aligned_and_covers_the_bbox():
    grid, box = map_grid(), pilot_bbox()
    assert grid.west % 100 == 0
    assert grid.north % 100 == 0
    lon = np.array([box.min_lon, box.max_lon, box.min_lon, box.max_lon])
    lat = np.array([box.min_lat, box.min_lat, box.max_lat, box.max_lat])
    row, col = grid.locate(*to_utm(lon, lat))
    assert grid.inside(row, col).all()
    assert grid.frame()["cell_id"].is_unique


def test_cell_id_matches_the_api_convention():
    # services/api/routes/aq.py builds cell_id as f"{int(x // 100)}:{int(y // 100)}".
    point = Point(106.8227, -6.2088)
    x, y = project_points([point])
    assert str(cell_id(x, y)[0]) == f"{int(x[0] // 100)}:{int(y[0] // 100)}"
    row, col = map_grid().locate(x, y)
    frame = map_grid().frame()
    match = frame[(frame["row"] == row[0]) & (frame["col"] == col[0])]
    assert match["cell_id"].item() == str(cell_id(x, y)[0])


def test_patch_grid_centres_on_the_point_cell():
    patch = Grid.around(701_234.0, 9_312_345.0, cells=1)
    row, col = patch.locate([701_234.0], [9_312_345.0])
    assert (row[0], col[0]) == (1, 1)
    assert patch.expand(2).refine(5).shape == (35, 35)


def test_map_extent_contains_the_pilot_and_tests_can_pin_the_pilot(monkeypatch):
    from hirup_pipelines.settings import map_bbox

    pilot = pilot_bbox()
    assert map_bbox() == pilot  # conftest pins HIRUP_MAP_EXTENT=pilot
    monkeypatch.delenv("HIRUP_MAP_EXTENT")
    wide = map_bbox()
    assert wide.union(pilot) == wide  # the routing pilot lies inside the map
    assert wide != pilot
