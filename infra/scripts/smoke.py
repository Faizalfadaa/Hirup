"""Require actual transit and road routes; print their raw engine durations."""

from __future__ import annotations

import argparse
import json
import math
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ORIGIN = (106.7741, -6.2893)
DESTINATION = (106.8229, -6.1917)


def request(url: str, payload: dict[str, object] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        body: object = json.load(response)
    if not isinstance(body, dict):
        raise ValueError("Expected a JSON object from the engine")
    return body


def positive_duration(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Engine duration is not a number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Engine duration must be finite and positive")
    return float(value)


def road_duration(body: dict[str, Any]) -> float:
    if body.get("code") != "Ok" or not body.get("routes"):
        raise ValueError(f"OSRM route failed: {body.get('code', 'missing code')}")
    return positive_duration(body["routes"][0].get("duration"))


def transit_duration(body: dict[str, Any]) -> float:
    if body.get("errors"):
        raise ValueError(f"OTP GraphQL error: {body['errors']}")
    plan = (body.get("data") or {}).get("plan") or {}
    itineraries = [
        it
        for it in plan.get("itineraries", [])
        if any(leg.get("transitLeg") for leg in it.get("legs", []))
    ]
    if not itineraries:
        raise ValueError(
            f"OTP has no transit itinerary: {plan.get('messageStrings', [])}"
        )
    return min(positive_duration(it.get("duration")) for it in itineraries)


def transit_payload(when: datetime) -> dict[str, object]:
    return {
        "query": """
          query Smoke($date: String!, $time: String!) {
            plan(from: {lat: -6.2893, lon: 106.7741},
                 to: {lat: -6.1917, lon: 106.8229},
                 date: $date, time: $time, numItineraries: 5,
                 transportModes: [{mode: WALK}, {mode: TRANSIT}]) {
              itineraries { duration legs { transitLeg mode } }
              messageStrings
            }
          }
        """,
        "variables": {
            "date": when.strftime("%Y-%m-%d"),
            "time": when.strftime("%H:%M:%S"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--departure", help="ISO timestamp with UTC offset; default tomorrow 08:00 WIB"
    )
    args = parser.parse_args()
    jakarta = ZoneInfo("Asia/Jakarta")
    when = (
        datetime.fromisoformat(args.departure)
        if args.departure
        else datetime.now(jakarta).replace(hour=8, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
    )
    if when.tzinfo is None:
        parser.error("--departure requires a UTC offset, e.g. +07:00")
    when = when.astimezone(jakarta)
    print(f"Lebak Bulus -> Bundaran HI; departure {when.isoformat()}")
    failed = False
    coordinates = f"{ORIGIN[0]},{ORIGIN[1]};{DESTINATION[0]},{DESTINATION[1]}"
    for label, host in (("OSRM car", "osrm-car"), ("OSRM motorcycle", "osrm-moto")):
        try:
            body = request(
                f"http://{host}:5000/route/v1/driving/{coordinates}"
                "?alternatives=3&overview=false"
            )
            duration = road_duration(body)
            print(
                f"{label}: {duration:.1f} s ({duration / 60:.2f} min); "
                f"alternatives={len(body['routes'])}; data_quality=approximated"
            )
        except (ValueError, OSError, urllib.error.URLError) as exc:
            print(f"FAIL {label}: {exc}")
            failed = True
    try:
        duration = transit_duration(
            request("http://otp:8080/otp/gtfs/v1", transit_payload(when))
        )
        print(
            f"OTP transit: {duration:.1f} s ({duration / 60:.2f} min); "
            "data_quality=real"
        )
    except (ValueError, OSError, urllib.error.URLError) as exc:
        print(f"FAIL OTP transit: {exc}")
        failed = True
    if failed:
        parser.exit(
            1, "Smoke failed; verify graph inputs, service dates, and engine logs.\n"
        )


if __name__ == "__main__":
    main()
