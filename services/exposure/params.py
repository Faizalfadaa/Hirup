"""Load and validate contracts/exposure_params.yaml.

This is the only module in `services.exposure` that touches the file system. Missing or
malformed fields fail hard with `ParamsError`; values whose `verified_by` is still null
raise one `UnverifiedParamsWarning` per load.

Optional values that the spec does not give yet are kept as None. When a human fills them
in, they must be mappings keyed by micro-environment name:
- `emission_factors.value`: {motorcycle: kg/km, car: kg/km, bus: kg/passenger-km, rail: ...}
- `fuel_cost.value`: {motorcycle: IDR/km, car: IDR/km}
- `transit_fares.value`: {bus: IDR per trip, rail: IDR per trip}
"""

import math
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "exposure_params.yaml"

ENTRY_KEYS = frozenset({"value", "range", "unit", "source", "verified_by", "note"})
LEG_MODES = ("WALK", "BICYCLE", "BUS", "SUBWAY", "RAIL", "MOTORCYCLE", "CAR")
WAIT_KEYS = ("WAIT_stop", "WAIT_station")


class ParamsError(ValueError):
    """exposure_params.yaml is missing a field or has an invalid value."""


class UnverifiedParamsWarning(UserWarning):
    """Some parameters have not been verified against their source by a human."""


@dataclass(frozen=True, slots=True)
class MicroEnvironment:
    f: float
    f_range: tuple[float, float]
    vr_m3_h: float


@dataclass(frozen=True, slots=True)
class ExposureParams:
    micro_environment: Mapping[str, MicroEnvironment]
    mode_mapping: Mapping[str, str]
    ugh_m3_per_cigarette: float
    vr_m3_day: float
    f_indoor: float | None
    emission_factors: Mapping[str, float] | None
    fuel_cost_idr_per_km: Mapping[str, float] | None
    transit_fares_idr: Mapping[str, float] | None
    sources: Mapping[str, str]
    unverified: tuple[str, ...]


def load_params(path: Path = DEFAULT_PATH) -> ExposureParams:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ParamsError(f"{path}: file not found") from exc
    if not isinstance(data, Mapping):
        raise ParamsError(f"{path}: top level must be a mapping")
    params = parse_params(data)
    if params.unverified:
        warnings.warn(
            f"{len(params.unverified)} exposure parameters have verified_by: null "
            f"(e.g. {', '.join(params.unverified[:3])})",
            UnverifiedParamsWarning,
            stacklevel=2,
        )
    return params


def parse_params(data: Mapping[str, Any]) -> ExposureParams:
    entries = dict(_collect_entries({k: v for k, v in data.items() if k != "mode_mapping"}))

    environments = {
        name: _parse_environment(name, env)
        for name, env in _mapping(data, "micro_environment").items()
    }
    mode_mapping = {str(k): str(v) for k, v in _mapping(data, "mode_mapping").items()}
    for key in (*LEG_MODES, *WAIT_KEYS):
        if key not in mode_mapping:
            raise ParamsError(f"mode_mapping.{key}: missing")
        if mode_mapping[key] not in environments:
            env = mode_mapping[key]
            raise ParamsError(f"mode_mapping.{key}: unknown micro_environment {env!r}")

    return ExposureParams(
        micro_environment=environments,
        mode_mapping=mode_mapping,
        ugh_m3_per_cigarette=_required(entries, "cigarette.ugh_m3_per_cigarette"),
        vr_m3_day=_required(entries, "daily.vr_m3_day"),
        f_indoor=_optional(entries, "daily.f_indoor"),
        emission_factors=_optional_table(entries, "emission_factors"),
        fuel_cost_idr_per_km=_optional_table(entries, "fuel_cost"),
        transit_fares_idr=_optional_table(entries, "transit_fares"),
        sources={path: str(entry["source"]) for path, entry in entries.items()},
        unverified=tuple(path for path, entry in entries.items() if entry["verified_by"] is None),
    )


def _collect_entries(node: Any, path: str = "") -> list[tuple[str, Mapping[str, Any]]]:
    """Leaf entries are mappings with a `value` key; validate their provenance fields."""
    if not isinstance(node, Mapping):
        return []
    if "value" in node:
        missing = ENTRY_KEYS - set(node)
        if missing:
            raise ParamsError(f"{path}: missing {', '.join(sorted(missing))}")
        if not node["source"]:
            raise ParamsError(f"{path}: empty source")
        return [(path, node)]
    return [e for k, v in node.items() for e in _collect_entries(v, f"{path}.{k}".lstrip("."))]


def _mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping) or not value:
        raise ParamsError(f"{key}: missing or empty")
    return value


def _positive(path: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ParamsError(f"{path}: expected a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ParamsError(f"{path}: must be a positive number, got {value!r}")
    return number


def _leaf(env: Any, key: str, path: str) -> Mapping[str, Any]:
    node = env.get(key) if isinstance(env, Mapping) else None
    if not isinstance(node, Mapping) or "value" not in node:
        raise ParamsError(f"{path}.{key}: missing")
    return node


def _parse_environment(name: str, env: Any) -> MicroEnvironment:
    path = f"micro_environment.{name}"
    f_entry = _leaf(env, "f", path)
    vr_entry = _leaf(env, "vr_m3_h", path)
    f = _positive(f"{path}.f", f_entry["value"])
    raw_range = f_entry["range"]
    if not isinstance(raw_range, list | tuple) or len(raw_range) != 2:
        raise ParamsError(f"{path}.f.range: expected [low, high]")
    low, high = (_positive(f"{path}.f.range", v) for v in raw_range)
    if not low <= f <= high:
        raise ParamsError(f"{path}.f: {f} outside range [{low}, {high}]")
    vr = _positive(f"{path}.vr_m3_h", vr_entry["value"])
    return MicroEnvironment(f=f, f_range=(low, high), vr_m3_h=vr)


def _entry(entries: Mapping[str, Mapping[str, Any]], path: str) -> Mapping[str, Any]:
    if path not in entries:
        raise ParamsError(f"{path}: missing")
    return entries[path]


def _required(entries: Mapping[str, Mapping[str, Any]], path: str) -> float:
    value = _entry(entries, path)["value"]
    if value is None:
        raise ParamsError(f"{path}: value is required")
    return _positive(path, value)


def _optional(entries: Mapping[str, Mapping[str, Any]], path: str) -> float | None:
    value = _entry(entries, path)["value"]
    return None if value is None else _positive(path, value)


def _optional_table(
    entries: Mapping[str, Mapping[str, Any]], path: str
) -> Mapping[str, float] | None:
    value = _entry(entries, path)["value"]
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ParamsError(f"{path}: expected a mapping keyed by micro_environment")
    return {str(k): _positive(f"{path}.{k}", v) for k, v in value.items()}
