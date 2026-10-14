import asyncio
import json
import subprocess
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
import yaml

from services.api.schemas.examples import AQ_POINT, HEALTH, PROBLEMS
from tests.contract import runner
from tests.contract.demo_backend import synthetic_cog
from tests.contract.runner import (
    CONTRACT,
    contract_schema,
    guided_case,
    local_url,
    operations,
    save_report,
    validate_case,
)


@pytest.fixture(scope="module")
def schema():
    return contract_schema(yaml.safe_load(CONTRACT.read_text()))


def response(code, body, headers=None, path="/v1/health"):
    reply = httpx.Response(
        code,
        json=body,
        headers=headers,
        request=httpx.Request("GET", f"http://127.0.0.1:8002{path}"),
    )
    reply.elapsed = timedelta(milliseconds=1)
    return reply


def test_valid_health_response_has_no_contract_violation(schema) -> None:
    assert validate_case(schema["/v1/health"]["GET"].Case(), response(200, HEALTH)) == ()


@pytest.mark.parametrize(
    "case",
    ["missing-field", "wrong-type", "unknown-quality", "bad-media", "500", "undeclared-status"],
)
def test_real_schemathesis_checks_detect_corrupted_responses(schema, case) -> None:
    body = deepcopy(HEALTH)
    code, headers = 200, None
    if case == "missing-field":
        del body["status"]
    elif case == "wrong-type":
        body["version"] = ["invalid"]
    elif case == "unknown-quality":
        body["data_quality"] = "dummy"
    elif case == "bad-media":
        headers = {"content-type": "text/plain"}
    elif case == "500":
        code = 500
    else:
        code = 201
    failures = validate_case(schema["/v1/health"]["GET"].Case(), response(code, body, headers))
    assert failures
    assert all(not failure.startswith("validator_error:") for failure in failures)


@pytest.mark.parametrize("header", ["bad", "-1"])
def test_invalid_age_header_is_a_contract_violation(schema, header) -> None:
    case = schema["/v1/aq/point"]["GET"].Case(query={"lat": -6.2088, "lon": 106.8227})
    reply = response(200, AQ_POINT, {"X-Data-Age-Seconds": header}, "/v1/aq/point")
    assert validate_case(case, reply)


def test_declared_503_must_still_have_valid_problem_content_and_schema(schema) -> None:
    case = schema["/v1/aq/forecast"]["GET"].Case(query={"lat": -6.2088, "lon": 106.8227})
    body = deepcopy(PROBLEMS[503])
    headers = {"content-type": "application/problem+json"}
    assert validate_case(case, response(503, body, headers, "/v1/aq/forecast")) == ()
    assert validate_case(case, response(503, body, path="/v1/aq/forecast"))
    assert validate_case(case, response(503, {}, headers, "/v1/aq/forecast"))


def test_failure_report_never_includes_values_from_request_or_response(
    schema, tmp_path: Path
) -> None:
    case = schema["/v1/aq/point"]["GET"].Case(query={"lat": -6.208812345, "lon": 106.822712345})
    private_marker = "private-detail-marker"
    reply = response(500, {"detail": private_marker}, path="/v1/aq/point")
    failures = validate_case(case, reply)
    report = {"operation": "GET /v1/aq/point", "violations": list(failures)}
    path = tmp_path / "report.json"
    save_report(path, report)
    text = path.read_text()
    assert failures
    for forbidden in (private_marker, "-6.208812345", "106.822712345", "curl", "request_body"):
        assert forbidden not in text
    assert json.loads(text) == report
    assert not path.with_suffix(".pending").exists()


