"""OpenAQ API v3: station discovery and hourly PM2.5 history (SPEC 10.1, primary labels)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from hirup_pipelines.http import Client
from hirup_pipelines.settings import BBox, load_config, require_env


def client(api_key: str | None = None, **kwargs: Any) -> Client:
    cfg = load_config()["openaq"]
    return Client(
        min_interval_s=float(cfg["min_interval_s"]),
        headers={"X-API-Key": api_key or require_env("OPENAQ_API_KEY")},
        **kwargs,
    )


def _pages(http: Client, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    limit = int(load_config()["openaq"]["page_limit"])
    results: list[dict[str, Any]] = []
    page = 1
    while True:
        body = http.get_json(url, params={**params, "limit": limit, "page": page})
        batch = body.get("results", [])
        results.extend(batch)
        if len(batch) < limit:
            return results
        page += 1


def fetch_stations(http: Client, bbox: BBox) -> pd.DataFrame:
    """Locations in `bbox` that have a PM2.5 sensor, one row per sensor."""
    cfg = load_config()["openaq"]
    locations = _pages(
        http,
        f"{cfg['base_url']}/locations",
        {"bbox": f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}"},
    )
    rows = []
    for location in locations:
        if location.get("isMobile"):
            continue
        coordinates = location.get("coordinates") or {}
        if coordinates.get("latitude") is None or coordinates.get("longitude") is None:
            continue
        for sensor in location.get("sensors", []):
            if (sensor.get("parameter") or {}).get("name") != cfg["parameter"]:
                continue
            rows.append(
                {
                    "station_id": f"openaq:{location['id']}",
                    "name": location.get("name"),
                    # OpenAQ marks regulatory-grade monitors with isMonitor.
                    "type": "reference" if location.get("isMonitor") else "lcs",
                    "source": "openaq",
                    "provider": (location.get("provider") or {}).get("name"),
                    "lat": float(coordinates["latitude"]),
                    "lon": float(coordinates["longitude"]),
                    "active": True,
                    "sensor_id": int(sensor["id"]),
                    "first_seen": ((location.get("datetimeFirst") or {}).get("utc")),
                    "last_seen": ((location.get("datetimeLast") or {}).get("utc")),
                }
            )
    frame = pd.DataFrame(rows)
    # A location can expose several PM2.5 sensors; keep the first so station_id stays unique.
    return frame.drop_duplicates("station_id").reset_index(drop=True) if rows else frame


def fetch_hours(
    http: Client, station_id: str, sensor_id: int, start: datetime, end: datetime
) -> pd.DataFrame:
    """Hourly means for one sensor in [start, end). `ts` is the start of the averaging hour."""
    cfg = load_config()["openaq"]
    results = _pages(
        http,
        f"{cfg['base_url']}/sensors/{sensor_id}/hours",
        {
            "datetime_from": start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datetime_to": end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    rows = [
        {
            "station_id": station_id,
            "ts": item["period"]["datetimeFrom"]["utc"],
            "value_raw": item.get("value"),
            "source": "openaq",
        }
        for item in results
        if item.get("period", {}).get("datetimeFrom", {}).get("utc")
    ]
    frame = pd.DataFrame(rows, columns=["station_id", "ts", "value_raw", "source"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.floor("h")
    frame["value_raw"] = pd.to_numeric(frame["value_raw"], errors="coerce")
    return frame.drop_duplicates(["station_id", "ts"], keep="last").reset_index(drop=True)
