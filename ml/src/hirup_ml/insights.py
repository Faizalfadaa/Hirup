"""Insight Kota data (FR-30, FR-31): mean PM2.5 per kelurahan from the model raster and an
inequality index. No user data is involved (SPEC 15).

Index (methodology, shown in the app): for each kelurahan take the percentile rank (0..1)
among pilot kelurahan of
    E = mean PM2.5 over the period        (high exposure)
    G = 1 - rank of green cover fraction   (little green space)
    P = population density                 (many people affected)
and combine them as the geometric mean (E * G * P)^(1/3). 1 is the highest priority.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import numpy.typing as npt
import pandas as pd
import rasterio

from hirup_ml import raster
from hirup_ml.config import FALLBACK_VERSION, insights_dir, load_config, rasters_dir
from hirup_pipelines import paths, store
from hirup_pipelines.grid import CRS, pilot_grid
from hirup_pipelines.settings import TIMEZONE

KEYS = ["kelurahan_id", "ts"]


def hourly_path() -> Any:
    return insights_dir() / "kelurahan_hourly.parquet"


def record_hour(
    cells: pd.DataFrame,
    p50: npt.NDArray[np.float64],
    valid_hour: datetime,
    quality: str,
    *,
    manifest: dict[str, Any] | None = None,
) -> None:
    """Append the nowcast mean of every kelurahan for one hour."""
    if "kelurahan_id" not in cells or cells["kelurahan_id"].isna().all():
        return
    frame = pd.DataFrame({"kelurahan_id": cells["kelurahan_id"], "pm25": p50.ravel()}).dropna()
    means = frame.groupby("kelurahan_id")["pm25"].mean().rename("mean_pm25").reset_index()
    means["kelurahan_id"] = means["kelurahan_id"].astype(str)
    means["ts"] = pd.Timestamp(valid_hour).tz_convert("UTC")
    means["data_quality"] = quality
    if manifest is not None:
        boundary = store.read_json(paths.boundaries() / "latest.json", default={})
        means["boundaries_version"] = boundary.get("boundaries_version")
        means["generated_at"] = pd.Timestamp(manifest["generated_at"])
        means["kind"] = manifest["kind"]
        means["model_version"] = manifest["model_version"]
        old = store.read_parquet(hourly_path())
        if old is not None and "kind" in old and manifest["kind"] == "forecast":
            # A replay must not replace an observed nowcast with an earlier forecast.
            protected = old[(old["ts"] == means["ts"].iloc[0]) & (old["kind"] == "nowcast")]
            means = means[~means["kelurahan_id"].isin(protected["kelurahan_id"])]
    if not means.empty:
        store.upsert(means, hourly_path(), KEYS)


def write_daily(run_dir: Path, generated_at: datetime) -> Path | None:
    """P1's complete-day adapter: never publish partial days or an unapproved index."""
    try:
        static = kelurahan_static()
    except (RuntimeError, FileNotFoundError, KeyError):
        return None
    static = static[static["coverage"] >= float(load_config()["insights"]["min_coverage"])]
    hourly = store.read_parquet(hourly_path())
    required = {"boundaries_version", "generated_at", "kind", "model_version"}
    if static.empty or hourly is None or not required.issubset(hourly):
        return None
    version = static.attrs["boundaries_version"]
    hourly = hourly[hourly["boundaries_version"] == version].copy()
    local = hourly["ts"].dt.tz_convert(TIMEZONE)
    today = generated_at.astimezone(raster.LOCAL).date()
    hourly["date"], hourly["hour"] = local.dt.date, local.dt.hour
    roster = set(static["kelurahan_id"].astype(str))
    days = []
    for day, window in hourly.groupby("date"):
        if day < today - timedelta(days=7) or day > today:
            continue
        window = window[window["kelurahan_id"].isin(roster)]
        groups = {str(key): group for key, group in window.groupby("kelurahan_id")}
        if set(groups) != roster or any(
            len(group) != 24 or set(group["hour"]) != set(range(24)) for group in groups.values()
        ):
            continue
        if window["generated_at"].isna().any() or (window["generated_at"] > generated_at).any():
            continue
        qualities = set(window["data_quality"])
        forecast = day == today or (window["kind"] == "forecast").any()
        models = sorted(set(window["model_version"].dropna().astype(str)))
        days.append(
            {
                "date": day.isoformat(),
                "boundaries_version": version,
                "generated_at": generated_at.isoformat(),
                "source_kind": "model"
                if models and all(m != FALLBACK_VERSION for m in models)
                else "cams",
                "model_version": ",".join(models) or None,
                "contains_forecast": bool(forecast),
                "data_quality": "synthetic"
                if "synthetic" in qualities
                else "approximated"
                if forecast or "approximated" in qualities
                else "real",
                "items": [
                    {
                        "kelurahan_id": key,
                        "mean_pm25": float(group["mean_pm25"].mean()),
                        "hours_covered": list(range(24)),
                    }
                    for key, group in sorted(groups.items())
                ],
            }
        )
    if not days:
        return None
    target = run_dir / "kelurahan_daily.json"
    store.write_json(
        {
            "source": "P2 hourly P50 raster means over 100 m pilot cells by kelurahan",
            "aggregation_method": (
                "equal-weight cell means per hour, then 24 equally weighted WIB hours"
            ),
            "units": "ug/m3",
            "boundaries_version": version,
            "regions": [
                {
                    "kelurahan_id": str(row.kelurahan_id),
                    "name": row.name,
                    "kecamatan": row.kecamatan,
                }
                for row in static.itertuples(index=False)
            ],
            "days": days,
        },
        target,
    )
    return target


