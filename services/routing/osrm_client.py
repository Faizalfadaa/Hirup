"""Async OSRM adapter; no OD logging and no fabricated congestion multiplier."""

import math
from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta
from zoneinfo import ZoneInfo

import httpx

from services.exposure.engine import Mode
from services.routing.models import Candidate, Query, RouteLeg
from services.routing.polyline import decode


class OsrmClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        mode: Mode,
        *,
        congestion_hourly: Mapping[int, float] | None = None,
        timeout_s: float = 3,
    ) -> None:
        if mode not in {Mode.CAR, Mode.MOTORCYCLE}:
            raise ValueError("OSRM adapter mode must be CAR or MOTORCYCLE")
        if any(not math.isfinite(v) or v <= 0 for v in (congestion_hourly or {}).values()):
            raise ValueError("Congestion factors must be finite and positive")
        self.http, self.url, self.mode = http, base_url.rstrip("/"), mode
        self.congestion = dict(congestion_hourly or {})
        self.timeout_s = timeout_s

    async def candidates(self, query: Query) -> tuple[Candidate, ...]:
        coordinates = (
            f"{query.origin.lon},{query.origin.lat};{query.destination.lon},{query.destination.lat}"
        )
        try:
            response = await self.http.get(
                f"{self.url}/route/v1/driving/{coordinates}",
                params={"alternatives": "3", "overview": "full", "geometries": "polyline6"},
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                return ()
            if body.get("code") != "Ok":
                return ()
            result = []
            for raw in body["routes"]:
                factor = self.congestion.get(query.anchor.astimezone(ZoneInfo("Asia/Jakarta")).hour)
                duration, distance = float(raw["duration"]), float(raw["distance"])
                if not all(math.isfinite(v) and v >= 0 for v in (duration, distance)):
                    continue
                duration *= (
                    factor if factor is not None else 1
                )  # raw estimate, explicitly null factor
                points = decode(raw["geometry"])
                leg = RouteLeg(self.mode, duration, distance, points)
                start = (
                    query.anchor - timedelta(seconds=duration) if query.arrive_by else query.anchor
                )
                result.append(Candidate((leg,), start, "approximated", factor))
            # Arrival-based hour factors are recalculated from the estimated departure.
            if query.arrive_by:
                revised = []
                for item in result:
                    factor = self.congestion.get(
                        item.depart_at.astimezone(ZoneInfo("Asia/Jakarta")).hour
                    )
                    raw_duration = item.duration_s / (item.congestion_factor or 1)
                    duration = raw_duration * (factor if factor is not None else 1)
                    revised.append(
                        replace(
                            item,
                            legs=(replace(item.legs[0], duration_s=duration),),
                            depart_at=query.anchor - timedelta(seconds=duration),
                            congestion_factor=factor,
                        )
                    )
                result = revised
            return tuple(result)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return ()
