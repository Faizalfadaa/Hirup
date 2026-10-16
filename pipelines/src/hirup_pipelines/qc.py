"""Quality control, source de-duplication and low-cost-sensor calibration (SPEC 10.2).

Everything works on an hourly matrix (rows = hours, columns = stations) so the rules stay
vectorised. Flags: ok, range, flatline, spike, interpolated. Only `ok` rows are ever labels;
`interpolated` rows (gaps of at most two hours) may feed features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from hirup_pipelines.grid import to_utm
from hirup_pipelines.settings import load_config

FloatArray = npt.NDArray[np.float64]
MAD_TO_SIGMA = 1.4826


def to_matrix(observations: pd.DataFrame, column: str = "value_raw") -> pd.DataFrame:
    """Hours x stations matrix on a gap-free hourly index."""
    wide = observations.pivot_table(index="ts", columns="station_id", values=column, aggfunc="last")
    if wide.empty:
        return wide
    full = pd.date_range(wide.index.min(), wide.index.max(), freq="h", name="ts")
    return wide.reindex(full)


def distances_m(stations: pd.DataFrame) -> FloatArray:
    x, y = to_utm(stations["lon"].to_numpy(), stations["lat"].to_numpy())
    return np.hypot(x[:, None] - x[None, :], y[:, None] - y[None, :])


def flag_range(values: pd.DataFrame) -> pd.DataFrame:
    cfg = load_config()["qc"]
    return (values < cfg["range_min"]) | (values > cfg["range_max"])


def flag_flatline(values: pd.DataFrame) -> pd.DataFrame:
    """True for every hour inside a run of >= N identical consecutive values."""
    hours = int(load_config()["qc"]["flatline_hours"])
    flags = pd.DataFrame(False, index=values.index, columns=values.columns)
    for station in values.columns:
        series = values[station]
        changed = series.ne(series.shift()) | series.isna()
        run = changed.cumsum()
        length = series.groupby(run).transform("size")
        flags[station] = series.notna() & (length >= hours)
    return flags


def robust_deviation(values: pd.DataFrame) -> pd.DataFrame:
    """(value - rolling median) / rolling robust sigma over the configured window."""
    window = int(load_config()["qc"]["spike_window_h"])
    median = values.rolling(window, min_periods=window // 2).median()
    mad = (values - median).abs().rolling(window, min_periods=window // 2).median()
    sigma = (mad * MAD_TO_SIGMA).clip(lower=1.0)  # 1 ug/m3 floor: sensors report integers
    return (values - median) / sigma


def flag_spike(values: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """A jump beyond `spike_sigma` that no neighbour within `spike_neighbour_km` shares."""
    cfg = load_config()["qc"]
    deviation = robust_deviation(values)
    suspect = deviation.abs() > cfg["spike_sigma"]
    ordered = stations.set_index("station_id").loc[list(values.columns)].reset_index()
    near = distances_m(ordered) <= cfg["spike_neighbour_km"] * 1000
    np.fill_diagonal(near, False)
    confirm = float(cfg["spike_confirm_sigma"])
    signed = deviation.to_numpy()
    up = np.nan_to_num(signed) >= confirm
    down = np.nan_to_num(signed) <= -confirm
    # A neighbour confirms when it deviates the same way in the same hour.
    confirmed = ((up.astype(float) @ near.T.astype(float)) > 0) & (signed > 0) | (
        (down.astype(float) @ near.T.astype(float)) > 0
    ) & (signed < 0)
    return suspect & ~pd.DataFrame(confirmed, index=values.index, columns=values.columns)


def fill_short_gaps(values: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Linear interpolation across gaps of at most `max_gap_h` hours with data on both sides."""
    limit = int(load_config()["qc"]["max_gap_h"])
    missing = values.isna()
    filled_mask = pd.DataFrame(False, index=values.index, columns=values.columns)
    for station in values.columns:
        gap = missing[station]
        run = (~gap).cumsum()
        length = gap.groupby(run).transform("sum")
        inside = run.gt(0) & run.lt(run.max()) if gap.any() else gap
        filled_mask[station] = gap & (length <= limit) & inside
    interpolated = values.interpolate(method="linear", limit_area="inside")
    return values.where(~filled_mask, interpolated), filled_mask


@dataclass
class Calibration:
    """PM_ref = a*PM_lcs + b*RH + c*PM_lcs*RH + d, fitted per provider."""

    version: str
    coefficients: dict[str, dict[str, float]] = field(default_factory=dict)
    pairs: dict[str, int] = field(default_factory=dict)

    def apply(self, provider: str | None, pm: FloatArray, rh: FloatArray) -> FloatArray | None:
        coef = self.coefficients.get(provider or "")
        if coef is None:
            return None
        out = coef["a"] * pm + coef["b"] * rh + coef["c"] * pm * rh + coef["d"]
        return np.asarray(np.clip(out, 0, None), dtype=float)

    def to_json(self) -> dict[str, Any]:
        return {"version": self.version, "coefficients": self.coefficients, "pairs": self.pairs}


