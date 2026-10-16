"""Paths, pilot bounds and the pipeline config. Secrets come from the process environment only."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("HIRUP_PROJECT_ROOT") or Path(__file__).resolve().parents[3])
CONFIG_PATH = ROOT / "pipelines" / "configs" / "pipeline.yaml"
TIMEZONE = "Asia/Jakarta"
USER_AGENT = "hirup-pipelines/0.1 (JOINTS 2026 student project)"


@dataclass(frozen=True, slots=True)
class BBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def expand_km(self, km: float) -> BBox:
        dlat = km / 110.574
        dlon = km / (111.320 * math.cos(math.radians((self.min_lat + self.max_lat) / 2)))
        return BBox(
            self.min_lat - dlat, self.max_lat + dlat, self.min_lon - dlon, self.max_lon + dlon
        )

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


def data_dir() -> Path:
    return Path(os.environ.get("HIRUP_DATA_DIR") or ROOT / "data")


def pilot_bbox() -> BBox:
    """The frozen pilot bounds live in the golden OD contract (SPEC 6.1)."""
    raw = json.loads((ROOT / "contracts" / "golden_od.json").read_text(encoding="utf-8"))
    return BBox(**raw["bbox"])


@cache
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    return loaded


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set; export it in the shell (see .env.example)")
    return value