def kelurahan_static() -> pd.DataFrame:
    """Per kelurahan: name, kecamatan, green fraction, population density, grid coverage."""
    cells = store.read_parquet(paths.grid_cells())
    latest = store.read_json(paths.boundaries() / "latest.json")
    if cells is None or latest is None:
        raise RuntimeError("Run `hirup-pipelines static` first")
    cells = cells.dropna(subset=["kelurahan_id"])
    cells = cells.assign(green=cells["wc_frac_tree_100m"] + cells["wc_frac_lowveg_100m"])
    per = cells.groupby("kelurahan_id").agg(
        green_fraction=("green", "mean"),
        pop_density=("pop_density", "mean"),
        cells=("cell_id", "size"),
    )
    boundaries = gpd.read_file(paths.boundaries() / latest["path"]).to_crs(CRS)
    boundaries["area_km2"] = boundaries.geometry.area / 1e6
    out = boundaries.drop(columns="geometry").merge(per, on="kelurahan_id", how="inner")
    out["coverage"] = np.clip(out["cells"] * (pilot_grid().res ** 2 / 1e6) / out["area_km2"], 0, 1)
    out.attrs["boundaries_version"] = latest["boundaries_version"]
    return out


def percentile_rank(values: pd.Series) -> pd.Series:
    """Rank in [0, 1]; ties share the mean rank, a single distinct value maps to 0.5."""
    if values.nunique() <= 1:
        return pd.Series(0.5, index=values.index)
    return (values.rank(method="average") - 1) / (len(values) - 1)


def summarise(start: date, end: date, hours: list[int] | None = None) -> dict[str, Any]:
    """The `GET /v1/insights/kelurahan` payload for local dates [start, end], optionally
    restricted to local hours of day (FR-30 "filter jam dan hari")."""
    static = kelurahan_static()
    static = static[static["coverage"] >= float(load_config()["insights"]["min_coverage"])]
    hourly = store.read_parquet(hourly_path())
    if hourly is None:
        raise RuntimeError("No hourly insight data yet; run `hirup-ml predict` first")
    local = hourly["ts"].dt.tz_convert(TIMEZONE)
    keep = (local.dt.date >= start) & (local.dt.date <= end)
    if hours is not None:
        keep &= local.dt.hour.isin(hours)
    window = hourly[keep]
    means = window.groupby("kelurahan_id")["mean_pm25"].mean()
    frame = static.merge(means, on="kelurahan_id", how="inner")
    exposure = percentile_rank(frame["mean_pm25"])
    green = 1 - percentile_rank(frame["green_fraction"])
    people = percentile_rank(frame["pop_density"])
    frame["inequality_index"] = np.cbrt(exposure * green * people)
    frame["priority_rank"] = (
        frame["inequality_index"].rank(method="first", ascending=False).astype(int)
    )
    frame = frame.sort_values("priority_rank")
    qualities = set(window["data_quality"])
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "boundaries_version": static.attrs["boundaries_version"],
        "items": [
            {
                "kelurahan_id": row.kelurahan_id,
                "name": row.name,
                "kecamatan": row.kecamatan if isinstance(row.kecamatan, str) else "",
                "mean_pm25": round(float(row.mean_pm25), 2),
                "inequality_index": round(float(row.inequality_index), 4),
                "priority_rank": int(row.priority_rank),
                "green_fraction": round(float(row.green_fraction), 4),
                "pop_density_km2": round(float(row.pop_density), 1),
            }
            for row in frame.itertuples(index=False)
        ],
        # Any fallback hour in the window makes the whole answer `approximated`.
        "data_quality": "real" if qualities == {"real"} else "approximated",
        "hours_in_window": int(window["ts"].nunique()),
    }


def write_latest() -> dict[str, Any] | None:
    """Refresh `insights/kelurahan_latest.json` for the last `window_days` days."""
    try:
        today = datetime.now(UTC).astimezone(raster.LOCAL).date()
        window = int(load_config()["insights"]["window_days"])
        payload = summarise(today - timedelta(days=window), today)
    except (RuntimeError, FileNotFoundError, KeyError):
        return None  # boundaries not built yet; the rasters are still published
    store.write_json(payload, insights_dir() / "kelurahan_latest.json")
    return payload


def archive_daily(day: date) -> None:
    """Daily mean P50 raster from that day's nowcasts (SPEC 10.3 "arsip rata-rata harian")."""
    target = rasters_dir() / "daily" / f"pm25_daily_{day:%Y%m%d}.tif"
    if target.is_file():
        return
    stack = []
    for hour in range(24):
        key = raster.stamp(datetime.combine(day, time(hour), tzinfo=raster.LOCAL))
        candidates = [
            store.read_json(path) for path in rasters_dir().glob(f"run_{key}*/manifest_00.json")
        ]
        candidates = [m for m in candidates if m and m["kind"] == "nowcast"]
        if not candidates:
            return  # Never freeze an incomplete day as a daily archive.
        manifest = max(candidates, key=lambda m: m["generated_at"])
        from hirup_pipelines.settings import data_dir

        path = data_dir() / manifest["files"]["p50"]
        if not path.is_file():
            return
        with rasterio.open(path) as src:
            stack.append(src.read(1).astype(float))
    if len(stack) == 24:
        raster.write_cog(target, np.mean(stack, axis=0), pilot_grid())
