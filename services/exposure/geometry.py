"""Coordinate and polyline operations shared by sampling and active routing."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise

import numpy as np
import numpy.typing as npt
from pyproj import Geod, Transformer

FloatArray = npt.NDArray[np.float64]
GEOD = Geod(ellps="WGS84")
TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32748", always_xy=True)
TO_WGS84 = Transformer.from_crs("EPSG:32748", "EPSG:4326", always_xy=True)


@dataclass(frozen=True, slots=True)
class Point:
    lon: float
    lat: float

    def __post_init__(self) -> None:
        if not (-180 <= self.lon <= 180 and -90 <= self.lat <= 90):
            raise ValueError("Coordinates must be finite WGS84 longitude/latitude")


@dataclass(frozen=True, slots=True)
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def __post_init__(self) -> None:
        Point(self.min_lon, self.min_lat)
        Point(self.max_lon, self.max_lat)
        if self.min_lat >= self.max_lat or self.min_lon >= self.max_lon:
            raise ValueError("Bounding box limits must be ordered")

    def contains(self, point: Point) -> bool:
        return (
            self.min_lat <= point.lat <= self.max_lat and self.min_lon <= point.lon <= self.max_lon
        )

    def clamp(self, point: Point) -> Point:
        return Point(
            min(self.max_lon, max(self.min_lon, point.lon)),
            min(self.max_lat, max(self.min_lat, point.lat)),
        )


def hour_key(ts: datetime) -> datetime:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return ts.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def project_points(points: Sequence[Point]) -> tuple[FloatArray, FloatArray]:
    x, y = TO_UTM.transform([p.lon for p in points], [p.lat for p in points])
    return np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)


def unproject(x: float, y: float) -> Point:
    lon, lat = TO_WGS84.transform(x, y)
    return Point(float(lon), float(lat))


def distance_m(a: Point, b: Point) -> float:
    return float(GEOD.inv(a.lon, a.lat, b.lon, b.lat)[2])


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance_m(a, b) for a, b in pairwise(points))


def segment_lengths(points: Sequence[Point]) -> FloatArray:
    """Geodesic distances in one native call, including duplicate vertices."""
    if len(points) < 2:
        return np.empty(0, dtype=np.float64)
    lon = np.asarray([p.lon for p in points], dtype=np.float64)
    lat = np.asarray([p.lat for p in points], dtype=np.float64)
    return np.asarray(GEOD.inv(lon[:-1], lat[:-1], lon[1:], lat[1:])[2], dtype=np.float64)


def sample_polyline(points: Sequence[Point], spacing_m: float) -> tuple[Point, ...]:
    """Include both endpoints and globally spaced samples, not per-edge restarts."""
    if not points:
        raise ValueError("Polyline must contain a point")
    if not math.isfinite(spacing_m) or spacing_m <= 0:
        raise ValueError("Sample spacing must be finite and positive")
    if len(points) == 1:
        return (points[0],)
    lon = np.asarray([p.lon for p in points], dtype=np.float64)
    lat = np.asarray([p.lat for p in points], dtype=np.float64)
    bearings, _, lengths = GEOD.inv(lon[:-1], lat[:-1], lon[1:], lat[1:])
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    positions = np.arange(1, math.ceil(cumulative[-1] / spacing_m)) * spacing_m
    positions = positions[positions < cumulative[-1]]
    # Right-side lookup skips zero-length vertices and samples on vertex boundaries.
    indices = np.searchsorted(cumulative, positions, side="right") - 1
    sampled_lon, sampled_lat, _ = GEOD.fwd(
        lon[indices], lat[indices], bearings[indices], positions - cumulative[indices]
    )
    sampled = [
        points[0],
        *(Point(float(x), float(y)) for x, y in zip(sampled_lon, sampled_lat, strict=True)),
    ]
    if distance_m(sampled[-1], points[-1]) > 1e-6:
        sampled.append(points[-1])
    else:
        sampled[-1] = points[-1]
    return tuple(sampled)
