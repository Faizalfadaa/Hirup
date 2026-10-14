"""Open raster layers warped onto a working grid: ESA WorldCover, its NDVI composite, WorldPop."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import numpy.typing as npt
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

from hirup_pipelines.grid import CRS, Grid
from hirup_pipelines.http import Client
from hirup_pipelines.settings import BBox, data_dir, load_config

log = logging.getLogger(__name__)
FloatArray = npt.NDArray[np.float32]

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


def _tile(lat: float, lon: float, size: int) -> tuple[str, str]:
    south = math.floor(lat / size) * size
    west = math.floor(lon / size) * size
    lat_name = f"{'S' if south < 0 else 'N'}{abs(south):02d}"
    return lat_name, f"{lat_name}{'W' if west < 0 else 'E'}{abs(west):03d}"


def tile_urls(template: str, bbox: BBox, size: int) -> list[str]:
    """ESA WorldCover tiles (named by their south-west corner) that intersect `bbox`."""
    urls = []
    for lat in np.arange(math.floor(bbox.min_lat / size) * size, bbox.max_lat, size):
        for lon in np.arange(math.floor(bbox.min_lon / size) * size, bbox.max_lon, size):
            lat_name, tile = _tile(float(lat), float(lon), size)
            urls.append(template.format(lat=lat_name, tile=tile))
    return urls


def warp(
    sources: list[str],
    grid: Grid,
    *,
    band: int = 1,
    resampling: Resampling = Resampling.nearest,
    fill: float = np.nan,
) -> FloatArray:
    """Reproject one band of the sources onto `grid`; cells no source covers hold `fill`."""
    out = np.full(grid.shape, np.nan, dtype=np.float32)
    with rasterio.Env(**GDAL_ENV):
        for source in sources:
            part = np.full(grid.shape, np.nan, dtype=np.float32)
            with rasterio.open(source) as src:
                reproject(
                    rasterio.band(src, band),
                    part,
                    dst_transform=grid.transform,
                    dst_crs=CRS,
                    dst_nodata=np.nan,
                    resampling=resampling,
                )
            out = np.where(np.isnan(out), part, out)
    return np.where(np.isnan(out), np.float32(fill), out).astype(np.float32)


def worldcover(grid: Grid) -> FloatArray:
    """Land-cover class codes (10 tree, 50 built-up, 80 water, ...); 0 where unmapped."""
    template = load_config()["rasters"]["worldcover_url"]
    return warp(tile_urls(template, grid.bbox_wgs84(), 3), grid, fill=0.0)


def ndvi(grid: Grid) -> FloatArray:
    """Median 2021 NDVI (band 2 of the WorldCover NDVI composite), NaN where missing."""
    template = load_config()["rasters"]["ndvi_url"]
    # Stored as uint8 with scale 0.008 and offset -1; 255 is nodata (handled by the warp).
    raw = warp(
        tile_urls(template, grid.bbox_wgs84(), 1), grid, band=2, resampling=Resampling.bilinear
    )
    return (raw * np.float32(0.008) - np.float32(1.0)).astype(np.float32)


def download(url: str, target: Path) -> Path:
    if target.is_file() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    log.info("downloading %s", url.rsplit("/", 1)[-1])
    with Client(timeout_s=600.0) as http:
        partial.write_bytes(http.request("GET", url).content)
    partial.replace(target)
    return target


def population_density(grid: Grid) -> FloatArray:
    """People per km2 from WorldPop 2020 constrained (people per ~100 m pixel)."""
    url = load_config()["rasters"]["worldpop_url"]
    path = download(url, data_dir() / "raw" / "worldpop" / url.rsplit("/", 1)[-1])
    with rasterio.open(path) as src:
        res_lon, res_lat = src.res
    people = warp([str(path)], grid, resampling=Resampling.bilinear, fill=0.0)
    box = grid.bbox_wgs84()
    mid_lat = math.radians((box.min_lat + box.max_lat) / 2)
    pixel_km2 = (res_lon * 111.320 * math.cos(mid_lat)) * (res_lat * 110.574)
    return (np.clip(people, 0, None) / np.float32(pixel_km2)).astype(np.float32)
