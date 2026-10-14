"""Hourly inference (SPEC 9.4 step 2, 11.6): nowcast + forecast rasters, manifests, tiles.

One run at local hour T publishes:
  - the nowcast for T (station readings carried forward at most `max_staleness_h` hours),
  - forecasts for T+1 .. T+24: the same model fed with forecast weather and CAMS, and with the
    station IDW field scaled by the CAMS trend,
  - `aq_inputs.json` and `city_medians.json`, the API's fallback inputs and C_ref.
When no model is active, or the drift alarm fires, the raster is IDW + CAMS and is labelled
`approximated`. Nothing here ever produces `synthetic` data.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from hirup_ml import insights, monitor, raster, registry
from hirup_ml.config import (
    FALLBACK_VERSION,
    baseline_path,
    load_config,
    manifests_dir,
    rasters_dir,
    tiles_dir,
)
from hirup_ml.dataset import FOLD_COLUMNS, shared_features
from hirup_pipelines import paths, qc, store
from hirup_pipelines.features import dynamic
from hirup_pipelines.features.static import feature_columns
from hirup_pipelines.grid import Grid, pilot_grid
from hirup_pipelines.settings import data_dir

log = logging.getLogger(__name__)
FloatArray = npt.NDArray[np.float64]


def slot_names() -> list[str]:
    """Fixed manifest file names. The API is configured with exactly this list."""
    cfg = load_config()["inference"]
    recent = [f"nowcast_minus_{k:02d}.json" for k in range(int(cfg["recent_slots"]), 0, -1)]
    ahead = [f"forecast_plus_{k:02d}.json" for k in range(1, int(cfg["horizon_h"]) + 1)]
    return [*recent, "nowcast.json", *ahead]


@dataclass
class Inputs:
    grid: Grid
    cells: pd.DataFrame
    stations: pd.DataFrame  # station_id, x, y, lat, lon
    hours: pd.DatetimeIndex  # T - history .. T + horizon, UTC
    now: int  # index of T in `hours`
    values: FloatArray  # hours x stations, carried forward up to max_staleness_h, NaN after T
    shared: dict[str, FloatArray]  # hours x cells
    cams_mean: FloatArray  # per hour, mean over the lattice


def load_inputs(valid_hour: datetime) -> Inputs:
    cfg = load_config()["inference"]
    grid = pilot_grid()
    cells = store.read_parquet(paths.grid_cells())
    weather, cams = store.read_parquet(paths.weather()), store.read_parquet(paths.cams())
    if cells is None or weather is None or cams is None:
        raise RuntimeError(
            "Inference needs grid_cells, weather_hourly and cams_hourly; run "
            "`hirup-pipelines static` and `hirup-pipelines hourly` first"
        )
    cells = cells.drop(columns=["geometry"], errors="ignore")
    start = valid_hour - timedelta(hours=int(cfg["history_h"]))
    hours = pd.date_range(start, valid_hour + timedelta(hours=int(cfg["horizon_h"])), freq="h")
    now = int(cfg["history_h"])

    stations = store.read_parquet(paths.stations())
    observations = store.read_daily(paths.observations(), start=start)
    if stations is not None and not observations.empty:
        stations = stations[stations["merged_into"].isna()].reset_index(drop=True)
        usable = observations[observations["qc_flag"].isin(["ok", "interpolated"])]
        wide = qc.to_matrix(usable, "value_cal").reindex(
            index=hours, columns=stations["station_id"]
        )
        wide.iloc[now + 1 :] = np.nan
        values = wide.ffill(limit=int(cfg["max_staleness_h"])).to_numpy(dtype=float, copy=True)
        values[now + 1 :] = np.nan
    else:
        stations = pd.DataFrame(columns=["station_id", "x", "y", "lat", "lon"])
        values = np.full((len(hours), 0), np.nan)

    cell_xy = cells[["x", "y"]].to_numpy(dtype=float)
    shared = shared_features(hours, cell_xy, weather, cams)
    cams_wide = cams.pivot_table(
        index="ts", columns="cell_group_id", values="pm25_cams", aggfunc="last"
    )
    return Inputs(
        grid,
        cells,
        stations,
        hours,
        now,
        values,
        shared,
        cams_wide.reindex(hours).mean(axis=1).to_numpy(dtype=float),
    )


def idw_series(inputs: Inputs) -> dict[str, FloatArray]:
    """The IDW feature group for every hour and cell. Hours after T hold the field at T scaled
    by the CAMS trend, because future station readings do not exist yet."""
    low, high = load_config()["inference"]["cams_ratio_clip"]
    station_xy = inputs.stations[["x", "y"]].to_numpy(dtype=float).reshape(-1, 2)
    cell_xy = inputs.cells[["x", "y"]].to_numpy(dtype=float)
    weights = dynamic.idw_weights(station_xy, cell_xy)
    field, count = dynamic.idw(inputs.values, weights)
    cams = inputs.shared["cams_pm25"]
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.clip(cams / cams[inputs.now], low, high)
    ratio = np.where(np.isfinite(ratio), ratio, 1.0)
    future = np.arange(len(inputs.hours)) > inputs.now
    field[future] = field[inputs.now] * ratio[future]
    count[future] = count[inputs.now]
    block = {"idw_pm25": field}
    for lag in dynamic.IDW_LAGS:
        block[f"idw_pm25_lag{lag}"] = dynamic.lagged(field, lag)
    block["n_stations"] = count
    nearest = (
        dynamic.nearest_source_distance(station_xy, cell_xy)
        if len(station_xy)
        else np.full(len(cell_xy), np.nan)
    )
    block["dist_nearest_station_m"] = np.repeat(nearest[None, :], len(inputs.hours), axis=0)
    return block


def design(inputs: Inputs, block: dict[str, FloatArray], hour: int, names: list[str]) -> FloatArray:
    """Feature matrix for one hour, columns in the order the model was trained with."""
    static_names = feature_columns(inputs.cells)
    columns: dict[str, FloatArray] = {
        n: inputs.cells[n].to_numpy(dtype=float) for n in static_names
    }
    columns |= {name: matrix[hour] for name, matrix in inputs.shared.items()}
    columns |= {name: block[name][hour] for name in FOLD_COLUMNS}
    missing = [name for name in names if name not in columns]
    if missing:
        raise RuntimeError(f"Model expects features that inference cannot build: {missing[:5]}")
    return np.column_stack([columns[name] for name in names])


def fallback_field(inputs: Inputs, block: dict[str, FloatArray], hour: int) -> FloatArray | None:
    """IDW of station readings where any exist, otherwise the CAMS background (SPEC 8)."""
    field = block["idw_pm25"][hour]
    background = inputs.shared["cams_pm25"][hour]
    out = np.where(np.isfinite(field), field, background)
    return out if np.isfinite(out).all() else None


def interval_ratio(model: registry.LoadedModel | None) -> tuple[float, float, bool]:
    """Multiplicative P10/P90 band for the fallback raster, learned from IDW LOSO residuals."""
    ratio = (model.meta.get("idw_interval_ratio") if model else None) or (
        store.read_json(baseline_path(), default={}) or {}
    ).get("idw_interval_ratio")
    if ratio:
        return min(1.0, float(ratio["p10"])), max(1.0, float(ratio["p90"])), True
    return 1.0, 1.0, False  # no labelled data yet: the band has zero width and is flagged


def run(at: datetime | None = None) -> dict[str, Any]:
    """Run inference for the hour containing `at` (default: now) and publish everything."""
    cfg = load_config()
    generated_at = datetime.now(UTC)
    valid_hour = (at or generated_at).astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    inputs = load_inputs(valid_hour)
    grid, shape = inputs.grid, inputs.grid.shape
    block = idw_series(inputs)

    model = registry.load_active()
    drift = monitor.status(model)
    use_model = model is not None and not drift["alarm"]
    low_ratio, high_ratio, has_band = interval_ratio(model)
    reporting = int(np.isfinite(inputs.values[inputs.now]).sum()) if inputs.values.size else 0
    run_dir = rasters_dir() / f"run_{raster.stamp(valid_hour)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    common_metrics: dict[str, float | None] = {
        "stations_reporting": float(reporting),
        "rolling_rmse_24h": drift["rolling_rmse_24h"],
        "drift_alarm": float(drift["alarm"]),
    }

    manifests: dict[int, dict[str, Any]] = {}
    p50_by_lead: dict[int, FloatArray] = {}
    for lead in range(int(cfg["inference"]["horizon_h"]) + 1):
        hour = inputs.now + lead
        arrays: dict[str, FloatArray] | None = None
        quality, version = "real", model.version if model else FALLBACK_VERSION
        if use_model and model is not None:
            x = design(inputs, block, hour, model.feature_names)
            offset = float(model.meta.get("conformal_offset_ug_m3") or 0.0)
            arrays = raster.postprocess(
                np.asarray(model.low.predict(x)).reshape(shape) - offset,
                np.asarray(model.mean.predict(x)).reshape(shape),
                np.asarray(model.high.predict(x)).reshape(shape) + offset,
            )
        else:
            field = fallback_field(inputs, block, hour)
            if field is None:
                log.warning("no station or CAMS value for lead %d; hour skipped", lead)
                continue
            mid = field.reshape(shape)
            arrays = raster.postprocess(mid * low_ratio, mid, mid * high_ratio)
            quality, version = "approximated", FALLBACK_VERSION
        manifests[lead] = raster.write_set(
            raster.RasterSet(
                inputs.hours[hour].to_pydatetime(),
                arrays,
                "nowcast" if lead == 0 else "forecast",
                lead,
                quality,
                version,
            ),
            grid,
            run_dir,
            generated_at,
            common_metrics | {"interval_available": float(use_model or has_band)},
        )
        p50_by_lead[lead] = arrays["p50"]
    if 0 not in manifests:
        raise RuntimeError("No nowcast could be produced: no model, no stations and no CAMS data")

    publish_manifests(manifests, run_dir)
    indices = raster.tile_indices(grid)
    tiles = sum(
        raster.render_tiles(
            p50_by_lead[lead], inputs.hours[inputs.now + lead], indices, tiles_dir()
        )
        for lead in cfg["tiles"]["leads"]
        if lead in p50_by_lead
    )
    publish_api_inputs(inputs, manifests, p50_by_lead)
    if use_model and model is not None:
        monitor.record(inputs, p50_by_lead[0], manifests[0], valid_hour)
    insights.record_hour(inputs.cells, p50_by_lead[0], valid_hour, manifests[0]["data_quality"])
    insights.write_latest()
    retention(valid_hour)
    summary = {
        "valid_hour": manifests[0]["valid_hour"],
        "model_version": manifests[0]["model_version"],
        "data_quality": manifests[0]["data_quality"],
        "hours_published": len(manifests),
        "tiles": tiles,
        "stations_reporting": reporting,
        "drift": drift,
        "seconds": round((datetime.now(UTC) - generated_at).total_seconds(), 1),
    }
    store.write_json(summary, data_dir() / "reports" / "last_inference.json")
    return summary


def publish_manifests(manifests: dict[int, dict[str, Any]], run_dir: Path) -> None:
    """Fill every slot. The API fails its whole reload if one listed manifest is missing, so a
    slot with nothing of its own (first run, skipped hour) repeats the current nowcast."""
    cfg = load_config()["inference"]
    folder = manifests_dir()
    for lead, manifest in manifests.items():
        store.write_json(manifest, run_dir / f"manifest_{lead:02d}.json")
    previous = store.read_json(folder / "nowcast.json")
    now_hour = datetime.fromisoformat(manifests[0]["valid_hour"])
    recent = int(cfg["recent_slots"])
    history: dict[datetime, dict[str, Any]] = {}
    for k in range(1, recent + 1):
        old = store.read_json(folder / f"nowcast_minus_{k:02d}.json")
        if old is not None:
            history[datetime.fromisoformat(old["valid_hour"])] = old
    if previous is not None:
        history[datetime.fromisoformat(previous["valid_hour"])] = previous
    for k in range(1, recent + 1):
        wanted = history.get(now_hour - timedelta(hours=k))
        usable = wanted is not None and all(
            (data_dir() / name).is_file() for name in wanted["files"].values()
        )
        store.write_json(wanted if usable else manifests[0], folder / f"nowcast_minus_{k:02d}.json")
    for lead in range(1, int(cfg["horizon_h"]) + 1):
        store.write_json(
            manifests.get(lead, manifests[0]), folder / f"forecast_plus_{lead:02d}.json"
        )
    store.write_json(manifests[0], folder / "nowcast.json")


def publish_api_inputs(
    inputs: Inputs, manifests: dict[int, dict[str, Any]], p50_by_lead: dict[int, FloatArray]
) -> None:
    """`HIRUP_AQ_INPUTS` (station + CAMS fallback) and `HIRUP_CITY_MEDIANS` (C_ref, SPEC 12)."""
    stations = []
    latest = inputs.values[inputs.now] if inputs.values.size else np.array([])
    for station, value in zip(inputs.stations.itertuples(index=False), latest, strict=True):
        if np.isfinite(value):
            stations.append(
                {
                    "point": {"lon": float(station.lon), "lat": float(station.lat)},
                    "valid_hour": manifests[0]["valid_hour"],
                    "pm25": {"p10": float(value), "p50": float(value), "p90": float(value)},
                }
            )
    cams = {}
    for lead, manifest in manifests.items():
        value = inputs.cams_mean[inputs.now + lead]
        if np.isfinite(value):
            cams[manifest["valid_hour"]] = {
                "p10": float(value),
                "p50": float(value),
                "p90": float(value),
            }
    store.write_json(
        {
            "data_quality": "approximated",
            "source": "QC-passed OpenAQ/WAQI station hours and CAMS global PM2.5 (Open-Meteo)",
            "generated_at": manifests[0]["generated_at"],
            "stations": stations,
            "cams": cams,
        },
        data_dir() / "aq_inputs.json",
    )
    medians = {
        manifest["valid_hour"]: {
            "value": float(np.median(p50_by_lead[lead])),
            "source": "median of the pilot-area P50 raster "
            f"({manifest['model_version']}, {manifest['kind']})",
        }
        for lead, manifest in manifests.items()
    }
    store.write_json(medians, data_dir() / "city_medians.json")


def retention(valid_hour: datetime) -> None:
    """Keep 7 days of nowcasts (SPEC 10.3), forecasts of the last few runs, and recent tiles.
    Files still referenced by a manifest slot are never removed."""
    cfg = load_config()
    referenced = set()
    for name in slot_names():
        manifest = store.read_json(manifests_dir() / name)
        if manifest:
            referenced |= {(data_dir() / f).resolve() for f in manifest["files"].values()}
    days, runs = (
        int(cfg["inference"]["retention_days"]),
        int(cfg["inference"]["keep_forecast_runs"]),
    )
    for run_dir in sorted(rasters_dir().glob("run_*")):
        try:
            run_hour = datetime.strptime(run_dir.name[4:], "%Y%m%d%H").replace(tzinfo=raster.LOCAL)
        except ValueError:
            continue
        age = valid_hour - run_hour.astimezone(UTC)
        if age <= timedelta(hours=runs):
            continue
        if age > timedelta(days=days):
            insights.archive_daily(run_hour.date())
        for path in run_dir.glob("pm25_*.tif"):
            is_nowcast = path.name.split("_")[1] == run_dir.name[4:]
            expired = age > timedelta(days=days) or not is_nowcast
            if expired and path.resolve() not in referenced:
                path.unlink(missing_ok=True)
        if not any(run_dir.glob("pm25_*.tif")):
            shutil.rmtree(run_dir, ignore_errors=True)
    keep = timedelta(hours=int(cfg["tiles"]["keep_hours"]))
    for folder in tiles_dir().glob("[0-9]" * 10):
        hour = datetime.strptime(folder.name, "%Y%m%d%H").replace(tzinfo=raster.LOCAL)
        if valid_hour - hour.astimezone(UTC) > keep:
            shutil.rmtree(folder, ignore_errors=True)
