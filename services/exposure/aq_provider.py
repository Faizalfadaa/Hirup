"""Thin AQ edges: hourly COGs, sourced IDW/CAMS inputs, and explicit demo data."""

from __future__ import annotations

import hashlib
import math
import threading
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
import rasterio  # type: ignore[import-untyped]
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from rasterio.transform import rowcol  # type: ignore[import-untyped]
from rasterio.windows import Window  # type: ignore[import-untyped]

from services.exposure.engine import Quantiles
from services.exposure.geometry import BoundingBox, FloatArray, Point, hour_key, project_points

DataQuality = Literal["real", "approximated", "synthetic"]


class AQUnavailableError(ValueError):
    """No valid sourced concentration is available for the requested hour."""


class OutOfServiceAreaError(ValueError):
    """The HTTP edge translates this to a 404 out_of_service_area problem."""


@dataclass(frozen=True, slots=True)
class Pm25Samples:
    p10: FloatArray
    p50: FloatArray
    p90: FloatArray
    valid_hour: datetime
    data_quality: DataQuality
    source: str

    def __post_init__(self) -> None:
        arrays = [np.array(a, dtype=np.float64, copy=True) for a in (self.p10, self.p50, self.p90)]
        if any(a.ndim != 1 or a.shape != arrays[0].shape for a in arrays):
            raise ValueError("PM2.5 samples must be matching one-dimensional arrays")
        if any(np.any(~np.isfinite(a)) or np.any(a < 0) for a in arrays):
            raise AQUnavailableError("PM2.5 samples must be finite and non-negative")
        if np.any(arrays[0] > arrays[1]) or np.any(arrays[1] > arrays[2]):
            raise AQUnavailableError("PM2.5 sample quantiles must be ordered")
        if self.data_quality not in {"real", "approximated", "synthetic"}:
            raise ValueError("Invalid data quality")
        for name, array in zip(("p10", "p50", "p90"), arrays, strict=True):
            array.setflags(write=False)
            object.__setattr__(self, name, array)
        object.__setattr__(self, "valid_hour", hour_key(self.valid_hour))

    def mean(self) -> Quantiles:
        if not len(self.p50):
            raise ValueError("Cannot average an empty sample set")
        return Quantiles(
            float(np.mean(self.p10)), float(np.mean(self.p50)), float(np.mean(self.p90))
        )


class AQProvider(Protocol):
    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples: ...


class ManifestBounds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    min_lat: float = Field(ge=-90, le=90)
    max_lat: float = Field(ge=-90, le=90)
    min_lon: float = Field(ge=-180, le=180)
    max_lon: float = Field(ge=-180, le=180)

    def domain(self) -> BoundingBox:
        return BoundingBox(self.min_lat, self.max_lat, self.min_lon, self.max_lon)


class RasterFiles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    p10: str = Field(pattern=r"^[^/].*pm25_[0-9]{10}_p(10|50|90)\.tif$")
    p50: str = Field(pattern=r"^[^/].*pm25_[0-9]{10}_p(10|50|90)\.tif$")
    p90: str = Field(pattern=r"^[^/].*pm25_[0-9]{10}_p(10|50|90)\.tif$")


