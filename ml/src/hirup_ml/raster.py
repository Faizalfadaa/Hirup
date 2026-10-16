"""Hourly raster sets: Cloud-Optimized GeoTIFFs, their contract manifest and map tiles."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import jsonschema
import numpy as np
import numpy.typing as npt
import rasterio
from PIL import Image
from scipy import ndimage

from hirup_ml.config import MANIFEST_SCHEMA, load_config
from hirup_pipelines import store
from hirup_pipelines.grid import CRS, Grid, to_utm
from hirup_pipelines.settings import TIMEZONE, data_dir, map_bbox

FloatArray = npt.NDArray[np.float64]
QUANTILES = ("p10", "p50", "p90")
LOCAL = ZoneInfo(TIMEZONE)


def stamp(valid_hour: datetime) -> str:
    """`yyyymmddhh` in Asia/Jakarta, the key the API uses for tiles."""
    return valid_hour.astimezone(LOCAL).strftime("%Y%m%d%H")


def postprocess(p10: FloatArray, p50: FloatArray, p90: FloatArray) -> dict[str, FloatArray]:
    """SPEC 11.6: clip to [0, 500], light Gaussian smoothing, then force P10 <= P50 <= P90."""
    cfg = load_config()["postprocess"]
    low, high = cfg["clip"]
    sigma = float(cfg["gaussian_sigma_cells"])
    smoothed = [
        ndimage.gaussian_filter(np.clip(a, low, high), sigma, mode="nearest") if sigma > 0 else a
        for a in (p10, p50, p90)
    ]
    mid = np.clip(smoothed[1], low, high)
    return {
        "p10": np.clip(np.minimum(smoothed[0], mid), low, high),
        "p50": mid,
        "p90": np.clip(np.maximum(smoothed[2], mid), low, high),
    }


def write_cog(path: Path, array: FloatArray, grid: Grid) -> None:
    """Write one band as a Cloud-Optimized GeoTIFF. No nodata: every cell of the grid is valid.

    The pilot raster is smaller than one 512 px block, so a tiled GeoTIFF without overviews
    already has the COG layout; writing it directly is several times faster than the COG driver.
    """
    if array.shape != grid.shape or not np.isfinite(array).all():
        raise ValueError("Raster must cover the whole grid with finite values")
    tmp = store.atomic_path(path)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=grid.height,
        width=grid.width,
        count=1,
        dtype="float32",
        crs=CRS,
        transform=grid.transform,
        tiled=True,
        blockxsize=512,
        blockysize=512,
        compress="DEFLATE",
        predictor=3,
    ) as dataset:
        dataset.write(array.astype(np.float32), 1)
    tmp.replace(path)


@cache
def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    _validator().validate(manifest)


@dataclass(frozen=True)
class RasterSet:
    valid_hour: datetime
    arrays: dict[str, FloatArray]
    kind: str  # nowcast | forecast
    lead_hours: int
    data_quality: str  # real | approximated
    model_version: str


def write_set(
    raster: RasterSet,
    grid: Grid,
    run_dir: Path,
    generated_at: datetime,
    extra_metrics: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """Write the three COGs into `run_dir` and return the contract manifest."""
    key = stamp(raster.valid_hour)
    files = {}
    for name in QUANTILES:
        path = run_dir / f"pm25_{key}_{name}.tif"
        write_cog(path, raster.arrays[name], grid)
        files[name] = path.relative_to(data_dir()).as_posix()
    box = map_bbox()
    p50 = raster.arrays["p50"]
    manifest = {
        "manifest_version": "1.0",
        "model_version": raster.model_version,
        "generated_at": generated_at.astimezone(LOCAL).isoformat(timespec="seconds"),
        "valid_hour": raster.valid_hour.astimezone(LOCAL).isoformat(timespec="seconds"),
        "kind": raster.kind,
        "lead_hours": raster.lead_hours,
        "crs": CRS,
        "resolution_m": 100,
        "bbox_wgs84": {
            "min_lat": box.min_lat,
            "max_lat": box.max_lat,
            "min_lon": box.min_lon,
            "max_lon": box.max_lon,
        },
        "units": "ug/m3",
        "files": files,
        "data_quality": raster.data_quality,
        "metrics": {
            "p50_median": float(np.median(p50)),
            "p50_spatial_std": float(np.std(p50)),
            # Sanity check for grid artefacts: largest jump between neighbouring cells.
            "p50_max_adjacent_jump": float(
                max(np.abs(np.diff(p50, axis=0)).max(), np.abs(np.diff(p50, axis=1)).max())
            ),
            **(extra_metrics or {}),
        },
    }
    validate_manifest(manifest)
    return manifest


# --- map tiles -------------------------------------------------------------------------------


@cache
def colour_steps() -> tuple[FloatArray, npt.NDArray[np.uint8]]:
    """Upper bounds and RGB colours of the configured ISPU categories."""
    categories = load_config()["tiles"]["ispu"]["categories"]
    uppers = np.array([float(upper) for _, upper, _ in categories])
    colours = np.array([rgb for _, _, rgb in categories], dtype=np.uint8)
    return uppers, colours


def colourise(values: FloatArray) -> npt.NDArray[np.uint8]:
    """One flat colour per category, as in the regulation: a value takes the colour of the
    first category whose upper bound it does not exceed (15.5 is still "baik")."""
    uppers, colours = colour_steps()
    index = np.searchsorted(uppers, np.asarray(values), side="left")
    return colours[np.clip(index, 0, len(colours) - 1)]


def tile_range(z: int) -> tuple[range, range]:
    box = map_bbox()
    n = 2**z

    def x_of(lon: float) -> int:
        return int(min(n - 1, max(0, int((lon + 180) / 360 * n))))

    def y_of(lat: float) -> int:
        rad = math.radians(lat)
        return int(min(n - 1, max(0, int((1 - math.asinh(math.tan(rad)) / math.pi) / 2 * n))))

    return range(x_of(box.min_lon), x_of(box.max_lon) + 1), range(
        y_of(box.max_lat), y_of(box.min_lat) + 1
    )


@dataclass(frozen=True)
class TileIndex:
    """Where each pixel of one 256 px tile falls on the raster (fractional row/column)."""

    z: int
    x: int
    y: int
    rows: FloatArray
    cols: FloatArray
    inside: npt.NDArray[np.bool_]


TILE_KNOTS = 17  # projection is evaluated on a 17 x 17 lattice per tile, then interpolated


def _pixel_positions(grid: Grid, n: int, x: int, y: int) -> tuple[FloatArray, FloatArray]:
    """Fractional raster row/column of each tile pixel centre. UTM is smooth over one tile,
    so projecting a coarse lattice and interpolating is accurate to well under a metre."""
    knots = np.linspace(0.0, 256.0, TILE_KNOTS)
    col, row = np.meshgrid(knots, knots)
    lon = (x + col / 256) / n * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (y + row / 256) / n))))
    ux, uy = to_utm(lon.ravel(), lat.ravel())
    rows = ((grid.north - uy) / grid.res - 0.5).reshape(TILE_KNOTS, TILE_KNOTS)
    cols = ((ux - grid.west) / grid.res - 0.5).reshape(TILE_KNOTS, TILE_KNOTS)
    at = (np.arange(256) + 0.5) / (256 / (TILE_KNOTS - 1))
    where = np.meshgrid(at, at, indexing="ij")
    return (
        ndimage.map_coordinates(rows, where, order=1),
        ndimage.map_coordinates(cols, where, order=1),
    )


def tile_indices(grid: Grid) -> list[TileIndex]:
    """Tile geometry depends only on the grid, so it is computed once per run."""
    box = map_bbox()
    out = []
    for z in load_config()["tiles"]["zooms"]:
        n = 2**z
        xs, ys = tile_range(z)
        for x in xs:
            for y in ys:
                col, row = np.meshgrid(np.arange(256) + 0.5, np.arange(256) + 0.5)
                lon = (x + col / 256) / n * 360 - 180
                lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (y + row / 256) / n))))
                inside = (
                    (lon >= box.min_lon)
                    & (lon <= box.max_lon)
                    & (lat >= box.min_lat)
                    & (lat <= box.max_lat)
                )
                if not inside.any():
                    continue
                rows, cols = _pixel_positions(grid, n, x, y)
                out.append(TileIndex(z, x, y, rows, cols, inside))
    return out


def render_tiles(
    p50: FloatArray, valid_hour: datetime, indices: list[TileIndex], root: Path
) -> int:
    """PNG tiles for one hour at `root/{yyyymmddhh}/{z}/{x}/{y}.png`; transparent outside."""
    alpha = int(load_config()["tiles"]["alpha"])
    folder = root / stamp(valid_hour)
    for tile in indices:
        values = ndimage.map_coordinates(p50, [tile.rows, tile.cols], order=1, mode="nearest")
        rgba = np.zeros((256, 256, 4), dtype=np.uint8)
        rgba[..., :3] = colourise(values)
        rgba[..., 3] = np.where(tile.inside, alpha, 0)
        path = folder / str(tile.z) / str(tile.x) / f"{tile.y}.png"
        tmp = store.atomic_path(path)
        Image.fromarray(rgba, "RGBA").save(tmp, format="PNG", compress_level=1)
        tmp.replace(path)
    return len(indices)


def read_p50(manifest: dict[str, Any]) -> FloatArray:
    with rasterio.open(data_dir() / manifest["files"]["p50"]) as src:
        return np.asarray(src.read(1), dtype=float)
