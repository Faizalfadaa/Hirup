"""Bounded live HTTP conformance against the frozen contract, with redacted reports."""

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

import requests
import schemathesis
import yaml
from hypothesis import HealthCheck, Phase, given, seed, settings
from schemathesis import Case, GenerationMode, checks
from schemathesis.core.failures import FailureGroup

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/openapi.yaml"
SHOULD = {
    "GET /v1/routes/departure-advice",
    "GET /v1/aq/forecast",
    "GET /v1/aq/daily-summary",
    "GET /v1/insights/kelurahan",
}
CHECKS = [
    checks.not_a_server_error,
    checks.status_code_conformance,
    checks.content_type_conformance,
    checks.response_headers_conformance,
    checks.response_schema_conformance,
    checks.negative_data_rejection,
]


def guided_case(schema: Any, label: str, day: date) -> Case:
    """Public golden OD and explicit synthetic grid point, never user coordinates."""
    from tests.test_forecast import POINT

    method, path = label.split(" ", 1)
    operation = schema[path][method]
    golden = json.loads((ROOT / "contracts/golden_od.json").read_text())
    pair = golden["pairs"][0]
    origin, destination = (
        {key: golden["places"][pair[name]][key] for key in ("lat", "lon")}
        for name in ("origin", "destination")
    )
    around = f"{day.isoformat()}T07:30:00+07:00"
    if path == "/v1/routes/plan":
        return operation.Case(
            body={
                "origin": origin,
                "destination": destination,
                "depart_at": around,
                "include_comparison": False,
            },
            media_type="application/json",
        )
    if path == "/v1/routes/departure-advice":
        return operation.Case(
            query={
                "origin_lat": origin["lat"],
                "origin_lon": origin["lon"],
                "destination_lat": destination["lat"],
                "destination_lon": destination["lon"],
                "around": around,
                "mode": "walk",
                "sensitivity": "umum",
            }
        )
    if path == "/v1/health":
        return operation.Case()
    if path == "/v1/insights/kelurahan":
        from datetime import timedelta

        return operation.Case(
            query={
                "from": (day - timedelta(days=2)).isoformat(),
                "to": (day - timedelta(days=1)).isoformat(),
            }
        )
    if "tiles" in path:
        return operation.Case(path_parameters={"z": 0, "x": 0, "y": 0}, query={"ts": around})
    query: dict[str, Any] = {"lat": POINT.lat, "lon": POINT.lon}
    if path == "/v1/aq/forecast":
        query["hours"] = 1
    elif path == "/v1/aq/daily-summary":
        query["date"] = day.isoformat()
    elif path == "/v1/aq/point":
        query["ts"] = around
    return operation.Case(query=query)


def contract_schema(document: dict[str, Any]) -> Any:
    config = schemathesis.Config.from_dict(
        {"checks": {"not_a_server_error": {"expected-statuses": ["2XX", "3XX", "4XX", "503"]}}}
    )
    # 503 is still checked by status, media, header and body checks against each operation.
    # Every other 5xx remains a server failure, even if later added to an operation schema.
    return schemathesis.openapi.from_dict(document, config=config)


def local_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Contract runner requires a plain localhost HTTP base URL")
    # Validate the port now, instead of discovering an invalid value during requests.
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid localhost port")
    return value.rstrip("/")


def validate_case(case: Case, response: Any) -> tuple[str, ...]:
    """Keep only failure class names; never emit bodies, URLs, curl or exception messages."""
    try:
        case.validate_response(response, checks=CHECKS)
    except FailureGroup as exc:
        return tuple(sorted({type(failure).__name__ for failure in exc.exceptions}))
    except Exception as exc:
        return (f"validator_error:{type(exc).__name__}",)
    return ()


def operations(document: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    selected, excluded = [], []
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            label = f"{method.upper()} {path}"
            if operation.get("x-priority") == "M" or label in SHOULD:
                selected.append(label)
            else:
                excluded.append(
                    {
                        "operation": label,
                        "reason": "Could scope",
                    }
                )
    return selected, excluded


def save_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2), encoding="utf-8")
    pending.replace(path)


