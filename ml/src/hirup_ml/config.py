"""ML config and artefact locations."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

from hirup_pipelines.settings import ROOT, data_dir

ML_ROOT = ROOT / "ml"
CONFIG_PATH = ML_ROOT / "configs" / "model.yaml"
MANIFEST_SCHEMA = ROOT / "contracts" / "schemas" / "raster_manifest.schema.json"
FALLBACK_VERSION = "idw-cams-v1"


@cache
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    return loaded


def models_dir() -> Path:
    """Model binaries (gitignored). `HIRUP_DATA_DIR` moves them too, which keeps tests isolated."""
    custom = data_dir()
    return ML_ROOT / "models" if custom == ROOT / "data" else custom / "models"


def registry_path() -> Path:
    """Metrics only, no data: committed so the team sees every trained model (Lampiran B)."""
    custom = data_dir()
    return (
        ML_ROOT / "model_registry.json"
        if custom == ROOT / "data"
        else custom / "model_registry.json"
    )


def rasters_dir() -> Path:
    return data_dir() / "rasters"


def manifests_dir() -> Path:
    return data_dir() / "manifests"


def tiles_dir() -> Path:
    return data_dir() / "tiles"


def insights_dir() -> Path:
    return data_dir() / "insights"


def monitor_path() -> Path:
    return data_dir() / "monitor" / "nowcast_at_stations.parquet"


def baseline_path() -> Path:
    return data_dir() / "reports" / "baseline.json"
