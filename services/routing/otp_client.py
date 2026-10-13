"""Async OTP 2 legacy GTFS GraphQL adapter, isolated behind a small interface."""

import asyncio
import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from services.exposure.engine import Mode
from services.exposure.geometry import Point
from services.routing.models import Candidate, Query, RouteLeg, TransitInfo
from services.routing.polyline import decode

QUERY = """
query Plan($from: InputCoordinates!, $to: InputCoordinates!, $date: String!,
           $time: String!, $arrive: Boolean!, $reluctance: Float!, $modes: [TransportMode]!,
           $window: Long!) {
  plan(from: $from, to: $to, date: $date, time: $time, arriveBy: $arrive,
       walkReluctance: $reluctance, transportModes: $modes, numItineraries: 5,
       searchWindow: $window) {
    itineraries { startTime legs {
      mode transitLeg duration distance startTime endTime
      from { name lat lon stop { gtfsId } } to { name lat lon }
      legGeometry { points }
      route { gtfsId shortName longName agency { name } }
      trip { gtfsId }
    } }
  }
}
"""


def epoch_ms(value: Any) -> datetime:
    return datetime.fromtimestamp(float(value) / 1000, ZoneInfo("Asia/Jakarta"))


def parse_itinerary(raw: dict[str, Any], query: Query) -> Candidate:
    legs = []
    for leg in raw["legs"]:
        mode = Mode.RAIL if leg["mode"] == "TRAM" else Mode(leg["mode"])
        a, b = leg["from"], leg["to"]
        geometry = leg.get("legGeometry") or {}
        points = (
            decode(geometry["points"], 5)
            if geometry.get("points")
            else (Point(float(a["lon"]), float(a["lat"])), Point(float(b["lon"]), float(b["lat"])))
        )
        route = leg.get("route")
        info = (
            TransitInfo(
                route["gtfsId"],
                route.get("shortName"),
                route.get("longName"),
                (route.get("agency") or {}).get("name"),
            )
            if route
            else None
        )
        duration, distance = float(leg["duration"]), float(leg.get("distance", 0))
        if not all(math.isfinite(v) and v >= 0 for v in (duration, distance)):
            raise ValueError("Invalid OTP leg measures")
        legs.append(
            RouteLeg(
                mode,
                duration,
                distance,
                points,
                a["name"],
                b["name"],
                info,
                (leg.get("trip") or {}).get("gtfsId"),
                (a.get("stop") or {}).get("gtfsId"),
                epoch_ms(leg["startTime"]),
            )
        )
    if not legs or not any(leg.route is not None for leg in legs):
        raise ValueError("OTP returned no actual transit leg")
    if any(leg.mode in query.excluded_modes for leg in legs):
        raise ValueError("OTP returned an excluded mode")
    if any(leg.mode == Mode.WALK and leg.distance_m > query.max_walk_m for leg in legs):
        raise ValueError("OTP returned walking beyond the requested limit")
    return Candidate(tuple(legs), epoch_ms(raw["startTime"]), "approximated")


class OtpClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        url: str,
        *,
        timeout_s: float = 3.2,
        available_modes: set[str] | None = None,
    ) -> None:
        self.http, self.url, self.timeout_s = http, url, timeout_s
        self.search_window_s = (
            1800  # Search strategy: departures within 30 min, not an exposure constant.
        )
        self.available_modes = available_modes

    async def _variant(
        self, query: Query, reluctance: float, modes: tuple[str, ...]
    ) -> tuple[Candidate, ...]:
        local = query.anchor.astimezone(ZoneInfo("Asia/Jakarta"))
        variables = {
            "from": {"lat": query.origin.lat, "lon": query.origin.lon},
            "to": {"lat": query.destination.lat, "lon": query.destination.lon},
            "date": local.strftime("%Y-%m-%d"),
            "time": local.strftime("%H:%M:%S"),
            "arrive": query.arrive_by,
            "window": self.search_window_s,
            "reluctance": reluctance,
            "modes": [{"mode": mode} for mode in ("WALK", *modes)],
        }
        try:
            response = await self.http.post(
                self.url, json={"query": QUERY, "variables": variables}, timeout=self.timeout_s
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
                return ()
            if body.get("errors"):
                return ()
            plan = body["data"].get("plan")
            if not isinstance(plan, dict) or not isinstance(plan.get("itineraries"), list):
                return ()
            result = []
            for itinerary in plan["itineraries"]:
                try:
                    result.append(parse_itinerary(itinerary, query))
                except (KeyError, ValueError, TypeError, OverflowError):
                    continue
            return tuple(result)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return ()

    async def candidates(self, query: Query) -> tuple[Candidate, ...]:
        mode_sets = [("TRANSIT",), ("SUBWAY", "RAIL", "TRAM"), ("BUS",)]
        if self.available_modes is not None:
            # Bus-only GTFS makes rail-first empty and all equivalent to bus-only.
            normalized = []
            for modes in mode_sets:
                available = (
                    tuple(sorted(self.available_modes))
                    if modes == ("TRANSIT",)
                    else tuple(mode for mode in modes if mode in self.available_modes)
                )
                if available and available not in normalized:
                    normalized.append(available)
            mode_sets = normalized
        variants = await asyncio.gather(
            *(
                self._variant(query, reluctance, modes)
                for reluctance in (1.5, 3, 6)
                for modes in mode_sets
            )
        )
        unique: dict[tuple[object, ...], Candidate] = {}
        for candidate in (item for batch in variants for item in batch):
            key = tuple(
                (
                    leg.route.id if leg.route else leg.mode,
                    leg.points[0],
                    leg.points[-1],
                )
                for leg in candidate.legs
            )
            if key not in unique or candidate.duration_s < unique[key].duration_s:
                unique[key] = candidate
        return tuple(unique.values())
