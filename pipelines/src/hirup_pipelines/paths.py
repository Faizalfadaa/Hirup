"""Where each SPEC 10.3 artefact lives under `data/` (gitignored)."""

from __future__ import annotations

from pathlib import Path

from hirup_pipelines.settings import data_dir


def raw_stations() -> Path:
    return data_dir() / "raw" / "stations.parquet"


def raw_observations() -> Path:
    return data_dir() / "raw" / "observations"


def stations() -> Path:
    return data_dir() / "stations.parquet"


def observations() -> Path:
    return data_dir() / "aq_observations"


def weather() -> Path:
    return data_dir() / "weather_hourly.parquet"


def cams() -> Path:
    return data_dir() / "cams_hourly.parquet"


def grid_cells() -> Path:
    return data_dir() / "grid_cells.parquet"


def features() -> Path:
    return data_dir() / "features"


def station_static() -> Path:
    return features() / "station_static.parquet"


def boundaries() -> Path:
    return data_dir() / "boundaries"


def reports() -> Path:
    return data_dir() / "reports"
