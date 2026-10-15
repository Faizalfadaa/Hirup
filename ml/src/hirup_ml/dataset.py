"""Training table: QC-passed station hours joined to static and hourly features (SPEC 11.2).

The IDW feature group depends on which stations are visible, so it is rebuilt per validation
fold without the held-out stations (SPEC 11.4: "fitur IDW dihitung ulang tanpa stasiun itu").
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from hirup_pipelines import paths, qc, store
from hirup_pipelines.features import dynamic
from hirup_pipelines.features.static import feature_columns
from hirup_pipelines.grid import to_utm

FloatArray = npt.NDArray[np.float64]
FOLD_COLUMNS = (*dynamic.IDW_COLUMNS, "dist_nearest_station_m")
WEATHER_FEATURES = (*dynamic.WEATHER_COLUMNS, "precip_6h")


@dataclass
class Dataset:
    stations: pd.DataFrame  # one row per station: station_id, x, y, weight, type
    hours: pd.DatetimeIndex
    labels: FloatArray  # hours x stations, QC `ok` only
    inputs: FloatArray  # hours x stations, `ok` + `interpolated`, feeds the IDW features
    static: FloatArray  # stations x static features
    static_names: list[str]
    shared: dict[str, FloatArray]  # fold-independent hourly features, hours x stations
    rows: npt.NDArray[np.int64]  # (n, 2) hour and station index of every labelled row

    @property
    def xy(self) -> FloatArray:
        return np.asarray(self.stations[["x", "y"]].to_numpy(dtype=float), dtype=np.float64)

    @property
    def y(self) -> FloatArray:
        return self.labels[self.rows[:, 0], self.rows[:, 1]]

    @property
    def weights(self) -> FloatArray:
        weight = np.asarray(self.stations["weight"].to_numpy(dtype=float), dtype=np.float64)
        return weight[self.rows[:, 1]]

    @property
    def feature_names(self) -> list[str]:
        return [*self.static_names, *self.shared, *FOLD_COLUMNS]

    def base(self) -> FloatArray:
        """Fold-independent feature columns for every labelled row."""
        h, s = self.rows[:, 0], self.rows[:, 1]
        return np.column_stack([self.static[s], *(matrix[h, s] for matrix in self.shared.values())])

    def fold(self, holdout: Sequence[int] = ()) -> FloatArray:
        """IDW columns as seen when `holdout` stations do not exist. A station never
        contributes to its own interpolation (zero self-weight)."""
        values = self.inputs.copy()
        values[:, list(holdout)] = np.nan
        weights = dynamic.idw_weights(self.xy, self.xy)
        block = dynamic.idw_block(values, weights)
        visible = np.ones(len(self.stations), dtype=bool)
        visible[list(holdout)] = False
        nearest = dynamic.nearest_source_distance(self.xy[visible], self.xy)
        h, s = self.rows[:, 0], self.rows[:, 1]
        return np.column_stack([*(block[name][h, s] for name in dynamic.IDW_COLUMNS), nearest[s]])

    def design(self, holdout: Sequence[int] = ()) -> FloatArray:
        return np.column_stack([self.base(), self.fold(holdout)])


def shared_features(
    hours: pd.DatetimeIndex,
    target_xy: FloatArray,
    weather: pd.DataFrame,
    cams: pd.DataFrame,
) -> dict[str, FloatArray]:
    """Calendar, weather and CAMS as hours x targets, in the order the model expects."""
    n = len(target_xy)
    out: dict[str, FloatArray] = {}
    for name, column in dynamic.time_features(hours).items():
        out[str(name)] = np.repeat(column.to_numpy(dtype=float)[:, None], n, axis=1)
    points = weather.drop_duplicates("cell_group_id").sort_values("cell_group_id")
    px, py = to_utm(points["lon"].to_numpy(), points["lat"].to_numpy())
    distance = np.hypot(target_xy[:, None, 0] - px[None, :], target_xy[:, None, 1] - py[None, :])
    groups = points["cell_group_id"].to_numpy()[distance.argmin(axis=1)]
    matrices = dynamic.weather_matrices(weather, hours, groups)
    for name in WEATHER_FEATURES:
        out[name] = matrices[name]
    cams_points = cams.drop_duplicates("cell_group_id").sort_values("cell_group_id")
    cx, cy = to_utm(cams_points["lon"].to_numpy(), cams_points["lat"].to_numpy())
    out["cams_pm25"] = dynamic.cams_matrix(cams, hours, target_xy, np.column_stack([cx, cy]))
    return out


def build(
    observations: pd.DataFrame,
    stations: pd.DataFrame,
    station_static: pd.DataFrame,
    weather: pd.DataFrame,
    cams: pd.DataFrame,
) -> Dataset:
    stations = stations[
        stations["merged_into"].isna() & stations["station_id"].isin(station_static["station_id"])
    ]
    stations = stations[stations["station_id"].isin(observations["station_id"])].reset_index(
        drop=True
    )
    ids = list(stations["station_id"])
    usable = observations[observations["station_id"].isin(ids)]
    inputs = qc.to_matrix(usable[usable["qc_flag"].isin(["ok", "interpolated"])], "value_cal")
    hours = pd.DatetimeIndex(inputs.index)
    inputs = inputs.reindex(columns=ids)
    labels = (
        qc.to_matrix(usable[usable["qc_flag"] == "ok"], "value_cal")
        .reindex(index=hours, columns=ids)
        .to_numpy(dtype=float, copy=True)
    )
    static_frame = station_static.set_index("station_id").loc[ids]
    static_names = feature_columns(static_frame.reset_index())
    xy = stations[["x", "y"]].to_numpy(dtype=float)
    return Dataset(
        stations=stations,
        hours=hours,
        labels=labels,
        inputs=inputs.to_numpy(dtype=float, copy=True),
        static=static_frame[static_names].to_numpy(dtype=float),
        static_names=static_names,
        shared=shared_features(hours, xy, weather, cams),
        rows=np.argwhere(np.isfinite(labels)),
    )


def load() -> Dataset:
    """Assemble the training table from `data/`. Raises when a required artefact is missing."""
    observations = store.read_daily(paths.observations())
    tables = {
        "stations": store.read_parquet(paths.stations()),
        "station_static": store.read_parquet(paths.station_static()),
        "weather": store.read_parquet(paths.weather()),
        "cams": store.read_parquet(paths.cams()),
    }
    missing = [name for name, table in tables.items() if table is None]
    if observations.empty or missing:
        raise RuntimeError(
            "Training data incomplete: "
            + ", ".join((["aq_observations"] if observations.empty else []) + missing)
            + ". Run the hirup-pipelines steps in pipelines/README.md first."
        )
    return build(observations, **tables)
