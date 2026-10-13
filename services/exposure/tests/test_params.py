from pathlib import Path
from typing import Any

import pytest
import yaml

from services.exposure.params import (
    ExposureParams,
    ParamsError,
    UnverifiedParamsWarning,
    load_params,
    parse_params,
)


def test_contract_file_loads(params: ExposureParams) -> None:
    assert params.micro_environment["walk"].f == 1.15
    assert params.micro_environment["walk"].f_range == (1.0, 1.3)
    assert params.micro_environment["motorcycle"].vr_m3_h == 0.6
    assert params.mode_mapping["SUBWAY"] == "rail"
    assert params.mode_mapping["WAIT_station"] == "wait_station"
    assert params.ugh_m3_per_cigarette == 528
    assert params.vr_m3_day == 16
    assert params.f_indoor is None
    assert params.emission_factors is None
    assert "micro_environment.walk.f" in params.unverified
    assert params.sources["cigarette.ugh_m3_per_cigarette"].startswith("Berkeley Earth")


def test_unverified_values_warn(tmp_path: Path, raw_params: dict[str, Any]) -> None:
    path = tmp_path / "params.yaml"
    path.write_text(yaml.safe_dump(raw_params), encoding="utf-8")

    with pytest.warns(UnverifiedParamsWarning, match="verified_by: null"):
        load_params(path)


def test_fully_verified_file_does_not_warn(
    tmp_path: Path, raw_params: dict[str, Any], recwarn: pytest.WarningsRecorder
) -> None:
    def verify(node: Any) -> None:
        if isinstance(node, dict):
            if "verified_by" in node:
                node["verified_by"] = "reviewer"
            for child in node.values():
                verify(child)

    verify(raw_params)
    path = tmp_path / "params.yaml"
    path.write_text(yaml.safe_dump(raw_params), encoding="utf-8")

    params = load_params(path)

    assert params.unverified == ()
    assert not [w for w in recwarn if issubclass(w.category, UnverifiedParamsWarning)]


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ParamsError, match="not found"):
        load_params(tmp_path / "nope.yaml")


def test_non_mapping_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "params.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")

    with pytest.raises(ParamsError, match="top level"):
        load_params(path)


def test_missing_provenance_field_fails(raw_params: dict[str, Any]) -> None:
    del raw_params["micro_environment"]["walk"]["f"]["source"]

    with pytest.raises(ParamsError, match=r"micro_environment\.walk\.f: missing source"):
        parse_params(raw_params)


def test_empty_source_fails(raw_params: dict[str, Any]) -> None:
    raw_params["daily"]["vr_m3_day"]["source"] = ""

    with pytest.raises(ParamsError, match="empty source"):
        parse_params(raw_params)


def test_missing_vr_fails(raw_params: dict[str, Any]) -> None:
    del raw_params["micro_environment"]["bus"]["vr_m3_h"]

    with pytest.raises(ParamsError, match=r"micro_environment\.bus\.vr_m3_h: missing"):
        parse_params(raw_params)


def test_f_outside_range_fails(raw_params: dict[str, Any]) -> None:
    raw_params["micro_environment"]["car"]["f"]["value"] = 0.9

    with pytest.raises(ParamsError, match="outside range"):
        parse_params(raw_params)


def test_bad_range_shape_fails(raw_params: dict[str, Any]) -> None:
    raw_params["micro_environment"]["car"]["f"]["range"] = None

    with pytest.raises(ParamsError, match="expected \\[low, high\\]"):
        parse_params(raw_params)


@pytest.mark.parametrize("bad", [0, -1, "1.2", True, float("nan")])
def test_non_positive_factor_fails(raw_params: dict[str, Any], bad: Any) -> None:
    raw_params["micro_environment"]["walk"]["vr_m3_h"]["value"] = bad

    with pytest.raises(ParamsError, match=r"micro_environment\.walk\.vr_m3_h"):
        parse_params(raw_params)


def test_cigarette_constant_is_required(raw_params: dict[str, Any]) -> None:
    raw_params["cigarette"]["ugh_m3_per_cigarette"]["value"] = None

    with pytest.raises(ParamsError, match="value is required"):
        parse_params(raw_params)


def test_missing_constant_entry_fails(raw_params: dict[str, Any]) -> None:
    del raw_params["daily"]["vr_m3_day"]

    with pytest.raises(ParamsError, match=r"daily\.vr_m3_day: missing"):
        parse_params(raw_params)


def test_unmapped_leg_mode_fails(raw_params: dict[str, Any]) -> None:
    del raw_params["mode_mapping"]["BICYCLE"]

    with pytest.raises(ParamsError, match=r"mode_mapping\.BICYCLE: missing"):
        parse_params(raw_params)


def test_mapping_to_unknown_environment_fails(raw_params: dict[str, Any]) -> None:
    raw_params["mode_mapping"]["BUS"] = "tram"

    with pytest.raises(ParamsError, match="unknown micro_environment 'tram'"):
        parse_params(raw_params)


def test_empty_section_fails(raw_params: dict[str, Any]) -> None:
    raw_params["micro_environment"] = {}

    with pytest.raises(ParamsError, match="micro_environment: missing or empty"):
        parse_params(raw_params)


def test_optional_values_parse_when_filled(raw_params: dict[str, Any]) -> None:
    # Arbitrary test numbers, not real factors.
    raw_params["daily"]["f_indoor"]["value"] = 0.5
    raw_params["emission_factors"]["value"] = {"motorcycle": 0.1, "car": 0.2}

    params = parse_params(raw_params)

    assert params.f_indoor == 0.5
    assert params.emission_factors == {"motorcycle": 0.1, "car": 0.2}


def test_optional_table_must_be_mapping(raw_params: dict[str, Any]) -> None:
    raw_params["fuel_cost"]["value"] = 1500

    with pytest.raises(ParamsError, match="expected a mapping"):
        parse_params(raw_params)
