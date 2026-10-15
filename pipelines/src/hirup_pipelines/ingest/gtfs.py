"""TransJakarta GTFS shapes with weekday trips per hour (SPEC 11.2 "Transit" features)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from hirup_pipelines.grid import CRS
from hirup_pipelines.ingest.rasters import download
from hirup_pipelines.settings import data_dir, load_config


def feed_path() -> Path:
    """Same location and cache rule as `infra/scripts/fetch_gtfs.sh`."""
    target = data_dir() / "gtfs" / "transjakarta.gtfs.zip"
    return download(load_config()["gtfs"]["transjakarta_url"], target)


def _seconds(value: str) -> int:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _table(archive: zipfile.ZipFile, name: str) -> pd.DataFrame:
    if name not in archive.namelist():
        return pd.DataFrame()
    with archive.open(name) as raw:
        return pd.read_csv(io.TextIOWrapper(raw, encoding="utf-8-sig"), dtype=str).fillna("")


def load_shapes(path: Path | None = None) -> gpd.GeoDataFrame:
    """One line per shape with `trips_per_hour` (weekday mean) and `is_brt`."""
    cfg = load_config()["gtfs"]
    first, last = (int(v) * 3600 for v in cfg["weekday_service_hours"])
    with zipfile.ZipFile(path or feed_path()) as archive:
        routes, trips = _table(archive, "routes.txt"), _table(archive, "trips.txt")
        calendar, shapes = _table(archive, "calendar.txt"), _table(archive, "shapes.txt")
        frequencies, stop_times = (
            _table(archive, "frequencies.txt"),
            _table(archive, "stop_times.txt"),
        )
    weekday = (
        set(calendar.loc[calendar["wednesday"] == "1", "service_id"]) if len(calendar) else set()
    )
    trips = trips[trips["service_id"].isin(weekday) & trips["shape_id"].ne("")]
    # Trips in the window: headway-based trips run (overlap / headway) times, the rest once.
    runs = pd.Series(0.0, index=trips["trip_id"].unique())
    headway_trips: set[str] = set()
    for row in frequencies.itertuples(index=False):
        headway = int(row.headway_secs)
        if headway <= 0 or row.trip_id not in runs.index:
            continue
        headway_trips.add(row.trip_id)
        overlap = min(last, _seconds(row.end_time)) - max(first, _seconds(row.start_time))
        runs[row.trip_id] += max(0, overlap) / headway
    if len(stop_times):
        starts = stop_times[stop_times["departure_time"].ne("")].groupby("trip_id")[
            "departure_time"
        ]
        for trip_id, start in starts.min().map(_seconds).items():
            if trip_id in runs.index and trip_id not in headway_trips and first <= start < last:
                runs[trip_id] += 1.0
    trips = trips.assign(runs=trips["trip_id"].map(runs))
    brt_routes = set(routes.loc[routes["route_desc"] == cfg["brt_route_desc"], "route_id"])
    per_shape = trips.groupby("shape_id").agg(
        runs=("runs", "sum"), is_brt=("route_id", lambda ids: bool(set(ids) & brt_routes))
    )
    shapes = shapes.astype({"shape_pt_sequence": int, "shape_pt_lat": float, "shape_pt_lon": float})
    lines = (
        shapes.sort_values(["shape_id", "shape_pt_sequence"])
        .groupby("shape_id")[["shape_pt_lon", "shape_pt_lat"]]
        .apply(lambda pts: LineString(pts.to_numpy()) if len(pts) >= 2 else None)
        .dropna()
    )
    frame = gpd.GeoDataFrame(
        per_shape.join(lines.rename("geometry"), how="inner"), geometry="geometry", crs="EPSG:4326"
    ).to_crs(CRS)
    frame["trips_per_hour"] = frame.pop("runs") / ((last - first) / 3600)
    return frame.reset_index()
