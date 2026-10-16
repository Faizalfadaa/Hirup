"""`hirup-pipelines <command>`; run `hirup-pipelines --help` for the list."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, date, datetime, timedelta

from hirup_pipelines import tasks
from hirup_pipelines.ingest import osm

log = logging.getLogger("hirup_pipelines")


def _loop() -> None:
    """Poor man's cron: WAQI every 10 minutes, the hourly job once per hour (SPEC 9.4)."""
    last_hour = None
    while True:
        started = time.monotonic()
        now = datetime.now(UTC)
        try:
            if now.hour != last_hour:
                tasks.hourly()
                last_hour = now.hour
            else:
                tasks.ingest_waqi()
        except Exception:
            log.exception("pipeline step failed; retrying on the next tick")
        time.sleep(max(1.0, 600 - (time.monotonic() - started)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="hirup-pipelines", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stations", help="discover OpenAQ and WAQI stations (pilot area +/- 10 km)")
    history = sub.add_parser("openaq", help="fetch hourly OpenAQ history")
    history.add_argument("--days", type=int, default=30)
    sub.add_parser("waqi", help="scrape the latest WAQI readings once")
    meteo = sub.add_parser("weather", help="fetch Open-Meteo weather and CAMS")
    meteo.add_argument("--days", type=int, help="back-fill this many days from the archive")
    sub.add_parser("qc", help="QC, de-duplicate and calibrate into aq_observations")
    sub.add_parser("g0", help="evaluate gate G0 and write data/reports/g0.json")
    sub.add_parser("osm-index", help="(re)build the local OSM index from the Java extract")
    sub.add_parser("static", help="build static features and kelurahan for the pilot grid")
    sub.add_parser("station-static", help="build static features at station locations")
    sub.add_parser("hourly", help="run the hourly job once")
    sub.add_parser("loop", help="run forever: WAQI every 10 minutes, hourly job each hour")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    if args.command == "stations":
        found = tasks.discover_stations()
        print(found.groupby(["source", "type"]).size().to_string())
    elif args.command == "openaq":
        print(f"{tasks.ingest_openaq(args.days)} rows")
    elif args.command == "waqi":
        print(f"{tasks.ingest_waqi()} rows")
    elif args.command == "weather":
        if args.days:
            end = date.today() - timedelta(days=1)
            tasks.ingest_weather_and_cams(start=end - timedelta(days=args.days - 1), end=end)
        print(f"{tasks.ingest_weather_and_cams()} live rows")
    elif args.command == "qc":
        result = tasks.run_qc()
        print(result.observations["qc_flag"].value_counts().to_string())
    elif args.command == "g0":
        report = tasks.gate_g0()
        print(json.dumps({k: v for k, v in report.items() if k != "hours_per_station"}, indent=2))
    elif args.command == "osm-index":
        print(json.dumps(osm.build_index(), indent=2))
    elif args.command == "static":
        print(f"{tasks.build_static()} cells")
    elif args.command == "station-static":
        print(f"{tasks.build_station_static()} stations")
    elif args.command == "hourly":
        tasks.hourly()
    elif args.command == "loop":
        _loop()


if __name__ == "__main__":
    main()
