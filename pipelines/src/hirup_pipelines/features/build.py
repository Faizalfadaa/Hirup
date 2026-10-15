"""Build static features for the pilot grid and for station locations."""

from __future__ import annotations

import logging
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from hirup_pipelines import paths, schemas, store
from hirup_pipelines.features.static import AREA_FACTOR, Layers, compute_static
from hirup_pipelines.grid import CRS, Grid, cell_id, pilot_grid
from hirup_pipelines.ingest import gtfs, osm, rasters
from hirup_pipelines.settings import load_config, pilot_bbox

log = logging.getLogger(__name__)


def gather_layers(grid: Grid, transit: gpd.GeoDataFrame | None) -> Layers:
    work = grid.expand(int(load_config()["features"]["margin_cells"]))
    area = work.refine(AREA_FACTOR)
    return Layers(
        osm=osm.fetch_layers(work.bbox_wgs84()),
        worldcover=rasters.worldcover(area),
        ndvi=rasters.ndvi(area),
        population=rasters.population_density(work),
        transit=transit,
    )


def load_transit() -> gpd.GeoDataFrame | None:
    try:
        return gtfs.load_shapes()
    except Exception as exc:  # a missing feed degrades two features, not the whole build
        log.warning("GTFS unavailable (%s); transit features will be empty", type(exc).__name__)
        return None


def build_boundaries() -> tuple[gpd.GeoDataFrame, str]:
    """Kelurahan polygons from OSM, saved as GeoJSON for the app's Insight Kota tab."""
    kelurahan = osm.fetch_admin(pilot_bbox())
    version = f"kelurahan-osm-{date.today().isoformat()}"
    target = paths.boundaries() / f"{version}.geojson"
    target.parent.mkdir(parents=True, exist_ok=True)
    simplified = kelurahan.copy()
    simplified["geometry"] = simplified.geometry.simplify(0.00005, preserve_topology=True)
    target.write_text(simplified.to_json(drop_id=True), encoding="utf-8")
    store.write_json(
        {
            "boundaries_version": version,
            "path": target.name,
            "source": "OpenStreetMap admin_level=7 relations via Overpass (ODbL)",
            "count": len(kelurahan),
        },
        paths.boundaries() / "latest.json",
    )
    return kelurahan, version


def build_grid_static() -> pd.DataFrame:
    """Static features + kelurahan for every pilot cell -> `grid_cells.parquet` (GeoParquet)."""
    grid = pilot_grid()
    if not (osm.index_dir() / "meta.json").is_file():
        osm.build_index()
    frame = compute_static(grid, gather_layers(grid, load_transit()))
    kelurahan, boundaries_version = build_boundaries()
    points = gpd.GeoDataFrame(
        frame[["cell_id"]], geometry=gpd.points_from_xy(frame["x"], frame["y"]), crs=CRS
    )
    joined = gpd.sjoin(
        points, kelurahan.to_crs(CRS)[["kelurahan_id", "geometry"]], how="left", predicate="within"
    )
    frame["kelurahan_id"] = (
        (joined.drop_duplicates("cell_id").set_index("cell_id")["kelurahan_id"])
        .reindex(frame["cell_id"])
        .to_numpy()
    )
    frame["kelurahan_id"] = frame["kelurahan_id"].astype("string")
    schemas.validate(frame, schemas.STATIC_FEATURES)
    half = grid.res / 2
    cells = gpd.GeoDataFrame(
        frame,
        geometry=shapely.box(
            frame["x"] - half, frame["y"] - half, frame["x"] + half, frame["y"] + half
        ),
        crs=CRS,
    )
    version = f"features_static_v{date.today().isoformat()}"
    dated = paths.features() / f"{version}.parquet"
    for target in (dated, paths.grid_cells()):
        tmp = store.atomic_path(target)
        cells.to_parquet(tmp, index=False)
        tmp.replace(target)
    store.write_json(
        {
            "version": version,
            "boundaries_version": boundaries_version,
            "cells": len(cells),
            "grid": {
                "west": grid.west,
                "north": grid.north,
                "width": grid.width,
                "height": grid.height,
                "res": grid.res,
                "crs": CRS,
            },
        },
        paths.features() / "static_latest.json",
    )
    return frame


def build_station_static(stations: pd.DataFrame) -> pd.DataFrame:
    """Static features at each station: a grid lookup inside the pilot, a small patch outside."""
    grid = pilot_grid()
    grid_static = pd.read_parquet(paths.grid_cells()).drop(columns=["geometry", "kelurahan_id"])
    done = store.read_parquet(paths.station_static())
    known = set() if done is None else set(done["station_id"])
    by_cell = grid_static.set_index("cell_id")
    transit: gpd.GeoDataFrame | None = None
    rows = []
    for station in stations.itertuples(index=False):
        if station.station_id in known:
            continue
        cid = str(cell_id(station.x, station.y))
        if cid in by_cell.index:
            row = by_cell.loc[cid].to_dict() | {"cell_id": cid}
        else:
            transit = transit if transit is not None else load_transit()
            patch = Grid.around(station.x, station.y, cells=1, res=grid.res)
            computed = compute_static(patch, gather_layers(patch, transit))
            row = computed[computed["cell_id"] == cid].iloc[0].to_dict()
        rows.append(row | {"station_id": station.station_id})
        log.info("static features for %s", station.station_id)
    if not rows:
        return done if done is not None else pd.DataFrame()
    new = pd.DataFrame(rows).drop(columns=["row", "col"], errors="ignore")
    merged = new if done is None else pd.concat([done, new], ignore_index=True)
    numeric = merged.select_dtypes("number").columns
    merged[numeric] = merged[numeric].astype(float).replace([np.inf, -np.inf], np.nan)
    store.write_parquet(merged, paths.station_static())
    return merged
