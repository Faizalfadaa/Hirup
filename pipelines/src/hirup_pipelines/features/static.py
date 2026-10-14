"""Static land-use features per 100 m cell (SPEC 11.2: roads, transit, buildings, vegetation,
population). The same function serves the pilot grid and small patches around stations that
lie outside it, so training and inference features are computed identically.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import numpy.typing as npt
import pandas as pd
import shapely
from rasterio.features import rasterize
from scipy import ndimage, signal

from hirup_pipelines.grid import Grid
from hirup_pipelines.ingest.osm import OsmLayers
from hirup_pipelines.settings import load_config

FloatArray = npt.NDArray[np.float64]

LINE_FACTOR = 5  # 20 m working raster for lines and points (odd, so cell centres align)
AREA_FACTOR = 10  # 10 m working raster for polygons and land cover
WC_TREE, WC_BUILT, WC_WATER = 10, 50, 80
WC_LOW_VEG = (20, 30, 40, 90)  # shrubland, grassland, cropland, herbaceous wetland


@dataclass
class Layers:
    """Inputs on the working extent `grid.expand(margin_cells)`."""

    osm: OsmLayers
    worldcover: npt.NDArray[np.float32]  # 10 m class codes
    ndvi: npt.NDArray[np.float32]  # 10 m
    population: npt.NDArray[np.float32]  # 100 m, people per km2
    transit: gpd.GeoDataFrame | None  # GTFS shapes with trips_per_hour, is_brt


def disk(radius_px: float) -> FloatArray:
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    return np.asarray(np.hypot(xx, yy) <= radius_px + 1e-9, dtype=np.float64)


def disk_sum(values: FloatArray, radius_px: float) -> FloatArray:
    """Sum of a non-negative raster over a disk around each pixel."""
    out = signal.fftconvolve(values, disk(radius_px), mode="same")
    return np.asarray(np.where(out < 1e-6, 0.0, out), dtype=float)  # FFT round-off


def disk_mean(values: FloatArray, radius_px: float) -> FloatArray:
    """Mean over a disk, ignoring NaN cells."""
    valid = np.isfinite(values).astype(float)
    total = signal.fftconvolve(np.nan_to_num(values), disk(radius_px), mode="same")
    count = signal.fftconvolve(valid, disk(radius_px), mode="same")
    return np.asarray(np.where(count > 0.5, total / np.maximum(count, 0.5), np.nan), dtype=float)


def block(values: npt.NDArray[np.floating], factor: int, how: str = "mean") -> FloatArray:
    h, w = values.shape[0] // factor, values.shape[1] // factor
    blocks = values.reshape(h, factor, w, factor).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN blocks stay NaN
        if how == "max":
            reduced = np.nanmax(blocks, axis=(1, 3))
        else:
            reduced = np.nanmean(blocks, axis=(1, 3))
    return np.asarray(reduced, dtype=np.float64)


def line_length_raster(lines: gpd.GeoSeries, fine: Grid) -> FloatArray:
    """Metres of line per fine pixel, binned by the midpoints of <= 5 m pieces."""
    out = np.zeros(fine.shape)
    if len(lines) == 0:
        return out
    pieces = shapely.segmentize(lines.values, fine.res / 4)
    coords, index = shapely.get_coordinates(pieces, return_index=True)
    same = index[1:] == index[:-1]
    start, end = coords[:-1][same], coords[1:][same]
    length = np.hypot(*(end - start).T)
    mid = (start + end) / 2
    row, col = fine.locate(mid[:, 0], mid[:, 1])
    keep = fine.inside(row, col)
    np.add.at(out, (row[keep], col[keep]), length[keep])
    return out


def point_count_raster(xy: npt.NDArray[np.float64], fine: Grid) -> FloatArray:
    out = np.zeros(fine.shape)
    if len(xy):
        row, col = fine.locate(xy[:, 0], xy[:, 1])
        keep = fine.inside(row, col)
        np.add.at(out, (row[keep], col[keep]), 1.0)
    return out


def polygon_fraction(polygons: gpd.GeoSeries, fine: Grid) -> FloatArray:
    """1 where a fine pixel centre falls in any polygon."""
    if len(polygons) == 0:
        return np.zeros(fine.shape)
    burned = rasterize(
        ((geom, 1) for geom in polygons.values if geom is not None and not geom.is_empty),
        out_shape=fine.shape,
        transform=fine.transform,
        fill=0,
        dtype="uint8",
    )
    return np.asarray(burned, dtype=float)


def compute_static(grid: Grid, layers: Layers) -> pd.DataFrame:
    """One row per cell of `grid`. Layers must cover `grid.expand(margin_cells)`."""
    cfg = load_config()["features"]
    margin = int(cfg["margin_cells"])
    work = grid.expand(margin)
    inner = (slice(margin, margin + grid.height), slice(margin, margin + grid.width))
    centre = (slice(LINE_FACTOR // 2, None, LINE_FACTOR),) * 2  # fine pixel at each cell centre
    fine = work.refine(LINE_FACTOR)
    cols: dict[str, FloatArray] = {}

    # Roads: metres of each class within a buffer of the cell centre.
    roads = layers.osm.roads
    major = np.zeros(fine.shape, dtype=bool)
    for road_class in load_config()["osm"]["road_classes"]:
        selected = (
            roads.geometry[roads["road_class"] == road_class] if len(roads) else gpd.GeoSeries([])
        )
        length = line_length_raster(selected, fine)
        if road_class in ("trunk", "primary"):
            major |= length > 0
        for buffer_m in cfg["road_buffers_m"]:
            summed = disk_sum(length, buffer_m / fine.res)
            cols[f"road_{road_class}_{buffer_m}m"] = summed[centre][inner]
    cap = float(cfg["distance_cap_m"])
    distance = (
        ndimage.distance_transform_edt(~major) * fine.res
        if major.any()
        else np.full(fine.shape, cap)
    )
    cols["dist_major_road_m"] = np.minimum(distance, cap)[centre][inner]
    junction_sum = disk_sum(point_count_raster(layers.osm.junctions, fine), 300 / fine.res)
    cols["junction_density_300m"] = junction_sum[centre][inner] / (np.pi * 0.3**2)

    # Buildings: footprint fraction and count.
    area = work.refine(AREA_FACTOR)
    footprint = block(polygon_fraction(layers.osm.buildings.geometry, area), AREA_FACTOR)
    cols["bldg_frac_100m"] = footprint[inner]
    cols["bldg_frac_300m"] = np.clip(disk_mean(footprint, 3), 0, 1)[inner]
    centroids = (
        shapely.get_coordinates(layers.osm.buildings.geometry.centroid.values)
        if len(layers.osm.buildings)
        else np.empty((0, 2))
    )
    cols["bldg_count_300m"] = disk_sum(point_count_raster(centroids, work), 3)[inner]

    # Land cover fractions and NDVI.
    cover = layers.worldcover
    for name, mask in {
        "tree": cover == WC_TREE,
        "built": cover == WC_BUILT,
        "water": cover == WC_WATER,
        "lowveg": np.isin(cover, WC_LOW_VEG),
    }.items():
        fraction = block(mask.astype(float), AREA_FACTOR)
        if name != "water":
            cols[f"wc_frac_{name}_100m"] = fraction[inner]
        cols[f"wc_frac_{name}_300m"] = np.clip(disk_mean(fraction, 3), 0, 1)[inner]
    ndvi_mean = block(layers.ndvi, AREA_FACTOR)
    cols["ndvi_mean_100m"] = ndvi_mean[inner]
    cols["ndvi_mean_300m"] = disk_mean(ndvi_mean, 3)[inner]
    ndvi_max = ndimage.maximum_filter(
        np.nan_to_num(block(layers.ndvi, AREA_FACTOR, "max"), nan=-1.0), footprint=disk(3) > 0
    )
    cols["ndvi_max_300m"] = np.where(np.isfinite(cols["ndvi_mean_300m"]), ndvi_max[inner], np.nan)

    cols["pop_density"] = np.asarray(layers.population, dtype=float)[inner]

    # Transit: distance to the nearest BRT corridor and scheduled bus trips through the cell.
    x, y = grid.mesh()
    brt_cap = float(cfg["brt_distance_cap_m"])
    if layers.transit is not None and len(layers.transit):
        brt = layers.transit.geometry[layers.transit["is_brt"]]
        dist_brt = (
            shapely.distance(shapely.points(x, y), brt.union_all())
            if len(brt)
            else np.full(grid.size, np.nan)
        )
        cols["dist_brt_m"] = np.minimum(dist_brt, brt_cap).reshape(grid.shape)
        trips = np.zeros(work.shape)
        clipped = shapely.clip_by_rect(
            layers.transit.geometry.values, work.west, work.south, work.east, work.north
        )
        for line, per_hour in zip(clipped, layers.transit["trips_per_hour"], strict=True):
            if not line.is_empty:
                trips[line_length_raster(gpd.GeoSeries([line]), work) > 0] += float(per_hour)
        cols["bus_trips_per_hour"] = trips[inner]
    else:
        cols["dist_brt_m"] = np.full(grid.shape, np.nan)
        cols["bus_trips_per_hour"] = np.full(grid.shape, np.nan)

    frame = grid.frame()
    for name, values in cols.items():
        frame[name] = np.asarray(values, dtype=float).ravel()
    return frame


def feature_columns(frame: pd.DataFrame) -> list[str]:
    skip = {"cell_id", "row", "col", "x", "y", "lon", "lat", "kelurahan_id", "station_id"}
    return [name for name in frame.columns if name not in skip and name != "geometry"]
