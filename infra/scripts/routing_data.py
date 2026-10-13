"""Validate routing inputs and stage independent GTFS feeds for OTP."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import shutil
import zipfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from pyproj import Geod

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Bounds:
    west: float = 106.76
    south: float = -6.30
    east: float = 106.85
    north: float = -6.13

    def contains(self, lon: float, lat: float) -> bool:
        return self.west <= lon <= self.east and self.south <= lat <= self.north

    def buffered(self, meters: float = 2000) -> Bounds:
        if not math.isfinite(meters) or meters < 0:
            raise ValueError("Buffer must be a finite non-negative distance")
        geod = Geod(ellps="WGS84")
        # Include both ends of each edge: the longitude offset varies with latitude.
        west = min(
            geod.fwd(self.west, lat, 270, meters)[0] for lat in (self.south, self.north)
        )
        east = max(
            geod.fwd(self.east, lat, 90, meters)[0] for lat in (self.south, self.north)
        )
        south = geod.fwd(self.west, self.south, 180, meters)[1]
        north = geod.fwd(self.west, self.north, 0, meters)[1]
        return Bounds(west, south, east, north)

    def osmium(self) -> str:
        return ",".join(f"{value:.8f}" for value in asdict(self).values())


class FeedError(ValueError):
    """An input feed fails the basic routing validation."""


def rows(archive: zipfile.ZipFile, table: str) -> Iterator[dict[str, str]]:
    candidates = [name for name in archive.namelist() if Path(name).name == table]
    if len(candidates) != 1:
        raise FeedError(f"Expected exactly one {table}, found {len(candidates)}")
    with archive.open(candidates[0]) as raw:
        with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise FeedError(f"Malformed CSV row in {table}")
                yield row


def gtfs_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise FeedError(f"Invalid GTFS date: {value!r}") from exc


def validate_feed(path: Path, bounds: Bounds | None = None) -> dict[str, object]:
    """Check geometry, essential tables, references, and timezone without I/O mocks."""
    bounds = bounds or Bounds()
    try:
        with zipfile.ZipFile(path) as archive:
            agencies = list(rows(archive, "agency.txt"))
            if not agencies or any(
                a.get("agency_timezone") != "Asia/Jakarta" for a in agencies
            ):
                raise FeedError("Every agency must use Asia/Jakarta")
            stops: set[str] = set()
            inside = 0
            for stop in rows(archive, "stops.txt"):
                stop_id = stop.get("stop_id", "")
                if not stop_id or stop_id in stops:
                    raise FeedError("Missing or duplicate stop_id")
                stops.add(stop_id)
                try:
                    lat, lon = float(stop["stop_lat"]), float(stop["stop_lon"])
                except (KeyError, ValueError) as exc:
                    raise FeedError(f"Invalid coordinates for stop {stop_id}") from exc
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise FeedError(f"Out-of-range coordinates for stop {stop_id}")
                inside += bounds.contains(lon, lat)
            if not inside:
                raise FeedError("No stops are inside the pilot bbox")

            shape_ids: set[str] = set()
            shape_points = 0
            for shape in rows(archive, "shapes.txt"):
                shape_id = shape.get("shape_id", "")
                try:
                    lat = float(shape["shape_pt_lat"])
                    lon = float(shape["shape_pt_lon"])
                    sequence = int(shape["shape_pt_sequence"])
                except (KeyError, ValueError) as exc:
                    raise FeedError("Invalid shape point") from exc
                if not shape_id or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise FeedError(
                        "Missing shape_id or out-of-range shape coordinates"
                    )
                if sequence < 0:
                    raise FeedError("Negative shape_pt_sequence")
                shape_ids.add(shape_id)
                shape_points += 1
            if not shape_points:
                raise FeedError("shapes.txt is empty")

            routes = {r.get("route_id", "") for r in rows(archive, "routes.txt")}
            if not routes or "" in routes:
                raise FeedError("Missing route_id or empty routes.txt")
            names = {Path(name).name for name in archive.namelist()}
            services: set[str] = set()
            dates: list[date] = []
            if "calendar.txt" in names:
                for calendar in rows(archive, "calendar.txt"):
                    services.add(calendar.get("service_id", ""))
                    start = gtfs_date(calendar.get("start_date", ""))
                    end = gtfs_date(calendar.get("end_date", ""))
                    if start > end:
                        raise FeedError("Calendar start is after its end")
                    dates.extend((start, end))
            if "calendar_dates.txt" in names:
                for calendar in rows(archive, "calendar_dates.txt"):
                    services.add(calendar.get("service_id", ""))
                    dates.append(gtfs_date(calendar.get("date", "")))
            if not services or "" in services:
                raise FeedError("Missing service calendars or service_id")

            trips: set[str] = set()
            for trip in rows(archive, "trips.txt"):
                trip_id = trip.get("trip_id", "")
                if not trip_id or trip_id in trips:
                    raise FeedError("Missing or duplicate trip_id")
                if trip.get("route_id") not in routes:
                    raise FeedError(f"Unknown route for trip {trip_id}")
                if trip.get("service_id") not in services:
                    raise FeedError(f"Unknown calendar for trip {trip_id}")
                if trip.get("shape_id") not in shape_ids:
                    raise FeedError(f"Missing or unknown shape for trip {trip_id}")
                trips.add(trip_id)
            if not trips:
                raise FeedError("trips.txt is empty")
            served: set[str] = set()
            for stop_time in rows(archive, "stop_times.txt"):
                if stop_time.get("stop_id") not in stops:
                    raise FeedError("stop_times.txt references an unknown stop")
                if stop_time.get("trip_id") not in trips:
                    raise FeedError("stop_times.txt references an unknown trip")
                served.add(stop_time["trip_id"])
            if served != trips:
                raise FeedError("Some trips have no stop times")
            return {
                "feed": path.name,
                "routes": len(routes),
                "trips": len(trips),
                "stops": len(stops),
                "stops_in_pilot": inside,
                "stops_outside_pilot": len(stops) - inside,
                "shapes": len(shape_ids),
                "shape_points": shape_points,
                "service_start": min(dates).isoformat(),
                "service_end": max(dates).isoformat(),
                "data_quality": "real",
            }
    except (zipfile.BadZipFile, UnicodeDecodeError) as exc:
        raise FeedError(f"Unreadable GTFS ZIP: {path.name}") from exc


def manual_feeds(root: Path) -> list[tuple[str, Path]]:
    """Find ZIPs or directories of GTFS tables without modifying P4's inputs."""
    directory = root / "data_prep/gtfs_manual"
    if not directory.exists():
        return []
    inputs = list(directory.rglob("*.zip"))
    inputs += [path.parent for path in directory.rglob("agency.txt")]
    found: list[tuple[str, Path]] = []
    used: set[str] = set()
    for path in sorted(inputs):
        relative = path.relative_to(directory)
        name = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(relative.with_suffix("")))
        name = f"manual-{name}.gtfs.zip"
        if name in used:
            raise FeedError(f"Manual feed names collide: {relative}")
        used.add(name)
        found.append((name, path))
    return found


