"""Hourly features (SPEC 11.2): calendar, weather, CAMS background and station IDW with lags.

Arrays are hours x targets, where a target is a station (training) or a grid cell (inference).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import numpy.typing as npt
import pandas as pd

from hirup_pipelines.settings import TIMEZONE, load_config

FloatArray = npt.NDArray[np.float64]
IDW_POWER = 2.0  # SPEC 11.3, baseline B1
IDW_LAGS = (1, 2, 3)  # SPEC 11.2
WEATHER_COLUMNS = ("wind_u", "wind_v", "temp", "rh", "precip", "blh")
TIME_COLUMNS = ("hour_sin", "hour_cos", "dow", "is_weekend", "is_holiday", "is_ramadan")
IDW_COLUMNS = ("idw_pm25", *(f"idw_pm25_lag{lag}" for lag in IDW_LAGS), "n_stations")


def time_features(hours: pd.DatetimeIndex) -> pd.DataFrame:
    cfg = load_config()["calendar"]
    local = hours.tz_convert(TIMEZONE)
    holidays = {date.fromisoformat(str(day)) for day in cfg["holidays"]}
    ramadan = [(date.fromisoformat(str(a)), date.fromisoformat(str(b))) for a, b in cfg["ramadan"]]
    days = pd.Series(local.date, index=hours)
    return pd.DataFrame(
        {
            "hour_sin": np.sin(2 * np.pi * local.hour / 24),
            "hour_cos": np.cos(2 * np.pi * local.hour / 24),
            "dow": local.dayofweek.astype(float),
            "is_weekend": (local.dayofweek >= 5).astype(float),
            "is_holiday": days.isin(holidays).to_numpy(dtype=float),
            "is_ramadan": days.map(lambda d: any(a <= d <= b for a, b in ramadan)).to_numpy(
                dtype=float
            ),
        },
        index=hours,
    )


def idw_weights(
    source_xy: FloatArray, target_xy: FloatArray, power: float = IDW_POWER
) -> FloatArray:
    """targets x sources inverse-distance weights. A source at the target itself gets weight
    zero, which makes station-to-station weights leave-one-out by construction."""
    distance = np.hypot(
        target_xy[:, None, 0] - source_xy[None, :, 0], target_xy[:, None, 1] - source_xy[None, :, 1]
    )
    with np.errstate(divide="ignore"):
        weights = np.where(distance < 1.0, 0.0, 1.0 / np.maximum(distance, 1.0) ** power)
    return np.asarray(weights, dtype=float)


def idw(values: FloatArray, weights: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Interpolate hours x sources onto targets. Returns (hours x targets, reporting count)."""
    present = np.isfinite(values)
    total = np.nan_to_num(values) @ weights.T
    norm = present.astype(float) @ weights.T
    count = present.astype(float) @ (weights.T > 0).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(norm > 0, total / norm, np.nan), count


def lagged(matrix: FloatArray, lag: int) -> FloatArray:
    out = np.full_like(matrix, np.nan)
    if lag < len(matrix):
        out[lag:] = matrix[: len(matrix) - lag]
    return out


def idw_block(values: FloatArray, weights: FloatArray) -> dict[str, FloatArray]:
    """The IDW feature group for every hour and target."""
    now, count = idw(values, weights)
    block = {"idw_pm25": now}
    for lag in IDW_LAGS:
        block[f"idw_pm25_lag{lag}"] = lagged(now, lag)
    block["n_stations"] = count
    return block


def weather_matrices(
    weather: pd.DataFrame, hours: pd.DatetimeIndex, groups: npt.NDArray[np.int64]
) -> dict[str, FloatArray]:
    """Each weather variable as hours x targets; `groups` maps a target to its lattice point."""
    out: dict[str, FloatArray] = {}
    for column in WEATHER_COLUMNS:
        wide = weather.pivot_table(
            index="ts", columns="cell_group_id", values=column, aggfunc="last"
        )
        out[column] = wide.reindex(hours).reindex(columns=np.unique(groups)).to_numpy(dtype=float)
    rain = pd.DataFrame(out["precip"], index=hours)
    out["precip_6h"] = rain.rolling(6, min_periods=1).sum().to_numpy()
    lookup = np.searchsorted(np.unique(groups), groups)
    return {name: matrix[:, lookup] for name, matrix in out.items()}


def cams_matrix(
    cams: pd.DataFrame, hours: pd.DatetimeIndex, target_xy: FloatArray, point_xy: FloatArray
) -> FloatArray:
    """CAMS PM2.5 as hours x targets, inverse-distance blended between lattice points."""
    wide = cams.pivot_table(index="ts", columns="cell_group_id", values="pm25_cams", aggfunc="last")
    values = wide.reindex(hours).to_numpy(dtype=float)
    distance = np.hypot(
        target_xy[:, None, 0] - point_xy[None, :, 0], target_xy[:, None, 1] - point_xy[None, :, 1]
    )
    weights = 1.0 / np.maximum(distance, 100.0) ** 2
    return idw(values, weights)[0]


def nearest_source_distance(source_xy: FloatArray, target_xy: FloatArray) -> FloatArray:
    """Distance from each target to the closest source other than itself."""
    distance = np.hypot(
        target_xy[:, None, 0] - source_xy[None, :, 0], target_xy[:, None, 1] - source_xy[None, :, 1]
    )
    distance = np.where(distance < 1.0, np.inf, distance)
    return np.asarray(distance.min(axis=1), dtype=float)
