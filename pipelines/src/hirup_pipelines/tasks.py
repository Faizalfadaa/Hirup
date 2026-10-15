"""Pipeline steps. Each step logs to `ingest_runs.parquet` and stops on a failed schema check."""

from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any

import duckdb
import pandas as pd

from hirup_pipelines import clean, paths, schemas, store
from hirup_pipelines.features import build
from hirup_pipelines.http import Client, HttpError
from hirup_pipelines.ingest import openaq, openmeteo, waqi
from hirup_pipelines.settings import load_config, pilot_bbox

log = logging.getLogger(__name__)
RAW_KEYS = ["station_id", "ts"]


def station_area() -> Any:
    return pilot_bbox().expand_km(float(load_config()["stations"]["buffer_km"]))


def discover_stations() -> pd.DataFrame:
    """Stations within the pilot area +/- 10 km from every source that has a key configured."""
    frames = []
    with store.log_run("stations") as run:
        if os.environ.get("OPENAQ_API_KEY"):
            with openaq.client() as http:
                frames.append(openaq.fetch_stations(http, station_area()))
        else:
            log.warning("OPENAQ_API_KEY not set; skipping OpenAQ station discovery")
        if os.environ.get("WAQI_TOKEN"):
            with waqi.client() as http:
                frames.append(waqi.fetch_stations(http, station_area()))
        else:
            log.warning("WAQI_TOKEN not set; skipping WAQI station discovery")
        frames = [frame for frame in frames if len(frame)]
        if not frames:
            raise RuntimeError("No stations found: set OPENAQ_API_KEY and/or WAQI_TOKEN")
        found = schemas.validate(pd.concat(frames, ignore_index=True), schemas.STATIONS)
        merged = store.upsert(found, paths.raw_stations(), ["station_id"])
        run.rows = len(found)
    return merged


def _last_seen() -> dict[str, pd.Timestamp]:
    root = paths.raw_observations()
    if not any(root.glob("date=*/part.parquet")):
        return {}
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'UTC'")
        rows = con.execute(
            "SELECT station_id, max(ts) FROM read_parquet(?) GROUP BY 1",
            [(root / "date=*" / "part.parquet").as_posix()],
        ).fetchall()
    return {station: pd.Timestamp(ts).tz_convert("UTC") for station, ts in rows}


def _window(value: Any) -> datetime | None:
    stamp = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(stamp) else stamp.to_pydatetime()


def ingest_openaq(days: int, chunk_days: int = 90) -> int:
    """Hourly history for every OpenAQ station, resuming from what is already stored.

    Requests are split into `chunk_days` windows (long ranges time out on OpenAQ) and
    clamped to the period each location reported. A station that keeps failing is logged
    and skipped so one bad sensor does not stop the others; rerunning resumes it.
    """
    stations = store.read_parquet(paths.raw_stations())
    if stations is None:
        raise RuntimeError("Run `hirup-pipelines stations` first")
    stations = stations[stations["source"] == "openaq"]
    now = datetime.now(UTC)
    floor = now - timedelta(days=days)
    seen = _last_seen()
    failed: list[str] = []
    with store.log_run("openaq") as run, openaq.client() as http:
        for station in stations.itertuples(index=False):
            last = seen.get(station.station_id)
            start = max(floor, _window(station.first_seen) or floor)
            if last is not None:
                start = max(start, (last - timedelta(hours=3)).to_pydatetime())
            reported = _window(station.last_seen)
            end = min(now, reported + timedelta(hours=1)) if reported else now
            cursor = start
            while cursor < end:
                stop = min(end, cursor + timedelta(days=chunk_days))
                try:
                    frame = openaq.fetch_hours(
                        http, station.station_id, int(station.sensor_id), cursor, stop
                    )
                except HttpError as exc:
                    log.warning("OpenAQ %s skipped: %s", station.station_id, exc)
                    failed.append(station.station_id)
                    break
                frame = schemas.validate(frame, schemas.RAW_OBSERVATIONS)
                run.rows += store.write_daily(frame, paths.raw_observations(), RAW_KEYS)
                cursor = stop
        if failed:
            log.warning("OpenAQ stations to retry: %s", ", ".join(failed))
        return run.rows


def ingest_waqi() -> int:
    """One scrape of the latest WAQI reading per station (SPEC 9.4: every 10 minutes)."""
    stations = store.read_parquet(paths.raw_stations())
    if stations is None:
        raise RuntimeError("Run `hirup-pipelines stations` first")
    ids = stations.loc[stations["source"] == "waqi", "station_id"].tolist()
    with store.log_run("waqi") as run, waqi.client() as http:
        frame = schemas.validate(waqi.fetch_latest(http, ids), schemas.RAW_OBSERVATIONS)
        run.rows = store.write_daily(frame, paths.raw_observations(), RAW_KEYS)
        return run.rows


def _chunks(start: date, end: date, days: int = 60) -> list[tuple[date, date]]:
    out, cursor = [], start
    while cursor <= end:
        stop = min(end, cursor + timedelta(days=days - 1))
        out.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return out


