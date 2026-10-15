"""WAQI / aqicn live feed (SPEC 10.1, live labels, scraped every 10 minutes).

WAQI data may not be redistributed. It is stored under `data/` (gitignored) and used only
as training labels and as input to the hourly raster.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from hirup_pipelines.http import Client
from hirup_pipelines.settings import BBox, load_config, require_env


def client(**kwargs: Any) -> Client:
    return Client(min_interval_s=float(load_config()["waqi"]["min_interval_s"]), **kwargs)


def aqi_to_pm25(aqi: float) -> float:
    """Invert the PM2.5 AQI sub-index to ug/m3 with the configured breakpoint table."""
    if aqi is None or not np.isfinite(aqi) or aqi < 0:
        return float("nan")
    for aqi_low, aqi_high, conc_low, conc_high in load_config()["waqi"]["aqi_breakpoints"]["table"]:
        if aqi <= aqi_high:
            # Values between two rows (50 < aqi < 51) snap to the upper row's lower bound.
            share = max(0.0, aqi - aqi_low) / (aqi_high - aqi_low)
            return float(conc_low + share * (conc_high - conc_low))
    return float("nan")


def _get(http: Client, path: str, token: str, **params: Any) -> Any:
    body = http.get_json(
        f"{load_config()['waqi']['base_url']}{path}", params={**params, "token": token}
    )
    if body.get("status") != "ok":
        raise RuntimeError(f"WAQI {path.split('@')[0]} returned status {body.get('status')!r}")
    return body["data"]


def fetch_stations(http: Client, bbox: BBox, token: str | None = None) -> pd.DataFrame:
    token = token or require_env("WAQI_TOKEN")
    data = _get(
        http,
        "/v2/map/bounds",
        token,
        latlng=f"{bbox.min_lat},{bbox.min_lon},{bbox.max_lat},{bbox.max_lon}",
        networks="all",
    )
    rows = [
        {
            "station_id": f"waqi:{item['uid']}",
            "name": (item.get("station") or {}).get("name"),
            # WAQI does not expose instrument grade; treat as low-cost until proven otherwise.
            "type": "lcs",
            "source": "waqi",
            "provider": "waqi",
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "active": True,
        }
        for item in data
        if item.get("uid") is not None
    ]
    return pd.DataFrame(rows)


def fetch_latest(http: Client, station_ids: list[str], token: str | None = None) -> pd.DataFrame:
    """Latest PM2.5 reading per station, converted from AQI sub-index to ug/m3."""
    token = token or require_env("WAQI_TOKEN")
    offset = pd.Timedelta(hours=float(load_config()["waqi"]["hour_offset_h"]))
    rows = []
    for station_id in station_ids:
        data = _get(http, f"/feed/@{station_id.split(':', 1)[1]}/", token)
        aqi = ((data.get("iaqi") or {}).get("pm25") or {}).get("v")
        stamp = (data.get("time") or {}).get("iso")
        if aqi is None or stamp is None:
            continue
        rows.append(
            {
                "station_id": station_id,
                "ts": (pd.Timestamp(stamp).tz_convert("UTC") + offset).floor("h"),
                "value_raw": aqi_to_pm25(float(aqi)),
                "source": "waqi",
                "aqi_raw": float(aqi),
            }
        )
    frame = pd.DataFrame(rows, columns=["station_id", "ts", "value_raw", "source", "aqi_raw"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame
