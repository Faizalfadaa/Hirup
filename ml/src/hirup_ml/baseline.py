"""Baselines without any model (SPEC 11.3): B1 IDW leave-one-station-out and B0 CAMS.

Needs only observations and stations, so it runs even when gate G0 fails. Its P10/P90 ratio
gives the IDW + CAMS fallback raster an honest uncertainty band.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from hirup_ml import metrics
from hirup_ml.config import baseline_path
from hirup_ml.train import idw_interval_ratio
from hirup_pipelines import paths, qc, store
from hirup_pipelines.features import dynamic
from hirup_pipelines.grid import to_utm


def run() -> dict[str, Any]:
    observations = store.read_daily(paths.observations())
    stations = store.read_parquet(paths.stations())
    if observations.empty or stations is None:
        raise RuntimeError("No observations yet; run `hirup-pipelines qc` first")
    stations = stations[stations["merged_into"].isna()].reset_index(drop=True)
    ids = list(stations["station_id"])
    inputs = qc.to_matrix(
        observations[observations["qc_flag"].isin(["ok", "interpolated"])], "value_cal"
    ).reindex(columns=ids)
    labels = (
        qc.to_matrix(observations[observations["qc_flag"] == "ok"], "value_cal")
        .reindex(index=inputs.index, columns=ids)
        .to_numpy(dtype=float)
    )
    xy = np.column_stack(to_utm(stations["lon"].to_numpy(), stations["lat"].to_numpy()))
    predicted, _ = dynamic.idw(inputs.to_numpy(dtype=float), dynamic.idw_weights(xy, xy))
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "data_window": {"start": inputs.index[0].isoformat(), "end": inputs.index[-1].isoformat()},
        "n_stations": len(ids),
        "idw_loso": metrics.regression(labels.ravel(), predicted.ravel()),
        "idw_interval_ratio": idw_interval_ratio(labels.ravel(), predicted.ravel()),
    }
    cams = store.read_parquet(paths.cams())
    if cams is not None:
        points = cams.drop_duplicates("cell_group_id").sort_values("cell_group_id")
        point_xy = np.column_stack(to_utm(points["lon"].to_numpy(), points["lat"].to_numpy()))
        background = dynamic.cams_matrix(cams, pd.DatetimeIndex(inputs.index), xy, point_xy)
        report["cams"] = metrics.regression(labels.ravel(), background.ravel())
    store.write_json(report, baseline_path())
    return report