class RasterManifest(BaseModel):
    """Matches raster_manifest.schema.json; no new contract fields are required."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    manifest_version: Literal["1.0"]
    model_version: str = Field(min_length=1)
    generated_at: AwareDatetime
    valid_hour: AwareDatetime
    kind: Literal["nowcast", "forecast"]
    lead_hours: int = Field(ge=0, le=24)
    crs: Literal["EPSG:32748"]
    resolution_m: Literal[100]
    bbox_wgs84: ManifestBounds
    units: Literal["ug/m3"]
    files: RasterFiles
    data_quality: DataQuality
    metrics: dict[str, float | None] | None = None

    @model_validator(mode="after")
    def check_geometry(self) -> RasterManifest:
        self.bbox_wgs84.domain()
        if self.valid_hour.minute or self.valid_hour.second or self.valid_hour.microsecond:
            raise ValueError("Raster valid_hour must start an hour")
        return self


@dataclass(frozen=True)
class _RasterSet:
    manifest: RasterManifest
    readers: tuple[Any, Any, Any]


class CogAQProvider:
    """Open rasters on refresh; use a bounded pixel window per sampling request."""

    def __init__(
        self,
        data_dir: Path,
        manifests: Sequence[Path],
        *,
        bounds: BoundingBox,
        allow_synthetic: bool = False,
    ) -> None:
        self.data_dir = data_dir.resolve()
        self.bounds = bounds
        self.allow_synthetic = allow_synthetic
        self._lock = threading.RLock()
        self._stack = ExitStack()
        self._rasters: dict[datetime, _RasterSet] = {}
        self._medians: dict[datetime, float] = {}
        self.reload(manifests)

    def reload(self, manifests: Sequence[Path]) -> None:
        new_stack = ExitStack()
        new_rasters: dict[datetime, _RasterSet] = {}
        try:
            for path in manifests:
                manifest = RasterManifest.model_validate_json(path.read_text(encoding="utf-8"))
                if manifest.data_quality == "synthetic" and not self.allow_synthetic:
                    raise AQUnavailableError("Synthetic rasters are forbidden in production")
                readers: list[Any] = []
                for filename in (manifest.files.p10, manifest.files.p50, manifest.files.p90):
                    target = (self.data_dir / filename).resolve()
                    if not target.is_relative_to(self.data_dir):
                        raise AQUnavailableError(
                            "Raster path escapes the configured data directory"
                        )
                    reader = new_stack.enter_context(rasterio.open(target))
                    if (
                        reader.crs is None
                        or reader.crs.to_epsg() != 32748
                        or reader.count != 1
                        or reader.transform.b != 0
                        or reader.transform.d != 0
                        or not math.isclose(reader.transform.a, manifest.resolution_m)
                        or not math.isclose(reader.transform.e, -manifest.resolution_m)
                    ):
                        raise AQUnavailableError("Raster grid does not match the frozen manifest")
                    readers.append(reader)
                if any(
                    r.transform != readers[0].transform or r.shape != readers[0].shape
                    for r in readers
                ):
                    raise AQUnavailableError("Quantile raster grids differ")
                key = hour_key(manifest.valid_hour)
                current = new_rasters.get(key)
                if current is None or current.manifest.generated_at < manifest.generated_at:
                    new_rasters[key] = _RasterSet(manifest, (readers[0], readers[1], readers[2]))
        except (OSError, ValueError, rasterio.errors.RasterioError) as exc:
            new_stack.close()
            if isinstance(exc, AQUnavailableError):
                raise
            raise AQUnavailableError("Unable to load the hourly raster set") from exc
        with self._lock:
            old = self._stack
            self._stack, self._rasters = new_stack, new_rasters
            self._medians = {}
            old.close()

    def _hour(self, ts: datetime) -> _RasterSet:
        try:
            return self._rasters[hour_key(ts)]
        except KeyError as exc:
            raise AQUnavailableError("No raster for the requested hour") from exc

    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
        if any(not self.bounds.contains(point) for point in points):
            raise OutOfServiceAreaError("Point lies outside the pilot service area")
        with self._lock:
            rasters = self._hour(ts)
            if any(not rasters.manifest.bbox_wgs84.domain().contains(point) for point in points):
                raise AQUnavailableError("Point lies outside this raster's coverage")
            if not points:
                empty = np.empty(0, dtype=np.float64)
                return Pm25Samples(empty, empty, empty, ts, rasters.manifest.data_quality, "cog")
            x, y = project_points(points)
            rows, columns = rowcol(rasters.readers[0].transform, x, y)
            rows, columns = np.asarray(rows, dtype=int), np.asarray(columns, dtype=int)
            if (
                np.any(rows < 0)
                or np.any(columns < 0)
                or np.any(rows >= rasters.readers[0].height)
                or np.any(columns >= rasters.readers[0].width)
            ):
                raise AQUnavailableError("Requested cell is outside the raster grid")
            top, left = int(rows.min()), int(columns.min())
            window = Window(left, top, int(columns.max()) - left + 1, int(rows.max()) - top + 1)
            arrays: list[FloatArray] = []
            for reader in rasters.readers:
                try:
                    pixels = reader.read(1, window=window, masked=True)[rows - top, columns - left]
                except (OSError, rasterio.errors.RasterioError) as exc:
                    raise AQUnavailableError("Unable to read the requested raster window") from exc
                if np.any(np.ma.getmaskarray(pixels)):
                    raise AQUnavailableError("Requested raster cell has no data")
                arrays.append(np.asarray(pixels, dtype=np.float64))
            return Pm25Samples(
                arrays[0], arrays[1], arrays[2], hour_key(ts), rasters.manifest.data_quality, "cog"
            )

    def raster_median(self, ts: datetime) -> float:
        """Median of this raster extent; callers must not claim it covers the whole city."""
        with self._lock:
            key = hour_key(ts)
            if key not in self._medians:
                try:
                    pixels = self._hour(ts).readers[1].read(1, masked=True).compressed()
                except (OSError, rasterio.errors.RasterioError) as exc:
                    raise AQUnavailableError("Unable to read the raster reference window") from exc
                pixels = pixels[np.isfinite(pixels) & (pixels >= 0)]
                if not len(pixels):
                    raise AQUnavailableError("Raster has no valid values for a reference median")
                self._medians[key] = float(np.median(pixels))
            return self._medians[key]

    def close(self) -> None:
        with self._lock:
            self._stack.close()
            self._rasters.clear()
            self._medians.clear()


@dataclass(frozen=True, slots=True)
class StationSample:
    point: Point
    valid_hour: datetime
    pm25: Quantiles
    data_quality: DataQuality = "real"

    def __post_init__(self) -> None:
        object.__setattr__(self, "valid_hour", hour_key(self.valid_hour))
        if self.data_quality not in {"real", "approximated", "synthetic"}:
            raise ValueError("Invalid station data quality")
        values = (self.pm25.p10, self.pm25.p50, self.pm25.p90)
        if not all(math.isfinite(v) and v >= 0 for v in values) or list(values) != sorted(values):
            raise ValueError("Station concentrations must be finite ordered quantiles")


class IdwAQProvider:
    def __init__(
        self,
        stations: Sequence[StationSample],
        bounds: BoundingBox,
        *,
        cams: Mapping[datetime, Quantiles] | None = None,
        power: float = 2,
        allow_synthetic: bool = False,
    ) -> None:
        if not math.isfinite(power) or power <= 0:
            raise ValueError("IDW power must be positive")
        if any(s.data_quality == "synthetic" for s in stations) and not allow_synthetic:
            raise ValueError("Synthetic station inputs are forbidden in production")
        self.stations = tuple(stations)
        self.bounds = bounds
        self.cams = {hour_key(ts): value for ts, value in (cams or {}).items()}
        self.power = power

    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
        if any(not self.bounds.contains(point) for point in points):
            raise OutOfServiceAreaError("Point lies outside the pilot service area")
        key = hour_key(ts)
        stations = [station for station in self.stations if station.valid_hour == key]
        quality: DataQuality = (
            "synthetic" if any(s.data_quality == "synthetic" for s in stations) else "approximated"
        )
        if not stations:
            background = self.cams.get(key)
            if background is None:
                raise AQUnavailableError("No current station or sourced CAMS background")
            return Pm25Samples(
                np.full(len(points), background.p10, dtype=np.float64),
                np.full(len(points), background.p50, dtype=np.float64),
                np.full(len(points), background.p90, dtype=np.float64),
                key,
                "approximated",
                "cams",
            )
        sx, sy = project_points([s.point for s in stations])
        values = np.asarray([(s.pm25.p10, s.pm25.p50, s.pm25.p90) for s in stations])
        result = np.empty((len(points), 3), dtype=np.float64)
        px, py = project_points(points)
        for index, (x, y) in enumerate(zip(px, py, strict=True)):
            distances = np.hypot(sx - x, sy - y)
            exact = distances < 1e-6
            if np.any(exact):
                result[index] = values[exact].mean(axis=0)
            else:
                weights = (distances.min() / distances) ** self.power
                result[index] = np.sum(values * weights[:, None], axis=0) / weights.sum()
        return Pm25Samples(result[:, 0], result[:, 1], result[:, 2], key, quality, "idw")


class FallbackAQProvider:
    """Never automatically substitute a synthetic provider in production."""

    def __init__(self, primary: AQProvider, fallback: AQProvider) -> None:
        self.primary, self.fallback = primary, fallback

    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
        try:
            samples = self.primary.sample(points, ts)
            if samples.data_quality == "synthetic":
                raise AQUnavailableError("A production primary cannot use synthetic data")
            return samples
        except AQUnavailableError:
            samples = self.fallback.sample(points, ts)
            if samples.data_quality == "synthetic":
                raise AQUnavailableError(
                    "A production fallback cannot use synthetic data"
                ) from None
            return samples


class SyntheticAQProvider:
    """Deterministic mock quantiles for explicit test/demo use, never model metrics."""

    def __init__(self, min_pm25: float, max_pm25: float, *, seed: int = 20261013) -> None:
        if not (0 <= min_pm25 < max_pm25 and math.isfinite(max_pm25)):
            raise ValueError("Synthetic concentration bounds must be finite and ordered")
        self.min_pm25, self.max_pm25, self.seed = min_pm25, max_pm25, seed

    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
        key = hour_key(ts)
        x, y = project_points(points)
        result = np.empty((len(points), 3), dtype=np.float64)
        for index, (east, north) in enumerate(zip(x, y, strict=True)):
            cell = (math.floor(east / 100), math.floor(north / 100))
            digest = hashlib.sha256(f"{self.seed}|{cell}|{key.isoformat()}".encode()).digest()
            rng = np.random.default_rng(int.from_bytes(digest[:8]))
            result[index] = np.sort(rng.uniform(self.min_pm25, self.max_pm25, 3))
        return Pm25Samples(result[:, 0], result[:, 1], result[:, 2], key, "synthetic", "synthetic")
