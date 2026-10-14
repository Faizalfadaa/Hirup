"""`model_registry.json` (SPEC 10.3) and the promotion rules (SPEC 11.5, gate G2)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import lightgbm as lgb

from hirup_ml.config import load_config, models_dir, registry_path
from hirup_pipelines import store

log = logging.getLogger(__name__)


def entries() -> list[dict[str, Any]]:
    return list(store.read_json(registry_path(), default=[]))


def active() -> dict[str, Any] | None:
    return next((entry for entry in entries() if entry.get("is_active")), None)


def next_version() -> str:
    """`lgbm-<ISO year>w<ISO week>`, suffixed when the week already has a model."""
    year, week, _ = datetime.now(UTC).isocalendar()
    base = f"lgbm-{year}w{week:02d}"
    taken = {entry["model_version"] for entry in entries()}
    if base not in taken:
        return base
    return next(f"{base}-{n}" for n in range(2, 1000) if f"{base}-{n}" not in taken)


def promotion_decision(entry: dict[str, Any], current: dict[str, Any] | None) -> tuple[bool, str]:
    new, idw = entry["metrics"].get("loso_rmse"), entry["metrics"].get("idw_loso_rmse")
    if new is None:
        return False, "no LOSO RMSE"
    # Gate G2: the model must beat the IDW baseline, otherwise the fallback is served.
    if idw is not None and new >= idw:
        return False, f"gate G2 failed: LOSO RMSE {new:.2f} is not below IDW {idw:.2f}"
    if current is None:
        return True, "first model that beats IDW"
    limit = current["metrics"]["loso_rmse"] * (
        1 + load_config()["promotion"]["max_rmse_regression"]
    )
    if new > limit:
        return False, f"LOSO RMSE {new:.2f} is more than 5% worse than active {limit:.2f}"
    return True, "LOSO RMSE within 5% of the active model or better"


def register(entry: dict[str, Any]) -> dict[str, Any]:
    """Append a model; it becomes active only when the promotion rules allow it."""
    existing = entries()
    promote, reason = promotion_decision(entry, active())
    entry = entry | {"is_active": promote, "promotion": reason}
    if promote:
        existing = [old | {"is_active": False} for old in existing]
    store.write_json([*existing, entry], registry_path())
    log.info(
        "%s: %s (%s)", entry["model_version"], "promoted" if promote else "not promoted", reason
    )
    return entry


@dataclass
class LoadedModel:
    version: str
    meta: dict[str, Any]
    mean: lgb.Booster
    low: lgb.Booster
    high: lgb.Booster

    @property
    def feature_names(self) -> list[str]:
        return list(self.meta["feature_names"])


def load_active() -> LoadedModel | None:
    entry = active()
    if entry is None:
        return None
    folder = models_dir() / entry["model_version"]
    meta = store.read_json(folder / "meta.json")
    if meta is None:
        log.warning("active model %s has no files on this machine", entry["model_version"])
        return None
    return LoadedModel(
        entry["model_version"],
        meta,
        lgb.Booster(model_file=str(folder / "mean.txt")),
        lgb.Booster(model_file=str(folder / "q10.txt")),
        lgb.Booster(model_file=str(folder / "q90.txt")),
    )
