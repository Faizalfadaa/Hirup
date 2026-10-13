"""The OpenAPI examples must validate and obey the SPEC chapter 12 formulas."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

from services.api.schemas import examples as ex
from services.api.schemas.aq import (
    AqForecastResponse,
    AqPointResponse,
    DailySummaryResponse,
    GreenSpacesResponse,
)
from services.api.schemas.health import HealthResponse
from services.api.schemas.insights import KelurahanInsightsResponse
from services.api.schemas.problem import Problem
from services.api.schemas.routes import (
    DepartureAdviceResponse,
    PlanRequest,
    PlanResponse,
)

# Example values are rounded to 0.1, so they may differ from the exact result by 0.05.
ROUND_TOL = 0.05 + 1e-9

PARAMS_PATH = Path(__file__).resolve().parents[3] / "contracts" / "exposure_params.yaml"


@pytest.fixture(scope="module")
def params() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(PARAMS_PATH.read_text(encoding="utf-8"))
    return data


def _env(params: dict[str, Any], leg: dict[str, Any]) -> dict[str, Any]:
    key = leg["mode"] if leg["mode"] != "WAIT" else f"WAIT_{leg['wait_place']}"
    env: dict[str, Any] = params["micro_environment"][params["mode_mapping"][key]]
    return env


def _f_vr(params: dict[str, Any], leg: dict[str, Any]) -> tuple[float, float]:
    env = _env(params, leg)
    return float(env["f"]["value"]), float(env["vr_m3_h"]["value"])


@pytest.mark.parametrize(
    ("model", "example"),
    [
        (PlanRequest, ex.PLAN_REQUEST),
        (PlanResponse, ex.PLAN_RESPONSE),
        (DepartureAdviceResponse, ex.DEPARTURE_ADVICE),
        (AqPointResponse, ex.AQ_POINT),
        (AqForecastResponse, ex.AQ_FORECAST),
        (DailySummaryResponse, ex.DAILY_SUMMARY),
        (GreenSpacesResponse, ex.GREENSPACES),
        (KelurahanInsightsResponse, ex.KELURAHAN_INSIGHTS),
        (HealthResponse, ex.HEALTH),
        *[(Problem, p) for p in ex.PROBLEMS.values()],
    ],
)
def test_example_validates(model: type[BaseModel], example: dict[str, Any]) -> None:
    model.model_validate(example)


def _all_scored(response: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(o["option_id"], o) for o in response["options"]]


def test_leg_dose_follows_formula(params: dict[str, Any]) -> None:
    for option_id, option in _all_scored(ex.PLAN_RESPONSE):
        for leg in option["legs"]:
            f, vr = _f_vr(params, leg)
            h = leg["duration_s"] / 3600
            for suffix, c in (
                ("", "mean_pm25"),
                ("_p10", "mean_pm25_p10"),
                ("_p90", "mean_pm25_p90"),
            ):
                expected = leg[c] * f * vr * h
                assert leg[f"dose_ug{suffix}"] == pytest.approx(expected, abs=ROUND_TOL), (
                    f"{option_id} {leg['mode']} dose{suffix}"
                )
            assert leg["ct_ugh_m3"] == pytest.approx(leg["mean_pm25"] * f * h, abs=ROUND_TOL)


def test_wait_leg_is_half_headway() -> None:
    for _, option in _all_scored(ex.PLAN_RESPONSE):
        for leg in option["legs"]:
            if leg["mode"] == "WAIT":
                assert leg["duration_s"] * 2 == leg["headway_s"]


def test_option_totals_are_sums_of_legs(params: dict[str, Any]) -> None:
    per_cig = params["cigarette"]["ugh_m3_per_cigarette"]["value"]
    for option_id, option in _all_scored(ex.PLAN_RESPONSE):
        legs = option["legs"]
        assert option["duration_s"] == sum(leg["duration_s"] for leg in legs), option_id
        for key in ("dose_ug", "dose_ug_p10", "dose_ug_p90", "ct_ugh_m3"):
            total = sum(leg[key] for leg in legs)
            assert option[key] == pytest.approx(total, rel=0.01), f"{option_id} {key}"  # FR-03
        exact_ct = sum(
            leg["mean_pm25"] * _f_vr(params, leg)[0] * leg["duration_s"] / 3600 for leg in legs
        )
        assert option["cig_eq"] == pytest.approx(exact_ct / per_cig, abs=0.005), option_id
        transit_legs = [leg for leg in legs if leg["mode"] in {"BUS", "SUBWAY", "RAIL"}]
        assert option["transfers"] == max(len(transit_legs) - 1, 0), option_id


def test_spec_13_2_numbers_are_kept() -> None:
    fastest = ex.PLAN_RESPONSE["options"][0]

    assert fastest["labels"] == ["fastest"]
    assert (fastest["dose_ug"], fastest["ct_ugh_m3"], fastest["cig_eq"]) == (21.8, 25.6, 0.05)
    assert [leg["dose_ug"] for leg in fastest["legs"]] == [9.8, 0.9, 5.7, 5.3]
    moto = ex.PLAN_RESPONSE["comparison"]["motorcycle"]
    car = ex.PLAN_RESPONSE["comparison"]["car"]
    assert (moto["dose_ug"], moto["cig_eq"]) == (39.0, 0.12)
    assert (car["dose_ug"], car["cig_eq"]) == (12.4, 0.05)


@pytest.mark.parametrize(("name", "mode"), [("motorcycle", "MOTORCYCLE"), ("car", "CAR")])
def test_comparison_follows_formula(params: dict[str, Any], name: str, mode: str) -> None:
    comp = ex.PLAN_RESPONSE["comparison"][name]
    f, vr = _f_vr(params, {"mode": mode})
    h = comp["duration_s"] / 3600
    per_cig = params["cigarette"]["ugh_m3_per_cigarette"]["value"]

    assert comp["dose_ug"] == pytest.approx(comp["mean_pm25"] * f * vr * h, abs=ROUND_TOL)
    assert comp["ct_ugh_m3"] == pytest.approx(comp["mean_pm25"] * f * h, abs=ROUND_TOL)
    assert comp["cig_eq"] == pytest.approx(comp["mean_pm25"] * f * h / per_cig, abs=0.005)


def test_labels_follow_ranking_rules(params: dict[str, Any]) -> None:
    profile = params["ranking"]["profiles"][ex.PLAN_RESPONSE["sensitivity"]]
    alpha = profile["alpha"]["value"]
    options = ex.PLAN_RESPONSE["options"]
    t_min = min(o["duration_s"] for o in options)
    d_min = min(o["dose_ug"] for o in options)
    tolerance = max(
        profile["cleanest_tolerance_min_s"]["value"],
        profile["cleanest_tolerance_frac"]["value"] * t_min,
    )
    eligible = [o for o in options if o["duration_s"] <= t_min + tolerance]

    def owner(pick: dict[str, Any]) -> str:
        return str(pick["option_id"])

    expected = {
        "fastest": owner(min(options, key=lambda o: o["duration_s"])),
        "cleanest": owner(min(eligible, key=lambda o: o["dose_ug"])),
        "balanced": owner(
            min(
                options,
                key=lambda o: alpha * o["duration_s"] / t_min + (1 - alpha) * o["dose_ug"] / d_min,
            )
        ),
    }
    actual = {label: o["option_id"] for o in options for label in o["labels"]}
    assert actual == expected


def test_deltas_vs_fastest() -> None:
    options = ex.PLAN_RESPONSE["options"]
    fastest = next(o for o in options if "fastest" in o["labels"])
    for o in options:
        pct = (o["dose_ug"] - fastest["dose_ug"]) / fastest["dose_ug"] * 100
        assert o["delta_vs_fastest_pct"] == pytest.approx(pct, abs=0.5)
        assert o["delta_duration_vs_fastest_s"] == o["duration_s"] - fastest["duration_s"]


def test_daily_summary_cigarettes(params: dict[str, Any]) -> None:
    per_cig = params["cigarette"]["ugh_m3_per_cigarette"]["value"]
    s = ex.DAILY_SUMMARY

    assert s["cig_eq_day"] == pytest.approx(s["mean_pm25"] * 24 / per_cig, abs=0.005)


def test_examples_are_labelled_synthetic() -> None:
    for example in (ex.PLAN_RESPONSE, ex.DEPARTURE_ADVICE, ex.AQ_POINT, ex.AQ_FORECAST):
        assert example["data_quality"] == "synthetic"
    for option in ex.PLAN_RESPONSE["options"]:
        assert option["data_quality"] == "synthetic"
