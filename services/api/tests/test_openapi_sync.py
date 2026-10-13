import yaml

from services.api.export_openapi import OPENAPI_PATH, build_spec, render


def test_openapi_yaml_matches_models() -> None:
    assert OPENAPI_PATH.exists(), "contracts/openapi.yaml missing; run `make contract`"
    committed = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))

    assert committed == build_spec(), "contracts/openapi.yaml is stale; run `make contract`"


def test_openapi_yaml_is_byte_identical_to_export() -> None:
    text = OPENAPI_PATH.read_text(encoding="utf-8")

    assert text == render(build_spec()), "formatting drift; run `make contract`"


def test_every_operation_has_priority_and_problem_errors() -> None:
    spec = build_spec()
    for path, item in spec["paths"].items():
        for method, op in item.items():
            assert op.get("x-priority") in {"M", "S", "C"}, f"{method} {path}"
            assert "422" not in op["responses"], f"{method} {path}"
            for status, resp in op["responses"].items():
                if status.startswith(("4", "5")):
                    assert "application/problem+json" in resp["content"], f"{method} {path}"


def test_every_json_response_schema_has_data_quality() -> None:
    spec = build_spec()
    schemas = spec["components"]["schemas"]
    for path, item in spec["paths"].items():
        for op in item.values():
            content = op["responses"]["200"]["content"]
            if "application/json" not in content:
                continue
            ref = content["application/json"]["schema"]["$ref"]
            name = ref.rsplit("/", 1)[-1]
            assert "data_quality" in schemas[name]["required"], f"{path} -> {name}"