def test_exact_scope_contains_all_must_and_only_implemented_should() -> None:
    document = yaml.safe_load(CONTRACT.read_text())
    selected, excluded = operations(document)
    assert len(selected) == 7
    assert set(selected) == {
        "POST /v1/routes/plan",
        "GET /v1/aq/point",
        "GET /v1/aq/tiles/{z}/{x}/{y}.png",
        "GET /v1/health",
        "GET /v1/routes/departure-advice",
        "GET /v1/aq/forecast",
        "GET /v1/aq/daily-summary",
    }
    assert {item["operation"] for item in excluded} == {
        "GET /v1/insights/kelurahan",
        "GET /v1/greenspaces/nearby",
    }
    # A future Must operation cannot silently disappear from the selected scope.
    document["paths"]["/future"] = {"get": {"x-priority": "M"}}
    assert "GET /future" in operations(document)[0]


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8002", "http://localhost:8002/", "http://[::1]:8002"]
)
def test_local_base_urls_are_accepted(url) -> None:
    assert local_url(url) == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com",
        "http://127.0.0.1:8002/v1",
        "http://user:secret@localhost:8002",
        "http://localhost:8002?x=1",
        "http://localhost:8002#fragment",
        "http://localhost:0",
        "http://localhost:99999",
    ],
)
def test_runner_cannot_target_external_servers_or_credential_urls(url) -> None:
    with pytest.raises(ValueError, match=r"localhost|port|Port"):
        local_url(url)


def test_503_is_not_accepted_on_an_operation_without_it_in_the_contract(schema) -> None:
    failures = validate_case(
        schema["/v1/health"]["GET"].Case(),
        response(503, PROBLEMS[503], {"content-type": "application/problem+json"}),
    )
    assert "UndefinedStatusCode" in failures


def test_schema_mismatch_never_passes_without_exercising_http_cases(
    tmp_path: Path, monkeypatch
) -> None:
    class DifferentSchema:
        status_code = 200

        def json(self):
            return {"unexpected": "private-schema-marker"}

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            return DifferentSchema()

    monkeypatch.setattr(runner.requests, "Session", Session)
    path = tmp_path / "report.json"
    report = runner.run_live(
        "http://127.0.0.1:8002",
        max_examples=1,
        random_seed=20261014,
        budget_s=10,
        request_timeout_s=1,
        output=path,
        day=date(2026, 10, 14),
    )
    assert report["success"] is False
    assert report["completed"] is False
    assert report["operations"] == []
    assert report["preflight_error"] == "live_schema_differs_from_frozen_contract"
    assert "private-schema-marker" not in path.read_text()


def test_wall_clock_timeout_fails_and_does_not_emit_worker_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    path = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--base-url",
            "http://127.0.0.1:8002",
            "--output",
            str(path),
            "--budget-s",
            "1",
            "--request-timeout-s",
            "1",
            "--date",
            "2026-10-14",
        ],
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            "worker", 1, output=b"private-request-marker", stderr=b"private-response-marker"
        )

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 1
    report = json.loads(path.read_text())
    assert report["success"] is False
    assert report["runner_error"] == "wall_clock_budget_exhausted"
    output = capsys.readouterr()
    assert "private" not in output.out
    assert "private" not in output.err


def test_guided_cases_cover_all_selected_operations_with_explicit_dates(schema) -> None:
    selected, _ = operations(yaml.safe_load(CONTRACT.read_text()))
    day = date(2026, 10, 14)
    cases = {label: guided_case(schema, label, day) for label in selected}
    assert set(cases) == set(selected)
    plan = cases["POST /v1/routes/plan"]
    assert plan.body["depart_at"] == "2026-10-14T07:30:00+07:00"
    assert plan.body["include_comparison"] is False
    assert cases["GET /v1/aq/forecast"].query["hours"] == 1
    assert cases["GET /v1/aq/daily-summary"].query["date"] == "2026-10-14"
    assert cases["GET /v1/routes/departure-advice"].query["mode"] == "walk"


async def test_fixture_reads_off_thread_and_closes_its_gdal_environment(tmp_path: Path) -> None:
    from tests.test_forecast import POINT, TS

    async with synthetic_cog(tmp_path) as cog:
        samples = await asyncio.to_thread(cog.sample, (POINT,), TS)
        assert samples.data_quality == "synthetic"
        assert samples.p50[0] == 9

    # Closed files are removable on Windows; context shutdown must not raise a GDAL EnvError.
    def remove_first_raster():
        first = next(tmp_path.rglob("*.tif"))
        first.unlink()
        return first.exists()

    assert await asyncio.to_thread(remove_first_raster) is False
