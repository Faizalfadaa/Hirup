"""AQ point/tile edge, including explicit demo rendering and pre-rendered P2 tiles."""

import math
import struct
import zlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from services.exposure.aq_provider import (
    AQProvider,
    AQUnavailableError,
    DataQuality,
    OutOfServiceAreaError,
    Pm25Samples,
)
from services.exposure.geometry import BoundingBox, Point, hour_key, project_points


def png_rgba(pixels: np.ndarray[tuple[int, int, int], np.dtype[np.uint8]]) -> bytes:
    height, width, _ = pixels.shape

    def chunk(name: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data)) + name + data + struct.pack("!I", zlib.crc32(name + data))
        )

    rows = b"".join(b"\x00" + row.tobytes() for row in pixels)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class AQService:
    def __init__(
        self,
        provider: AQProvider,
        bounds: BoundingBox,
        *,
        tiles_dir: Path | None = None,
        demo_range: tuple[float, float] | None = None,
    ) -> None:
        self.provider, self.bounds, self.tiles_dir, self.demo_range = (
            provider,
            bounds,
            tiles_dir,
            demo_range,
        )
        self.tiles_available = True

    def point(self, point: Point, ts: datetime) -> Pm25Samples:
        if not self.bounds.contains(point):
            raise OutOfServiceAreaError("Point is outside the pilot service area")
        samples = self.provider.sample([point], ts)
        if len(samples.p50) != 1 or samples.valid_hour != hour_key(ts):
            raise AQUnavailableError("AQ sample hour/count differs from the point request")
        return samples

    def tile(self, z: int, x: int, y: int, ts: datetime) -> tuple[bytes, DataQuality]:
        if not 0 <= z <= 20 or not 0 <= x < 2**z or not 0 <= y < 2**z:
            raise ValueError("Tile indices are outside the zoom range")
        n = 2**z
        north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
        west, east = x / n * 360 - 180, (x + 1) / n * 360 - 180
        if (
            north < self.bounds.min_lat
            or south > self.bounds.max_lat
            or east < self.bounds.min_lon
            or west > self.bounds.max_lon
        ):
            raise OutOfServiceAreaError("Tile is outside the pilot service area")
        if self.demo_range is None:
            if not self.tiles_available:
                raise AQUnavailableError("Tile categories are awaiting source verification")
            if self.tiles_dir is None:
                raise AQUnavailableError("No sourced pre-rendered AQ tiles are configured")
            local = ts.astimezone(ZoneInfo("Asia/Jakarta"))
            path = self.tiles_dir / local.strftime("%Y%m%d%H") / str(z) / str(x) / f"{y}.png"
            if not path.resolve().is_relative_to(self.tiles_dir.resolve()):
                raise AQUnavailableError("Tile path leaves its configured directory")
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise AQUnavailableError("No sourced tile for this hour") from exc
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise AQUnavailableError("Invalid pre-rendered PNG")
            # Read the corresponding raster quality; never silently claim a real tile.
            representative = self.bounds.clamp(Point((west + east) / 2, (north + south) / 2))
            quality = self.point(representative, ts).data_quality
            if quality == "synthetic":
                raise AQUnavailableError("Synthetic tiles are forbidden in production")
            return data, quality
        # Demo only: a continuous grey concentration scale, never an invented ISPU threshold.
        pixels = np.zeros((256, 256, 4), dtype=np.uint8)
        col, row = np.meshgrid(np.arange(256) + 0.5, np.arange(256) + 0.5)
        lon = ((x + col / 256) / n) * 360 - 180
        lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + row / 256) / n))))
        mask = (
            (lon >= self.bounds.min_lon)
            & (lon <= self.bounds.max_lon)
            & (lat >= self.bounds.min_lat)
            & (lat <= self.bounds.max_lat)
        )
        points = [Point(float(a), float(b)) for a, b in zip(lon[mask], lat[mask], strict=True)]
        if points:
            px, py = project_points(points)
            cells = np.column_stack((np.floor(px / 100), np.floor(py / 100)))
            _, first, inverse = np.unique(cells, axis=0, return_index=True, return_inverse=True)
            samples = self.provider.sample([points[int(i)] for i in first], ts)
            low, high = self.demo_range
            values = np.clip((samples.p50[inverse] - low) / (high - low), 0, 1)
            colors = np.round(255 * (1 - values)).astype(np.uint8)
            pixels[mask] = np.column_stack((colors, colors, colors, np.full(len(colors), 180)))
        return png_rgba(pixels), "synthetic"
