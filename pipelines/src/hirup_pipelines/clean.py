"""Raw observations -> `aq_observations` (SPEC 10.3): QC flags, merged sources, calibration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from hirup_pipelines import qc, schemas
from hirup_pipelines.grid import to_utm


@dataclass
class Cleaned:
    observations: pd.DataFrame  # station_id, ts, value_raw, value_cal, qc_flag, source
    stations: pd.DataFrame  # adds x, y, merged_into, weight, calibrated
    calibration: qc.Calibration
    duplicates: pd.DataFrame


def nearest_group(stations: pd.DataFrame, points: pd.DataFrame) -> pd.Series:
    """`cell_group_id` of the weather lattice point nearest to each station."""
    sx, sy = to_utm(stations["lon"].to_numpy(), stations["lat"].to_numpy())
    px, py = to_utm(points["lon"].to_numpy(), points["lat"].to_numpy())
    nearest = np.hypot(sx[:, None] - px[None, :], sy[:, None] - py[None, :]).argmin(axis=1)
    return pd.Series(points["cell_group_id"].to_numpy()[nearest], index=stations["station_id"])


def station_matrix(
    table: pd.DataFrame, column: str, stations: pd.DataFrame, index: pd.DatetimeIndex
) -> pd.DataFrame:
    """A weather variable as an hours x stations matrix (each station reads its lattice point)."""
    if table.empty:
        return pd.DataFrame(np.nan, index=index, columns=stations["station_id"])
    points = table.drop_duplicates("cell_group_id")[["cell_group_id", "lat", "lon"]]
    wide = table.pivot_table(index="ts", columns="cell_group_id", values=column, aggfunc="last")
    groups = nearest_group(stations, points)
    out = wide.reindex(index)[groups.to_numpy()]
    out.columns = groups.index
    return out


def clean(
    raw: pd.DataFrame, stations: pd.DataFrame, weather: pd.DataFrame, version: str
) -> Cleaned:
    raw = schemas.validate(raw, schemas.RAW_OBSERVATIONS)
    stations = stations[stations["station_id"].isin(raw["station_id"].unique())].reset_index(
        drop=True
    )
    values = qc.to_matrix(raw)[list(stations["station_id"])]
    flags = pd.DataFrame("ok", index=values.index, columns=values.columns)
    flags = flags.mask(qc.flag_range(values), "range")
    plausible = values.where(flags.eq("ok"))
    flags = flags.mask(qc.flag_flatline(plausible), "flatline")
    flags = flags.mask(qc.flag_spike(plausible.where(flags.eq("ok")), stations), "spike")
    good = values.where(flags.eq("ok"))
    source = pd.DataFrame(
        np.tile(stations["source"].to_numpy(), (len(values), 1)),
        index=values.index,
        columns=values.columns,
    )

    # Fold WAQI mirrors into their OpenAQ twin: OpenAQ wins, WAQI fills its gaps.
    duplicates = qc.find_duplicates(good, stations)
    merged_into: dict[str, str] = {}
    for row in duplicates[duplicates["merge"]].itertuples(index=False):
        if row.station_id in merged_into or row.station_id not in values.columns:
            continue
        take = good[row.merged_into].isna() & good[row.station_id].notna()
        for matrix in (values, good, flags, source):
            matrix[row.merged_into] = matrix[row.merged_into].where(~take, matrix[row.station_id])
        merged_into[row.station_id] = row.merged_into
    keep = [s for s in values.columns if s not in merged_into]
    values, good, flags, source = values[keep], good[keep], flags[keep], source[keep]
    kept = stations.set_index("station_id").loc[keep].reset_index()

    rh = station_matrix(weather, "rh", kept, values.index)
    calibration = qc.fit_calibration(good, kept, rh, version)
    calibrated = good.copy()
    for i, station in enumerate(kept.itertuples(index=False)):
        if station.type != "lcs":
            continue
        fitted = calibration.apply(
            station.provider, good.iloc[:, i].to_numpy(), rh.iloc[:, i].to_numpy()
        )
        if fitted is not None:
            # Hours without humidity keep the raw value rather than dropping the label.
            calibrated.iloc[:, i] = np.where(np.isfinite(fitted), fitted, good.iloc[:, i])
    filled, interpolated = qc.fill_short_gaps(calibrated)
    # Only truly missing hours are filled; an hour that failed QC keeps its flag.
    interpolated &= values.isna()
    filled = calibrated.where(~interpolated, filled)
    flags = flags.mask(interpolated, "interpolated")

    long = pd.DataFrame(
        {
            "value_raw": values.stack(future_stack=True),
            "value_cal": filled.stack(future_stack=True),
            "qc_flag": flags.stack(future_stack=True),
            "source": source.stack(future_stack=True),
        }
    ).reset_index()
    long = long.rename(columns={long.columns[0]: "ts", long.columns[1]: "station_id"})
    long = long[long["value_raw"].notna() | long["qc_flag"].eq("interpolated")]
    observations = schemas.validate(
        long[["station_id", "ts", "value_raw", "value_cal", "qc_flag", "source"]].reset_index(
            drop=True
        ),
        schemas.AQ_OBSERVATIONS,
    )

    out = stations.copy()
    out["x"], out["y"] = to_utm(out["lon"].to_numpy(), out["lat"].to_numpy())
    out["merged_into"] = out["station_id"].map(merged_into).astype("string")
    out["weight"] = out["station_id"].map(qc.sample_weights(out, calibration))
    out["calibrated"] = out["type"].eq("lcs") & out["provider"].isin(list(calibration.coefficients))
    return Cleaned(observations, out, calibration, duplicates)