def prepare_gtfs(root: Path = ROOT) -> list[dict[str, object]]:
    destination = root / "data/gtfs"
    destination.mkdir(parents=True, exist_ok=True)
    summaries = [validate_feed(destination / "transjakarta.gtfs.zip")]
    manual = manual_feeds(root)
    # Remove only our previous staged manual copies, never P4's source files.
    for previous in destination.glob("manual-*.gtfs.zip"):
        previous.unlink()
    for name, source in manual:
        output = destination / name
        if source.is_dir():
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for table in sorted(source.glob("*.txt")):
                    archive.write(table, table.name)
        else:
            shutil.copyfile(source, output)
        summary = validate_feed(output)
        # Manual timetables require P4 provenance before being called real data.
        summary["data_quality"] = "approximated"
        summaries.append(summary)
    if not manual:
        print("WARNING: MRT/LRT manual GTFS is absent; using TransJakarta only.")
    print(json.dumps(summaries, indent=2))
    return summaries


def stage(root: Path = ROOT) -> None:
    osm = root / "data/osm/pilot.osm.pbf"
    if not osm.is_file() or not osm.stat().st_size:
        raise FeedError("Missing pilot.osm.pbf; run data-routing first")
    prepare_gtfs(root)
    target = root / "data/otp"
    target.mkdir(parents=True, exist_ok=True)
    for previous in target.glob("*.gtfs.zip"):
        previous.unlink()
    feeds = sorted((root / "data/gtfs").glob("*.gtfs.zip"))
    for feed in feeds:
        shutil.copyfile(feed, target / feed.name)
    shutil.copyfile(osm, target / osm.name)
    for config in ("build-config.json", "router-config.json", "otp-config.json"):
        shutil.copyfile(root / "infra/otp" / config, target / config)
    build_path = target / "build-config.json"
    build_config = json.loads(build_path.read_text())
    build_config["transitFeeds"] = [
        {
            "type": "gtfs",
            "feedId": feed.name.removesuffix(".gtfs.zip"),
            "source": f"file:///var/opentripplanner/{feed.name}",
        }
        for feed in feeds
    ]
    build_path.write_text(json.dumps(build_config, indent=2) + "\n")
    print(f"Staged OTP inputs in {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bbox", "prepare-gtfs", "stage"))
    args = parser.parse_args()
    try:
        if args.action == "bbox":
            print(Bounds().buffered().osmium())
        elif args.action == "prepare-gtfs":
            prepare_gtfs()
        else:
            stage()
    except (FeedError, OSError) as exc:
        parser.exit(1, f"Routing input error: {exc}\n")


if __name__ == "__main__":
    main()
