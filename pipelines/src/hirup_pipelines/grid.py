"""The 100 m pilot grid in EPSG:32748, aligned to the lattice the API uses for `cell_id`."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd
from pyproj import Transformer
from rasterio.transform import Affine

from hirup_pipelines.settings import BBox, load_config, pilot_bbox

CRS = "EPSG:32748"
TO_UTM = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
TO_WGS84 = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)

FloatArray = npt.NDArray[np.float64]


def to_utm(lon: npt.ArrayLike, lat: npt.ArrayLike) -> tuple[FloatArray, FloatArray]:
    x, y = TO_UTM.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


def to_wgs84(x: npt.ArrayLike, y: npt.ArrayLike) -> tuple[FloatArray, FloatArray]:
    lon, lat = TO_WGS84.transform(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)


@dataclass(frozen=True, slots=True)
class Grid:
    """North-up raster grid. `west`/`north` are the outer edges of the top-left cell."""

    west: float
    north: float
    width: int
    height: int
    res: float = 100.0

    @classmethod
    def from_bbox(cls, bbox: BBox, res: float = 100.0) -> Grid:
        # A lat/lon rectangle is not a rectangle in UTM, so take the envelope of its outline.
        t = np.linspace(0.0, 1.0, 51)
        lon = np.concatenate(
            [
                bbox.min_lon + t * (bbox.max_lon - bbox.min_lon),
                np.full_like(t, bbox.max_lon),
                bbox.min_lon + t * (bbox.max_lon - bbox.min_lon),
                np.full_like(t, bbox.min_lon),
            ]
        )
        lat = np.concatenate(
            [
                np.full_like(t, bbox.min_lat),
                bbox.min_lat + t * (bbox.max_lat - bbox.min_lat),
                np.full_like(t, bbox.max_lat),
                bbox.min_lat + t * (bbox.max_lat - bbox.min_lat),
            ]
        )
        x, y = to_utm(lon, lat)
        west = math.floor(x.min() / res) * res
        east = math.ceil(x.max() / res) * res
        south = math.floor(y.min() / res) * res
        north = math.ceil(y.max() / res) * res
        return cls(west, north, round((east - west) / res), round((north - south) / res), res)

    @classmethod
    def around(cls, x: float, y: float, cells: int = 1, res: float = 100.0) -> Grid:
        """A small lattice-aligned grid whose centre cell contains (x, y)."""
        west = (math.floor(x / res) - cells) * res
        north = (math.floor(y / res) + 1 + cells) * res
        return cls(west, north, 2 * cells + 1, 2 * cells + 1, res)

    @property
    def east(self) -> float:
        return self.west + self.width * self.res

    @property
    def south(self) -> float:
        return self.north - self.height * self.res

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    @property
    def size(self) -> int:
        return self.height * self.width

    @property
    def transform(self) -> Affine:
        return Affine(self.res, 0.0, self.west, 0.0, -self.res, self.north)

    def expand(self, cells: int) -> Grid:
        return Grid(
            self.west - cells * self.res,
            self.north + cells * self.res,
            self.width + 2 * cells,
            self.height + 2 * cells,
            self.res,
        )

    def refine(self, factor: int) -> Grid:
        return Grid(
            self.west, self.north, self.width * factor, self.height * factor, self.res / factor
        )

    def centers(self) -> tuple[FloatArray, FloatArray]:
        """Cell-centre x per column and y per row."""
        x = self.west + (np.arange(self.width) + 0.5) * self.res
        y = self.north - (np.arange(self.height) + 0.5) * self.res
        return np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)

    def mesh(self) -> tuple[FloatArray, FloatArray]:
        """Flattened (row-major) cell-centre coordinates."""
        x, y = self.centers()
        xx, yy = np.meshgrid(x, y)
        return xx.ravel(), yy.ravel()

    def locate(
        self, x: npt.ArrayLike, y: npt.ArrayLike
    ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]:
        """Row and column of the cell containing each point (may fall outside the grid)."""
        col = np.floor((np.asarray(x, dtype=float) - self.west) / self.res).astype(np.int64)
        row = np.floor((self.north - np.asarray(y, dtype=float)) / self.res).astype(np.int64)
        return row, col

    def inside(self, row: npt.ArrayLike, col: npt.ArrayLike) -> npt.NDArray[np.bool_]:
        r, c = np.asarray(row), np.asarray(col)
        return (r >= 0) & (r < self.height) & (c >= 0) & (c < self.width)

    def bbox_wgs84(self) -> BBox:
        x = np.array([self.west, self.east, self.west, self.east])
        y = np.array([self.south, self.south, self.north, self.north])
        lon, lat = to_wgs84(x, y)
        return BBox(float(lat.min()), float(lat.max()), float(lon.min()), float(lon.max()))

    def cell_ids(self) -> npt.NDArray[np.str_]:
        """`{easting // 100}:{northing // 100}`, the same id `GET /v1/aq/point` returns."""
        x, y = self.mesh()
        return cell_id(x, y)

    def frame(self) -> pd.DataFrame:
        x, y = self.mesh()
        lon, lat = to_wgs84(x, y)
        row, col = np.divmod(np.arange(self.size), self.width)
        return pd.DataFrame(
            {
                "cell_id": cell_id(x, y),
                "row": row,
                "col": col,
                "x": x,
                "y": y,
                "lon": lon,
                "lat": lat,
            }
        )


def cell_id(x: npt.ArrayLike, y: npt.ArrayLike) -> npt.NDArray[np.str_]:
    e = np.floor(np.asarray(x, dtype=float) / 100).astype(np.int64)
    n = np.floor(np.asarray(y, dtype=float) / 100).astype(np.int64)
    ids: npt.NDArray[np.str_] = np.char.add(np.char.add(e.astype(str), ":"), n.astype(str))
    return ids


def pilot_grid() -> Grid:
    return Grid.from_bbox(pilot_bbox(), float(load_config()["grid"]["resolution_m"]))
