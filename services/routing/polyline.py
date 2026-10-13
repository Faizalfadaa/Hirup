"""Encoded polyline precision 6 at the API edge; OTP's legacy geometry uses 5."""

from collections.abc import Sequence

from services.exposure.geometry import Point


def encode(points: Sequence[Point], precision: int = 6) -> str:
    result: list[str] = []
    previous = (0, 0)
    for point in points:
        current = (round(point.lat * 10**precision), round(point.lon * 10**precision))
        for value, prior in zip(current, previous, strict=True):
            delta = value - prior
            chunk = ~(delta << 1) if delta < 0 else delta << 1
            while chunk >= 0x20:
                result.append(chr((0x20 | (chunk & 0x1F)) + 63))
                chunk >>= 5
            result.append(chr(chunk + 63))
        previous = current
    return "".join(result)


def decode(value: str, precision: int = 6) -> tuple[Point, ...]:
    position, lat, lon = 0, 0, 0
    points: list[Point] = []
    while position < len(value):
        deltas = []
        for _ in range(2):
            result, shift = 0, 0
            while True:
                if position >= len(value) or shift > 30:
                    raise ValueError("Invalid encoded polyline")
                chunk = ord(value[position]) - 63
                position += 1
                if not 0 <= chunk <= 63:
                    raise ValueError("Invalid encoded polyline character")
                result |= (chunk & 0x1F) << shift
                shift += 5
                if chunk < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append(Point(lon / 10**precision, lat / 10**precision))
    if not points:
        raise ValueError("Encoded polyline has no points")
    return tuple(points)
