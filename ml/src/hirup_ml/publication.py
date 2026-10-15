"""Publish complete, immutable runs behind one atomic pointer consumed by P1."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hirup_ml.config import load_config
from hirup_pipelines import paths, store
from hirup_pipelines.settings import TIMEZONE, data_dir, pilot_bbox


def history(run_dir: Path, generated_at: datetime) -> Path | None:
    """Observed regional hour-of-week quantiles; no current raster is repeated as history."""
    observed = store.read_daily(paths.observations())
    if observed.empty:
        return None
    local = observed["ts"].dt.tz_convert(TIMEZONE)
    usable = observed[(observed["qc_flag"] == "ok") & (local.dt.date < generated_at.date())]
    if usable.empty:
        return None
    hourly = usable.groupby("ts")["value_cal"].mean().dropna()
    local_hours = hourly.index.tz_convert(TIMEZONE)
    keys = [f"{ts.dayofweek}:{ts.hour:02d}" for ts in local_hours]
    hours = {}
    for key, values in hourly.groupby(keys):
        quantiles = values.quantile([0.1, 0.5, 0.9])
        hours[str(key)] = dict(zip(("p10", "p50", "p90"), map(float, quantiles), strict=True))
    box = pilot_bbox()
    target = run_dir / "history.json"
    store.write_json(
        {
            "source": "QC-passed OpenAQ/WAQI regional station means, grouped by WIB weekday/hour",
            "data_quality": "approximated",
            "units": "ug/m3",
            "period_start": min(local_hours.date).isoformat(),
            "period_end": max(local_hours.date).isoformat(),
            "bbox_wgs84": {
                name: getattr(box, name) for name in ("min_lat", "max_lat", "min_lon", "max_lon")
            },
            "hours": hours,
        },
        target,
    )
    return target


def commit(
    manifests: dict[int, dict[str, Any]],
    run_dir: Path,
    generated_at: datetime,
    historical: Path | None,
    kelurahan: Path | None,
    *,
    tiles_available: bool = False,
) -> None:
    """Archive real hourly publications and replace the public index only after all writes."""
    root = data_dir()
    old = store.read_json(root / "aq_publication.json", default={})
    cutoff = generated_at - timedelta(days=int(load_config()["inference"]["retention_days"]))
    retained: dict[str, str] = {}
    for relative in old.get("manifests", []):
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Previous publication escapes the data root")
        previous = store.read_json(path)
        if (
            previous
            and previous["kind"] == "nowcast"
            and datetime.fromisoformat(previous["valid_hour"]) >= cutoff
        ):
            retained[previous["valid_hour"]] = relative
    for lead, manifest in manifests.items():
        path = run_dir / f"manifest_{lead:02d}.json"
        store.write_json(manifest, path)
        retained[manifest["valid_hour"]] = path.relative_to(root).as_posix()
    payload = {
        "version": 1,
        "generated_at": generated_at.isoformat(),
        "manifests": list(retained.values()),
        "fallback": (run_dir / "aq_inputs.json").relative_to(root).as_posix(),
        "medians": (run_dir / "city_medians.json").relative_to(root).as_posix(),
        "history": historical.relative_to(root).as_posix() if historical else None,
        "kelurahan": kelurahan.relative_to(root).as_posix() if kelurahan else None,
        "tiles_available": tiles_available,
    }
    # Single commit point: readers either see the previous run or this complete run.
    store.write_json(payload, root / "aq_publication.json")
