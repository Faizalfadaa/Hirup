from datetime import datetime

import pytest

from services.exposure.engine import LegInput, Mode, Quantiles, trip_exposure
from services.exposure.geometry import Point
from services.exposure.params import UnverifiedParamsWarning, load_params
from services.routing.models import Candidate, RouteLeg, ScoredCandidate
from services.routing.rerank import load_ranking_params, select

TS = datetime.fromisoformat("2026-10-14T06:30:00+07:00")


def scored(duration: float, dose: float, marker: float) -> ScoredCandidate:
    points = (Point(106.8, -6.2), Point(106.8 + marker / 1000, -6.2))
    leg = RouteLeg(Mode.WALK, duration, 100, points)
    with pytest.warns(UnverifiedParamsWarning):
        params = load_params()
    concentration = dose / (1.15 * 1.2 * duration / 3600) if duration else 0
    exposure = trip_exposure(
        [LegInput(Mode.WALK, duration, Quantiles(concentration, concentration, concentration))],
        params,
    )
    return ScoredCandidate(
        Candidate((leg,), TS, "synthetic"), exposure, "synthetic", ((concentration,),)
    )


def test_profile_changes_cleanest_and_balanced() -> None:
    choices = [scored(600, 10, 1), scored(1200, 7, 2), scored(1500, 3, 3)]
    common = select(choices, load_ranking_params("umum"))
    vulnerable = select(choices, load_ranking_params("rentan"))
    assert next(x.scored for x in common if "fastest" in x.labels) is choices[0]
    assert next(x.scored for x in common if "cleanest" in x.labels) is choices[1]
    assert next(x.scored for x in vulnerable if "cleanest" in x.labels) is choices[2]
    assert next(x.scored for x in vulnerable if "balanced" in x.labels) is choices[2]


def test_identical_option_merges_all_labels() -> None:
    one = scored(600, 10, 1)
    selected = select([one, one], load_ranking_params("umum"))
    assert len(selected) == 1
    assert selected[0].labels == ("fastest", "cleanest", "balanced")
    assert selected[0].dose_delta_pct == 0


def test_dominated_option_not_balanced() -> None:
    choices = [scored(600, 10, 1), scored(900, 12, 2)]
    assert len(select(choices, load_ranking_params("umum"))) == 1


def test_zero_dose_duration_and_empty_pool() -> None:
    assert select([], load_ranking_params("umum")) == ()
    zero = scored(0, 0, 1)
    assert select([zero, scored(100, 0, 2)], load_ranking_params("umum"))[0].scored is zero


def test_hand_computed_deltas() -> None:
    selected = select([scored(600, 10, 1), scored(900, 5, 2)], load_ranking_params("umum"))
    clean = next(x for x in selected if "cleanest" in x.labels)
    assert clean.dose_delta_pct == pytest.approx(-50)
    assert clean.duration_delta_s == 300
