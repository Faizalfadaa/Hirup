"""Static checks on the frozen files in contracts/ (no running services needed)."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

from services.api.schemas.examples import PLAN_REQUEST, PLAN_RESPONSE
from services.api.schemas.routes import LegMode

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
ENTRY_KEYS = {"value", "range", "unit", "source", "verified_by", "note"}


def _load_yaml(name: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((CONTRACTS / name).read_text(encoding="utf-8"))
    return data


def _load_json(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CONTRACTS / name).read_text(encoding="utf-8"))
    return data


def _entries(node: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    """Leaf parameter entries, recognised by having a `value` key."""
    if isinstance(node, dict):
        if "value" in node:
            return [(path, node)]
        return [e for k, v in node.items() for e in _entries(v, f"{path}.{k}".lstrip("."))]
    return []


# --- exposure_params.yaml ------------------------------------------------------------


@pytest.fixture(scope="module")
def params() -> dict[str, Any]:
    return _load_yaml("exposure_params.yaml")


def test_every_param_has_full_provenance(params: dict[str, Any]) -> None:
    entries = _entries({k: v for k, v in params.items() if k != "mode_mapping"})

    assert len(entries) > 20
    for path, entry in entries:
        assert set(entry) == ENTRY_KEYS, path
        assert entry["source"], path
        assert entry["verified_by"] is None, f"{path}: only humans set verified_by"
        if entry["value"] is None:
            assert "TODO(verify)" in entry["note"], path


def test_micro_environment_f_is_midpoint_of_spec_range(params: dict[str, Any]) -> None:
    for name, env in params["micro_environment"].items():
        lo, hi = env["f"]["range"]
        assert env["f"]["value"] == pytest.approx((lo + hi) / 2), name
        assert env["vr_m3_h"]["value"] > 0, name


def test_mode_mapping_covers_every_leg_mode(params: dict[str, Any]) -> None:
    mapping = params["mode_mapping"]
    expected = {m.value for m in LegMode if m is not LegMode.WAIT} | {"WAIT_stop", "WAIT_station"}

    assert set(mapping) == expected
    assert set(mapping.values()) <= set(params["micro_environment"])


def test_spec_constants(params: dict[str, Any]) -> None:
    assert params["cigarette"]["ugh_m3_per_cigarette"]["value"] == 528
    assert params["daily"]["vr_m3_day"]["value"] == 16
    assert params["daily"]["f_indoor"]["value"] is None


def test_spec_12_5_motorcycle_example(params: dict[str, Any]) -> None:
    f = params["micro_environment"]["motorcycle"]["f"]["value"]
    per_cig = params["cigarette"]["ugh_m3_per_cigarette"]["value"]

    assert 60 * f * (50 / 60) / per_cig == pytest.approx(0.12, abs=0.005)


# --- golden_od.json ------------------------------------------------------------------


def test_golden_od_shape_and_bbox() -> None:
    golden = _load_json("golden_od.json")
    bbox = golden["bbox"]
    places = golden["places"]

    assert golden["validated_by"] is None
    assert golden["time_slots"] == ["06:30", "07:30", "17:30"]
    assert len(golden["pairs"]) == 10
    assert len({p["id"] for p in golden["pairs"]}) == 10
    for key, place in places.items():
        assert bbox["min_lat"] <= place["lat"] <= bbox["max_lat"], key
        assert bbox["min_lon"] <= place["lon"] <= bbox["max_lon"], key
    used = {p[end] for p in golden["pairs"] for end in ("origin", "destination")}
    assert used <= set(places)
    required = {"lebak_bulus", "blok_m", "dukuh_atas", "sudirman", "bundaran_hi", "kota"}
    assert required <= used
    assert all(p["origin"] != p["destination"] for p in golden["pairs"])


# --- schemas/*.json ------------------------------------------------------------------


@pytest.mark.parametrize("name", ["raster_manifest.schema.json", "demo_scenario.schema.json"])
def test_json_schemas_are_valid(name: str) -> None:
    schema = _load_json(f"schemas/{name}")

    jsonschema.Draft202012Validator.check_schema(schema)


def test_raster_manifest_examples_validate() -> None:
    schema = _load_json("schemas/raster_manifest.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    for example in schema["examples"]:
        validator.validate(example)
    bad = {**schema["examples"][0], "crs": "EPSG:4326"}
    assert not validator.is_valid(bad)


def test_demo_scenario_requires_synthetic() -> None:
    validator = jsonschema.Draft202012Validator(_load_json("schemas/demo_scenario.schema.json"))
    scenario = {
        "scenario_version": "1.0",
        "scenario_id": "lebak_bulus_sudirman_0700",
        "title": "Lebak Bulus ke Sudirman, 07.00",
        "description": "Komuter pagi, profil rentan",
        "data_quality": "synthetic",
        "seed": 42,
        "generator": "fixtures/generate.py",
        "request": PLAN_REQUEST,
        "response": PLAN_RESPONSE,
    }

    validator.validate(scenario)
    assert not validator.is_valid({**scenario, "data_quality": "real"})
    assert not validator.is_valid(
        {**scenario, "response": {**PLAN_RESPONSE, "data_quality": "real"}}
    )
