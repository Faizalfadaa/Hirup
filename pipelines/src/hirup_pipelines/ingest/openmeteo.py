"""Open-Meteo weather and CAMS air quality on a small lattice over the pilot area (SPEC 10.1)."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from hirup_pipelines.http import Client
from hirup_pipelines.settings import BBox, load_config


def lattice(bbox: BBox) -> pd.DataFrame:
    """Query points; `cell_group_id` is the row index and keys the weather tables."""
    cfg = load_config()["open_meteo"]["lattice"]
    lats = np.linspace(bbox.min_lat, bbox.max_lat, int(cfg["n_lat"]) + 2)[1:-1]
    lons = np.linspace(bbox.min_lon, bbox.max_lon, int(cfg["n_lon"]) + 2)[1:-1]
    grid = [(float(lat), float(lon)) for lat in lats for lon in lons]
    return pd.DataFrame(grid, columns=["lat", "lon"]).rename_axis("cell_group_id").reset_index()


def _fetch(
    http: Client,
    url: str,
    points: pd.DataFrame,
    hourly: list[str],
    *,
    start: date | None,
    end: date | None,
    past_days: int | None,
    forecast_days: int | None,
    extra: dict[str, Any] | None = None,
) -> pd.DataFrame:
    params: dict[str, Any] = {
        "latitude": ",".join(f"{v:.4f}" for v in points["lat"]),
        "longitude": ",".join(f"{v:.4f}" for v in points["lon"]),
        "hourly": ",".join(hourly),
        "timezone": "GMT",
        **(extra or {}),
    }
    if start is not None and end is not None:
        params |= {"start_date": start.isoformat(), "end_date": end.isoformat()}
    else:
        params |= {"past_days": past_days or 0, "forecast_days": forecast_days or 1}
    body = http.get_json(url, params=params)
    payloads = body if isinstance(body, list) else [body]
    frames = []
    for (_, point), payload in zip(points.iterrows(), payloads, strict=True):
        frame = pd.DataFrame(payload["hourly"])
        frame["ts"] = pd.to_datetime(frame.pop("time"), utc=True)
        frame.insert(0, "cell_group_id", int(point["cell_group_id"]))
        frame["lat"], frame["lon"] = float(point["lat"]), float(point["lon"])
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def fetch_weather(
    http: Client,
    points: pd.DataFrame,
    *,
    start: date | None = None,
    end: date | None = None,
    past_days: int | None = None,
    forecast_days: int | None = None,
) -> pd.DataFrame:
    """Hourly weather. A date range uses the historical-forecast archive; otherwise the live API."""
    cfg = load_config()["open_meteo"]
    url = cfg["weather_history_url"] if start is not None else cfg["weather_url"]
    raw = _fetch(
        http,
        url,
        points,
        list(cfg["weather_vars"]),
        start=start,
        end=end,
        past_days=past_days,
        forecast_days=forecast_days,
        extra={"wind_speed_unit": "ms"},
    )
    # Meteorological direction is where the wind comes from.
    direction = np.radians(raw["wind_direction_10m"].astype(float))
    speed = raw["wind_speed_10m"].astype(float)
    return pd.DataFrame(
        {
            "cell_group_id": raw["cell_group_id"],
            "ts": raw["ts"],
            "lat": raw["lat"],
            "lon": raw["lon"],
            "wind_u": -speed * np.sin(direction),
            "wind_v": -speed * np.cos(direction),
            "temp": raw["temperature_2m"].astype(float),
            "rh": raw["relative_humidity_2m"].astype(float),
            "precip": raw["precipitation"].astype(float),
            "blh": raw["boundary_layer_height"].astype(float),
        }
    )


def fetch_cams(
    http: Client,
    points: pd.DataFrame,
    *,
    start: date | None = None,
    end: date | None = None,
    past_days: int | None = None,
    forecast_days: int | None = None,
) -> pd.DataFrame:
    """Hourly CAMS global PM2.5 (regional background and forecast basis)."""
    cfg = load_config()["open_meteo"]
    raw = _fetch(
        http,
        cfg["air_quality_url"],
        points,
        ["pm2_5"],
        start=start,
        end=end,
        past_days=past_days,
        forecast_days=forecast_days,
        extra={"domains": cfg["cams_domain"]},
    )
    return raw.rename(columns={"pm2_5": "pm25_cams"})[
        ["cell_group_id", "ts", "lat", "lon", "pm25_cams"]
    ].astype({"pm25_cams": float})
