"""Read expected headways from the actual imported GTFS, never from a dummy constant."""

import csv
import io
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo


def seconds(value: str) -> int:
    h, m, s = (int(p) for p in value.split(":"))
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError("Invalid GTFS time")
    return h * 3600 + m * 60 + s


class GtfsHeadways:
    def __init__(self, feeds: dict[str, Path]) -> None:
        self.trips: dict[tuple[str, str], tuple[str, str, str]] = {}
        self.transport_modes: set[str] = set()
        self.departures: dict[tuple[str, str, str, str], list[tuple[str, int]]] = defaultdict(list)
        self.frequencies: dict[tuple[str, str], list[tuple[int, int, int]]] = defaultdict(list)
        self.calendars: dict[tuple[str, str], dict[str, str]] = {}
        self.exceptions: dict[tuple[str, str, date], bool] = {}
        self.trip_stops: dict[tuple[str, str, str], int] = {}
        self.first_departures: dict[tuple[str, str], int] = {}
        self._schedule_cache: dict[tuple[str, str, str, str, date], tuple[int, ...]] = {}
        for feed, path in feeds.items():
            with zipfile.ZipFile(path) as archive:

                def rows(name: str) -> list[dict[str, str]]:
                    if name not in archive.namelist():
                        return []
                    with (
                        archive.open(name) as raw,
                        io.TextIOWrapper(raw, encoding="utf-8-sig") as stream,
                    ):
                        return list(csv.DictReader(stream))

                for row in rows("routes.txt"):
                    kind = int(row["route_type"])
                    if kind == 3 or 700 <= kind < 800:
                        self.transport_modes.add("BUS")
                    elif kind == 1 or 400 <= kind < 500:
                        self.transport_modes.add("SUBWAY")
                    elif kind == 2 or 100 <= kind < 200:
                        self.transport_modes.add("RAIL")
                    elif kind == 0 or 900 <= kind < 1000:
                        self.transport_modes.add("TRAM")
                for row in rows("trips.txt"):
                    self.trips[feed, row["trip_id"]] = (
                        row["route_id"],
                        row["service_id"],
                        row.get("direction_id", ""),
                    )
                for row in rows("stop_times.txt"):
                    trip = self.trips.get((feed, row["trip_id"]))
                    if trip is not None and row.get("departure_time"):
                        route, service, direction = trip
                        departure = seconds(row["departure_time"])
                        stop_key = (feed, row["trip_id"], row["stop_id"])
                        self.trip_stops[stop_key] = min(
                            self.trip_stops.get(stop_key, departure), departure
                        )
                        trip_key = (feed, row["trip_id"])
                        self.first_departures[trip_key] = min(
                            self.first_departures.get(trip_key, departure), departure
                        )
                        self.departures[feed, route, row["stop_id"], direction].append(
                            (service, seconds(row["departure_time"]))
                        )
                for row in rows("frequencies.txt"):
                    headway = int(row["headway_secs"])
                    if headway > 0:
                        self.frequencies[feed, row["trip_id"]].append(
                            (seconds(row["start_time"]), seconds(row["end_time"]), headway)
                        )
                for row in rows("calendar.txt"):
                    self.calendars[feed, row["service_id"]] = row
                for row in rows("calendar_dates.txt"):
                    day = datetime.strptime(row["date"], "%Y%m%d").date()
                    self.exceptions[feed, row["service_id"], day] = row["exception_type"] == "1"

    def active(self, feed: str, service: str, day: date) -> bool:
        override = self.exceptions.get((feed, service, day))
        if override is not None:
            return override
        calendar = self.calendars.get((feed, service))
        if calendar is None:
            return False
        weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[
            day.weekday()
        ]
        return (
            calendar["start_date"] <= day.strftime("%Y%m%d") <= calendar["end_date"]
            and calendar[weekday] == "1"
        )

    def _times(
        self, feed: str, route: str, stop: str, direction: str, day: date
    ) -> tuple[int, ...]:
        key = (feed, route, stop, direction, day)
        if key in self._schedule_cache:
            return self._schedule_cache[key]
        result = tuple(
            sorted(
                {
                    time
                    for service, time in self.departures.get((feed, route, stop, direction), [])
                    if self.active(feed, service, day)
                }
            )
        )
        if len(self._schedule_cache) >= 4096:
            self._schedule_cache.pop(next(iter(self._schedule_cache)))
        self._schedule_cache[key] = result
        return result

    def headway(self, trip_id: str, stop_id: str, ts: datetime) -> float | None:
        if ":" not in trip_id or ":" not in stop_id:
            return None
        feed, trip = trip_id.split(":", 1)
        stop_feed, stop = stop_id.split(":", 1)
        meta = self.trips.get((feed, trip))
        if meta is None or stop_feed != feed:
            return None
        local = ts.astimezone(ZoneInfo("Asia/Jakarta"))
        clock = local.hour * 3600 + local.minute * 60 + local.second
        route, service, direction = meta
        active_days = []
        offset = self.trip_stops.get((feed, trip, stop), 0) - self.first_departures.get(
            (feed, trip), 0
        )
        for shift in (0, -1):
            day = local.date() + timedelta(days=shift)
            relative_clock = clock - shift * 86400
            if not self.active(feed, service, day):
                continue
            active_days.append((day, relative_clock))
            for start, end, headway in self.frequencies.get((feed, trip), []):
                if start <= relative_clock - offset < end:
                    return float(headway)
        for day, relative_clock in active_days:
            times = self._times(feed, route, stop, direction, day)
            if len(times) >= 2 and times[0] <= relative_clock <= times[-1]:
                # Use the interval containing boarding, otherwise nearest observed interval.
                pairs = list(pairwise(times))
                a, b = min(
                    pairs,
                    key=lambda pair: max(pair[0] - relative_clock, relative_clock - pair[1], 0),
                )
                return float(b - a)
        return None
