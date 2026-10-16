"""Seeded toy data for unit tests only. Never used for model metrics or reports (SPEC 10.4)."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from hirup_ml.config import load_config
from hirup_pipelines import paths, store
from hirup_pipelines.grid import CRS, map_grid, to_wgs84
from hirup_pipelines.ingest import openmeteo
from hirup_pipelines.settings import pilot_bbox

LAST_HOUR = pd.Timestamp("2026-10-10T23:00:00Z")
N_HOURS = 10 * 24


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HIRUP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HIRUP_MAP_EXTENT", "pilot")  # keep the small pilot grid in tests
    # Small forests keep the suite fast; accuracy is not what these tests measure.
    monkeypatch.setitem(load_config()["lightgbm"], "n_estimators", 40)
    # This simulated palette is allowed only inside isolated unit tests, never production.
    monkeypatch.setitem(load_config()["tiles"]["ispu"], "verified_by", "unit-test-only")
    return tmp_path / "data"


def make_cells(rng):
    grid = map_grid()
    cells = grid.frame()
    gradient = cells["col"] / grid.width  # more traffic towards the east
    cells["road_trunk_100m"] = np.clip(200 * gradient + rng.normal(0, 10, len(cells)), 0, None)
    cells["ndvi_mean_100m"] = np.clip(0.6 - 0.4 * gradient, -1, 1)
    cells["wc_frac_tree_100m"] = np.clip(0.5 - 0.4 * gradient, 0, 1)
    cells["wc_frac_lowveg_100m"] = 0.05
    cells["pop_density"] = 8000 + 6000 * (cells["row"] / grid.height)
    cells["kelurahan_id"] = np.where(cells["col"] < grid.width // 2, "osm_r1", "osm_r2")
    return grid, cells


@pytest.fixture
def toy(isolated_data_dir):
    """A complete data/ directory: grid, boundaries, stations, observations, weather, CAMS."""
    rng = np.random.default_rng(42)
    grid, cells = make_cells(rng)
    half = grid.res / 2
    gpd.GeoDataFrame(
        cells,
        geometry=[
            box(x - half, y - half, x + half, y + half)
            for x, y in zip(cells["x"], cells["y"], strict=True)
        ],
        crs=CRS,
    ).to_parquet(paths.grid_cells().parent.mkdir(parents=True, exist_ok=True) or paths.grid_cells())

    middle = grid.west + grid.width // 2 * grid.res
    halves = gpd.GeoDataFrame(
        {
            "kelurahan_id": ["osm_r1", "osm_r2"],
            "name": ["Barat", "Timur"],
            "kecamatan": ["Kec A", "Kec B"],
        },
        geometry=[
            box(grid.west, grid.south, middle, grid.north),
            box(middle, grid.south, grid.east, grid.north),
        ],
        crs=CRS,
    ).to_crs(4326)
    paths.boundaries().mkdir(parents=True, exist_ok=True)
    (paths.boundaries() / "toy.geojson").write_text(halves.to_json(), encoding="utf-8")
    store.write_json(
        {"boundaries_version": "kelurahan-toy", "path": "toy.geojson"},
        paths.boundaries() / "latest.json",
    )

    picks = cells.iloc[rng.choice(len(cells), size=8, replace=False)].reset_index(drop=True)
    lon, lat = to_wgs84(picks["x"], picks["y"])
    stations = pd.DataFrame(
        {
            "station_id": [f"openaq:{i}" for i in range(8)],
            "name": "toy",
            "type": "reference",
            "source": "openaq",
            "provider": "toy",
            "lat": lat,
            "lon": lon,
            "active": True,
            "x": picks["x"],
            "y": picks["y"],
            "merged_into": pd.Series([None] * 8, dtype="string"),
            "weight": 1.0,
            "calibrated": False,
        }
    )
    store.write_parquet(stations, paths.stations())
    static = picks.drop(columns=["row", "col", "kelurahan_id"]).assign(
        station_id=stations["station_id"]
    )
    store.write_parquet(static, paths.station_static())

    hours = pd.date_range(end=LAST_HOUR, periods=N_HOURS, freq="h")
    regional = 45 + 15 * np.sin(2 * np.pi * (hours.hour + 7) / 24) + rng.normal(0, 3, N_HOURS)
    frames = []
    for i, station in enumerate(stations["station_id"]):
        value = regional + 0.12 * picks.loc[i, "road_trunk_100m"] + rng.normal(0, 2, N_HOURS)
        frames.append(
            pd.DataFrame(
                {
                    "station_id": station,
                    "ts": hours,
                    "value_raw": value,
                    "value_cal": value,
                    "qc_flag": "ok",
                    "source": "openaq",
                }
            )
        )
    store.write_daily(
        pd.concat(frames, ignore_index=True), paths.observations(), ["station_id", "ts"]
    )

    span = pd.date_range(hours[0], LAST_HOUR + pd.Timedelta(hours=30), freq="h")
    points = openmeteo.lattice(pilot_bbox())
    weather = points.merge(pd.DataFrame({"ts": span}), how="cross").assign(
        wind_u=1.0, wind_v=-0.5, temp=28.0, rh=75.0, precip=0.0, blh=400.0
    )
    store.write_parquet(weather, paths.weather())
    level = np.resize(regional, len(span)) * 0.8
    cams = points.merge(pd.DataFrame({"ts": span, "pm25_cams": level}), how="cross")
    store.write_parquet(cams, paths.cams())
    return {"grid": grid, "cells": cells, "stations": stations, "last_hour": LAST_HOUR}