def run_live(
    base_url: str,
    *,
    max_examples: int,
    random_seed: int,
    budget_s: float,
    request_timeout_s: float,
    output: Path,
    day: date,
    fixture_aq: bool = False,
) -> dict[str, Any]:
    base_url = local_url(base_url)
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    selected, excluded = operations(document)
    report: dict[str, Any] = {
        "purpose": "HTTP contract regression; no model/impact/production availability claim",
        "seed": random_seed,
        "max_examples_per_mode": max_examples,
        "budget_s": budget_s,
        "date": day.isoformat(),
        "fixture_aq": fixture_aq,
        "checks": [check.__name__ for check in CHECKS],
        "selected_operations": selected,
        "excluded_operations": excluded,
        "operations": [],
        "success": False,
        "completed": False,
    }
    save_report(output, report)
    deadline = monotonic() + budget_s
    schema = contract_schema(document)
    schema.validate()
    with requests.Session() as session:
        session.trust_env = False
        preflight = session.get(
            f"{base_url}/openapi.json", timeout=request_timeout_s, allow_redirects=False
        )
        if preflight.status_code != 200 or preflight.json() != document:
            report["preflight_error"] = "live_schema_differs_from_frozen_contract"
            save_report(output, report)
            return report
        for index, label in enumerate(selected):
            method, path = label.split(" ", 1)
            operation = schema[path][method]
            record: dict[str, Any] = {
                "operation": label,
                "requests": 0,
                "statuses": {},
                "violations": {},
                "phases": [],
            }
            report["operations"].append(record)
            statuses: Counter[str] = Counter()
            violations: Counter[str] = Counter()

            def execute(
                case: Case,
                record: dict[str, Any] = record,
                statuses: Counter[str] = statuses,
                violations: Counter[str] = violations,
                expected_status: int | None = None,
            ) -> None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("Contract run budget exhausted")
                record["requests"] += 1
                try:
                    response = case.call(
                        base_url=base_url,
                        session=session,
                        timeout=min(request_timeout_s, remaining),
                        allow_redirects=False,
                    )
                except Exception as exc:
                    violations[f"transport_error:{type(exc).__name__}"] += 1
                else:
                    statuses[str(response.status_code)] += 1
                    violations.update(validate_case(case, response))
                    if expected_status is not None and response.status_code != expected_status:
                        violations["guided_availability_failure"] += 1
                    if (
                        fixture_aq
                        and response.status_code == 200
                        and case.path in {"/v1/aq/forecast", "/v1/aq/daily-summary"}
                    ):
                        body = response.json()
                        if not isinstance(body, dict) or body.get("data_quality") != "synthetic":
                            violations["fixture_response_not_synthetic"] += 1
                record["statuses"] = dict(statuses)
                record["violations"] = dict(violations)

            def exercise(
                strategy: Any,
                phase_name: str,
                count: int,
                phase_seed: int,
                record: dict[str, Any] = record,
                execute: Callable[[Case], None] = execute,
            ) -> bool:
                before = record["requests"]
                phase: dict[str, Any] = {"name": phase_name, "completed": False}
                record["phases"].append(phase)

                @seed(phase_seed)
                @settings(
                    max_examples=count,
                    deadline=None,
                    database=None,
                    phases=(Phase.generate,),
                    suppress_health_check=(HealthCheck.too_slow,),
                )
                @given(strategy)
                def generated(case: Case) -> None:
                    execute(case)

                try:
                    generated()
                except Exception as exc:
                    phase["error"] = type(exc).__name__
                else:
                    phase["completed"] = record["requests"] > before
                phase["requests"] = record["requests"] - before
                save_report(output, report)
                return bool(phase["completed"])

            guided = {"name": "guided", "completed": False, "requests": 0}
            record["phases"].append(guided)
            execute(guided_case(schema, label, day), expected_status=200 if fixture_aq else None)
            guided.update(completed=True, requests=1)
            save_report(output, report)
            # Schema examples remain unchanged; fuzzing is seeded and has no persistent database.
            for number, strategy in enumerate(operation.get_strategies_from_examples()):
                if not exercise(strategy, f"example-{number}", 1, random_seed + index * 10):
                    return report
            if not exercise(
                operation.as_strategy(generation_mode=GenerationMode.POSITIVE),
                "positive",
                max_examples,
                random_seed + index * 10 + 1,
            ):
                return report
            raw = document["paths"][path][method.lower()]
            if raw.get("parameters") or raw.get("requestBody"):
                if not exercise(
                    operation.as_strategy(generation_mode=GenerationMode.NEGATIVE),
                    "negative",
                    max_examples,
                    random_seed + index * 10 + 2,
                ):
                    return report
            else:
                record["negative_not_applicable"] = "operation has no request inputs"
            save_report(output, report)
    report["completed"] = True
    report["success"] = all(
        item["requests"] > 0 and not item["violations"] for item in report["operations"]
    ) and len(report["operations"]) == len(selected)
    save_report(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=local_url, required=True)
    parser.add_argument("--max-examples", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261014)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--fixture-aq", action="store_true")
    parser.add_argument("--budget-s", type=float, default=300)
    parser.add_argument("--request-timeout-s", type=float, default=30)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/contracts/http-conformance.json"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.max_examples <= 100 or not 0 < args.request_timeout_s <= args.budget_s <= 900:
        parser.error("Use 1-100 examples and 0 < request timeout <= budget <= 900 seconds")
    if args.worker:
        try:
            run_live(
                args.base_url,
                max_examples=args.max_examples,
                random_seed=args.seed,
                budget_s=args.budget_s,
                request_timeout_s=args.request_timeout_s,
                output=args.output,
                day=args.date,
                fixture_aq=args.fixture_aq,
            )
        except Exception as exc:
            # The parent discards stderr too; never serialize a requests/Hypothesis exception.
            print(json.dumps({"worker_error": type(exc).__name__}))
            raise SystemExit(2) from None
        return
    with TemporaryDirectory(prefix="hirup-contract-") as folder:
        snapshot = Path(folder) / "summary.json"
        command = [
            sys.executable,
            "-m",
            "tests.contract.runner",
            "--worker",
            "--base-url",
            args.base_url,
            "--max-examples",
            str(args.max_examples),
            "--seed",
            str(args.seed),
            "--date",
            args.date.isoformat(),
            "--budget-s",
            str(args.budget_s),
            "--request-timeout-s",
            str(args.request_timeout_s),
            "--output",
            str(snapshot),
        ]
        if args.fixture_aq:
            command.append("--fixture-aq")
        error = None
        try:
            worker = subprocess.run(
                command, cwd=ROOT, capture_output=True, timeout=args.budget_s, check=False
            )
            if worker.returncode:
                error = "worker_failed"
        except subprocess.TimeoutExpired:
            error = "wall_clock_budget_exhausted"
        report = json.loads(snapshot.read_text()) if snapshot.is_file() else {"success": False}
        if error is not None:
            report.update(success=False, completed=False, runner_error=error)
        save_report(args.output, report)
        print(json.dumps(report, indent=2))
        if not report["success"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
