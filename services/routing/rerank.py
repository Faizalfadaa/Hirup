"""Pure Pareto selection and profile labels using sourced contract parameters."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from services.routing.models import Profile, ScoredCandidate, Selected

PARAMS_PATH = Path(__file__).resolve().parents[2] / "contracts/exposure_params.yaml"


@dataclass(frozen=True, slots=True)
class RankingParams:
    transfer_penalty_s: float
    alpha: float
    tolerance_min_s: float
    tolerance_frac: float


def load_ranking_params(profile: Profile, path: Path = PARAMS_PATH) -> RankingParams:
    doc: Any = yaml.safe_load(path.read_text(encoding="utf-8"))["ranking"]
    fields = [
        doc["transfer_penalty_s"],
        *(
            doc["profiles"][profile][name]
            for name in ("alpha", "cleanest_tolerance_min_s", "cleanest_tolerance_frac")
        ),
    ]
    values = []
    for field in fields:
        value = field["value"]
        if not field.get("source") or isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Missing ranking value or source")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Invalid ranking value")
        values.append(float(value))
    if values[1] > 1:
        raise ValueError("Ranking alpha must be in [0, 1]")
    return RankingParams(*values)


def select(options: Sequence[ScoredCandidate], params: RankingParams) -> tuple[Selected, ...]:
    if not options:
        return ()
    # Stable deduplication: identical mode/geometry/route sequences represent one choice.
    unique: dict[tuple[object, ...], ScoredCandidate] = {}
    for option in options:
        key = tuple(
            (leg.mode, leg.points, leg.route, leg.duration_s) for leg in option.candidate.legs
        )
        unique.setdefault(key, option)
    pool = list(unique.values())

    def time(option: ScoredCandidate) -> float:
        return option.candidate.duration_s + params.transfer_penalty_s * option.candidate.transfers

    def dose(option: ScoredCandidate) -> float:
        return option.exposure.dose_ug.p50

    frontier = [
        a
        for a in pool
        if not any(
            time(b) <= time(a) and dose(b) <= dose(a) and (time(b) < time(a) or dose(b) < dose(a))
            for b in pool
        )
    ]
    fastest = min(pool, key=lambda a: (a.candidate.duration_s, dose(a)))
    limit = fastest.candidate.duration_s + max(
        params.tolerance_min_s, params.tolerance_frac * fastest.candidate.duration_s
    )
    cleanest = min(
        (a for a in pool if a.candidate.duration_s <= limit), key=lambda a: (dose(a), time(a))
    )
    t_min, d_min = min(map(time, frontier)), min(map(dose, frontier))

    def balanced_score(a: ScoredCandidate) -> tuple[float, float, float]:
        # Zero-dose/zero-duration cases are exact; no arbitrary epsilon is introduced.
        t_ratio = time(a) / t_min if t_min else (0 if time(a) == 0 else math.inf)
        d_ratio = dose(a) / d_min if d_min else (0 if dose(a) == 0 else math.inf)
        score = (params.alpha * t_ratio if params.alpha else 0) + (
            (1 - params.alpha) * d_ratio if params.alpha < 1 else 0
        )
        return score, time(a), dose(a)

    balanced = min(frontier, key=balanced_score)
    chosen: list[tuple[ScoredCandidate, list[str]]] = []
    for option, label in ((fastest, "fastest"), (cleanest, "cleanest"), (balanced, "balanced")):
        existing = next((labels for item, labels in chosen if item is option), None)
        if existing is None:
            chosen.append((option, [label]))
        else:
            existing.append(label)
    return tuple(
        Selected(
            option,
            tuple(labels),
            100 * (dose(option) - dose(fastest)) / dose(fastest) if dose(fastest) else 0,
            round(option.candidate.duration_s - fastest.candidate.duration_s),
        )
        for option, labels in chosen
    )
