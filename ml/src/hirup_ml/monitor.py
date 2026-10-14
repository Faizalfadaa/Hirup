"""Drift monitoring (SPEC 11.6): rolling 24 h RMSE of published nowcasts against the station
readings that arrive afterwards. Above 1.5x the validation RMSE the raster falls back to
IDW + CAMS and is labelled `approximated`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from hirup_ml.config import load_config, monitor_path
from hirup_pipelines import paths, store

KEYS = ["station_id", "ts"]


def record(
    inputs: Any, p50: npt.NDArray[np.float64], manifest: dict[str, Any], valid_hour: datetime
) -> None:
    """Store the model nowcast at every station cell so it can be scored later."""
    stations = inputs.stations
    if not len(stations):
        return
    row, col = inputs.grid.locate(stations["x"].to_numpy(), stations["y"].to_numpy())
    inside = inputs.grid.inside(row, col)
    if not inside.any():
        return
    frame = pd.DataFrame(
        {
            "station_id": stations["station_id"].to_numpy()[inside],
            "ts": pd.Timestamp(valid_hour).tz_convert("UTC"),
            "p50": p50[row[inside], col[inside]],
            "model_version": manifest["model_version"],
        }
    )
    old = store.read_parquet(monitor_path())
    merged = frame if old is None else pd.concat([old, frame], ignore_index=True)
    cutoff = pd.Timestamp(valid_hour).tz_convert("UTC") - pd.Timedelta(days=14)
    merged = merged[merged["ts"] >= cutoff].drop_duplicates(KEYS, keep="last")
    store.write_parquet(merged.reset_index(drop=True), monitor_path())


def status(model: Any, now: datetime | None = None) -> dict[str, Any]:
    """Rolling RMSE over the last `window_h` hours and whether it trips the alarm."""
    cfg = load_config()["drift"]
    out: dict[str, Any] = {"alarm": False, "rolling_rmse_24h": None, "pairs": 0, "threshold": None}
    predictions = store.read_parquet(monitor_path())
    if model is None or predictions is None or model.meta.get("loso_rmse") is None:
        return out
    end = (now or datetime.now(UTC)).astimezone(UTC)
    start = end - timedelta(hours=int(cfg["window_h"]))
    observations = store.read_daily(paths.observations(), start=start, end=end)
    if observations.empty:
        return out
    scored = predictions[predictions["model_version"] == model.version].merge(
        observations.loc[observations["qc_flag"] == "ok", [*KEYS, "value_cal"]], on=KEYS
    )
    scored = scored[(scored["ts"] >= start) & (scored["ts"] < end)]
    threshold = float(cfg["alarm_ratio"]) * float(model.meta["loso_rmse"])
    out |= {"pairs": len(scored), "threshold": threshold}
    if len(scored) < int(cfg["min_pairs"]):
        return out
    rmse = float(np.sqrt(np.mean((scored["p50"] - scored["value_cal"]) ** 2)))
    return out | {"rolling_rmse_24h": rmse, "alarm": rmse > threshold}