def ingest_weather_and_cams(
    *, start: date | None = None, end: date | None = None, past_days: int = 2
) -> int:
    """Weather and CAMS on the lattice. With dates: archive back-fill. Without: live + forecast."""
    cfg = load_config()["open_meteo"]
    points = openmeteo.lattice(pilot_bbox())
    keys = ["cell_group_id", "ts"]
    rows = 0
    with Client(min_interval_s=0.5) as http:
        with store.log_run("open_meteo_weather") as run:
            if start is not None and end is not None:
                frames = [
                    openmeteo.fetch_weather(http, points, start=a, end=b)
                    for a, b in _chunks(start, end)
                ]
            else:
                frames = [
                    openmeteo.fetch_weather(
                        http, points, past_days=past_days, forecast_days=int(cfg["forecast_days"])
                    )
                ]
            weather = schemas.validate(pd.concat(frames, ignore_index=True), schemas.WEATHER_HOURLY)
            store.upsert(weather, paths.weather(), keys)
            run.rows = len(weather)
            rows += run.rows
        with store.log_run("open_meteo_cams") as run:
            if start is not None and end is not None:
                frames = [
                    openmeteo.fetch_cams(http, points, start=a, end=b)
                    for a, b in _chunks(start, end)
                ]
            else:
                frames = [
                    openmeteo.fetch_cams(
                        http, points, past_days=past_days, forecast_days=int(cfg["forecast_days"])
                    )
                ]
            cams = schemas.validate(pd.concat(frames, ignore_index=True), schemas.CAMS_HOURLY)
            store.upsert(cams, paths.cams(), keys)
            run.rows = len(cams)
            rows += run.rows
    return rows


def run_qc() -> clean.Cleaned:
    """Rebuild `aq_observations` and `stations` from the raw tables (idempotent)."""
    with store.log_run("qc") as run:
        raw = store.read_daily(paths.raw_observations())
        stations = store.read_parquet(paths.raw_stations())
        if raw.empty or stations is None:
            raise RuntimeError("No raw observations yet: ingest OpenAQ or WAQI first")
        weather = store.read_parquet(paths.weather())
        version = f"calibration_v{date.today().isoformat()}"
        result = clean.clean(
            raw[["station_id", "ts", "value_raw", "source"]],
            stations,
            weather if weather is not None else pd.DataFrame(),
            version,
        )
        store.write_daily(result.observations, paths.observations(), RAW_KEYS, replace=True)
        store.write_parquet(schemas.validate(result.stations, schemas.STATIONS), paths.stations())
        store.write_json(result.calibration.to_json(), paths.reports() / "calibration.json")
        store.write_json(
            result.duplicates.to_dict(orient="records"), paths.reports() / "duplicates.json"
        )
        run.rows = len(result.observations)
    return result


def gate_g0() -> dict[str, Any]:
    """Gate G0 (SPEC 10.1): enough stations with at least seven days of hourly data?"""
    cfg = load_config()["g0"]
    stations = store.read_parquet(paths.stations())
    counts: dict[str, int] = {}
    if any(paths.observations().glob("date=*/part.parquet")):
        with duckdb.connect() as con:
            rows = con.execute(
                "SELECT station_id, count(*) FROM read_parquet(?) WHERE qc_flag = 'ok' GROUP BY 1",
                [(paths.observations() / "date=*" / "part.parquet").as_posix()],
            ).fetchall()
        counts = {station: int(n) for station, n in rows}
    active = (
        set()
        if stations is None
        else set(stations.loc[stations["merged_into"].isna(), "station_id"])
    )
    qualifying = sorted(s for s, n in counts.items() if n >= cfg["min_hours"] and s in active)
    in_pilot = 0
    if stations is not None:
        box = pilot_bbox()
        inside = stations[stations["station_id"].isin(qualifying)]
        in_pilot = int(
            sum(
                box.contains(lat, lon)
                for lat, lon in zip(inside["lat"], inside["lon"], strict=True)
            )
        )
    passed = len(qualifying) >= cfg["min_stations"]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "criterion": f">= {cfg['min_stations']} stations with >= {cfg['min_hours']} QC-ok hours",
        "area": f"pilot bbox +/- {load_config()['stations']['buffer_km']} km",
        "stations_total": len(active),
        "stations_qualifying": len(qualifying),
        "stations_qualifying_in_pilot": in_pilot,
        "hours_per_station": dict(sorted(counts.items())),
        "passed": passed,
        "decision": (
            "LightGBM nowcast is the main model"
            if passed
            else "Main model is IDW + CAMS + static features; focus innovation on routing (SPEC 18)"
        ),
    }
    store.write_json(report, paths.reports() / "g0.json")
    return report


def build_static() -> int:
    with store.log_run("static_features") as run:
        run.rows = len(build.build_grid_static())
        return run.rows


def build_station_static() -> int:
    stations = store.read_parquet(paths.stations())
    if stations is None:
        raise RuntimeError("Run `hirup-pipelines qc` first")
    with store.log_run("station_static_features") as run:
        run.rows = len(build.build_station_static(stations[stations["merged_into"].isna()]))
        return run.rows


def hourly() -> None:
    """The hourly job (SPEC 9.4 step 1). Sources without a key are skipped with a warning."""
    if os.environ.get("WAQI_TOKEN") and paths.raw_stations().is_file():
        ingest_waqi()
    if os.environ.get("OPENAQ_API_KEY") and paths.raw_stations().is_file():
        ingest_openaq(days=2)
    ingest_weather_and_cams()
    if any(paths.raw_observations().glob("date=*/part.parquet")):
        run_qc()
