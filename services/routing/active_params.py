"""Load active-route design parameters from the frozen exposure contract."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "contracts/exposure_params.yaml"


@dataclass(frozen=True, slots=True)
class ActiveParams:
    walk_speed_m_s: float
    bike_speed_m_s: float
    max_detour_frac: float
    max_detour_s: float
    lambdas: tuple[float, ...]
    sample_spacing_m: float


def load_active_params(path: Path = DEFAULT_PATH) -> ActiveParams:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise ValueError("Invalid exposure parameter document")
    section = document.get("active_routing")
    if not isinstance(section, Mapping):
        raise ValueError("Missing active_routing contract section")

    def value(name: str) -> Any:
        leaf = section.get(name)
        if not isinstance(leaf, Mapping) or not leaf.get("source"):
            raise ValueError(f"Missing active-routing parameter or source: {name}")
        return leaf.get("value")

    def number(name: str, *, allow_zero: bool = False) -> float:
        raw = value(name)
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise ValueError(f"Invalid active-routing parameter: {name}")
        parsed = float(raw)
        if not math.isfinite(parsed) or parsed < 0 or (parsed == 0 and not allow_zero):
            raise ValueError(f"Invalid active-routing parameter: {name}")
        return parsed

    weights = value("lambdas")
    if not isinstance(weights, list) or not weights:
        raise ValueError("Invalid active-routing lambdas")
    parsed_weights: list[float] = []
    for weight in weights:
        if (
            isinstance(weight, bool)
            or not isinstance(weight, int | float)
            or not math.isfinite(weight)
            or weight < 0
        ):
            raise ValueError("Invalid active-routing lambda")
        parsed_weights.append(float(weight))
    if 0 not in parsed_weights:
        raise ValueError("Active-routing lambdas must include the baseline zero")
    return ActiveParams(
        number("walk_speed_m_s"),
        number("bike_speed_m_s"),
        number("max_detour_frac", allow_zero=True),
        number("max_detour_s"),
        tuple(dict.fromkeys(parsed_weights)),
        number("sample_spacing_m"),
    )