def fit_calibration(
    values: pd.DataFrame, stations: pd.DataFrame, rh: pd.DataFrame, version: str
) -> Calibration:
    """Fit on low-cost / reference pairs at most `pair_km` apart, pooled per provider."""
    cfg = load_config()["calibration"]
    ordered = stations.set_index("station_id").loc[list(values.columns)].reset_index()
    distance = distances_m(ordered)
    is_ref = ordered["type"].eq("reference").to_numpy()
    calibration = Calibration(version)
    for provider, group in ordered[~is_ref].groupby("provider"):
        xs, ys = [], []
        for i in group.index:
            candidates = np.where(is_ref & (distance[i] <= cfg["pair_km"] * 1000))[0]
            if not len(candidates):
                continue
            j = candidates[np.argmin(distance[i, candidates])]
            lcs = values.iloc[:, i].to_numpy()
            ref = values.iloc[:, j].to_numpy()
            humidity = rh.iloc[:, i].to_numpy()
            ok = np.isfinite(lcs) & np.isfinite(ref) & np.isfinite(humidity)
            xs.append(
                np.column_stack([lcs[ok], humidity[ok], lcs[ok] * humidity[ok], np.ones(ok.sum())])
            )
            ys.append(ref[ok])
        if not xs or sum(len(y) for y in ys) < cfg["min_pairs"]:
            continue
        design, target = np.vstack(xs), np.concatenate(ys)
        a, b, c, d = np.linalg.lstsq(design, target, rcond=None)[0]
        calibration.coefficients[str(provider)] = {
            "a": float(a),
            "b": float(b),
            "c": float(c),
            "d": float(d),
        }
        calibration.pairs[str(provider)] = len(target)
    return calibration


def find_duplicates(values: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """WAQI stations that mirror an OpenAQ station (<= 50 m apart and well correlated).

    Also reports the correlation at -1/0/+1 h lag, which shows whether the two sources
    stamp the same hour (see README "Open questions").
    """
    cfg = load_config()["dedupe"]
    ordered = stations.set_index("station_id").loc[list(values.columns)].reset_index()
    distance = distances_m(ordered)
    rows = []
    for i in ordered.index[ordered["source"].eq("waqi")]:
        for j in ordered.index[ordered["source"].eq("openaq")]:
            if distance[i, j] > cfg["max_distance_m"]:
                continue
            a, b = values.iloc[:, i], values.iloc[:, j]
            lags = {}
            for lag in (-1, 0, 1):
                both = pd.concat([a.shift(lag), b], axis=1).dropna()
                enough = len(both) >= cfg["min_overlap_h"] and both.std().min() > 0
                lags[lag] = float(both.corr().iloc[0, 1]) if enough else float("nan")
            overlap = int((a.notna() & b.notna()).sum())
            best = (
                np.nanmax(list(lags.values())) if np.isfinite(list(lags.values())).any() else np.nan
            )
            rows.append(
                {
                    "station_id": ordered.loc[i, "station_id"],
                    "merged_into": ordered.loc[j, "station_id"],
                    "distance_m": float(distance[i, j]),
                    "overlap_h": overlap,
                    "corr_lag_m1": lags[-1],
                    "corr_lag_0": lags[0],
                    "corr_lag_p1": lags[1],
                    # Too little overlap to test correlation: co-location alone decides.
                    "merge": bool(np.isnan(best) or best >= cfg["min_correlation"]),
                }
            )
    columns = [
        "station_id",
        "merged_into",
        "distance_m",
        "overlap_h",
        "corr_lag_m1",
        "corr_lag_0",
        "corr_lag_p1",
        "merge",
    ]
    return pd.DataFrame(rows, columns=columns)


def merge_duplicates(values: pd.DataFrame, duplicates: pd.DataFrame) -> pd.DataFrame:
    """Fold each merged WAQI column into its OpenAQ twin (OpenAQ wins, WAQI fills gaps)."""
    merged = values.copy()
    for row in duplicates[duplicates["merge"]].itertuples(index=False):
        if row.station_id in merged.columns and row.merged_into in merged.columns:
            merged[row.merged_into] = merged[row.merged_into].fillna(merged[row.station_id])
            merged = merged.drop(columns=row.station_id)
    return merged


def sample_weights(stations: pd.DataFrame, calibration: Calibration) -> pd.Series:
    cfg = load_config()["sample_weight"]
    calibrated = stations["provider"].isin(list(calibration.coefficients))
    weights = np.where(
        stations["type"].eq("reference"),
        cfg["reference"],
        np.where(calibrated, cfg["lcs_calibrated"], cfg["lcs_raw"]),
    )
    return pd.Series(weights, index=stations["station_id"], name="weight", dtype=float)
