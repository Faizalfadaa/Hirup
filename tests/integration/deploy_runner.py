"""Local-only TLS/proxy/container regression using explicitly synthetic AQ."""

import json
import os
import re
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from infra.ci.check import warm_transit
from services.api.schemas.problem import Problem

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "infra/deploy"
CANARY = "HIRUP_PRIVATE_OD_CANARY"


def main() -> None:
    project = os.environ.get("HIRUP_CI_PROJECT", "")
    if re.fullmatch(r"hirup-ci-[a-z0-9-]+", project) is None:
        raise SystemExit("Set a unique isolated HIRUP_CI_PROJECT")
    edge = project + "-edge"
    env = {**os.environ, "HIRUP_LOCAL_DATA": str(ROOT / "data"), "MSYS_NO_PATHCONV": "1"}
    command = [
        "docker",
        "compose",
        "--project-name",
        edge,
        "--project-directory",
        str(DEPLOY),
        "--env-file",
        str(ROOT / "infra/images.env"),
        "--env-file",
        str(DEPLOY / "images.env"),
        "-f",
        str(DEPLOY / "local.compose.yml"),
    ]
    output = ROOT / "data/deploy-validation"
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "purpose": "container/TLS regression; synthetic AQ, not production or impact evidence"
    }

    def compose(*arguments: str) -> None:
        subprocess.run(command + list(arguments), env=env, check=True, timeout=300)

    try:
        # A real production image with no P2 input must honestly report degraded/503.
        compose("--profile", "preview", "up", "-d", "--wait", "api-preview")
        with httpx.Client(trust_env=False, timeout=30) as client:
            health = client.get("http://127.0.0.1:8004/v1/health").json()
            if health["status"] != "degraded" or health["data_quality"] == "synthetic":
                raise ValueError("Production without P2 must be degraded, never synthetic")
            missing = client.get(
                "http://127.0.0.1:8004/v1/aq/point", params={"lat": -6.2, "lon": 106.8}
            )
            Problem.model_validate(missing.json())
            if missing.status_code != 503:
                raise ValueError("Production without AQ must return 503")
        report["production_missing_aq"] = "degraded/503"
        compose("stop", "api-preview")
        warm_transit()
        compose("up", "-d", "--wait", "api", "gateway", "caddy")
        ca = output / "local-ca.crt"
        for attempt in range(30):
            copied = subprocess.run(
                [
                    "docker",
                    "cp",
                    f"{edge}-caddy-1:/data/caddy/pki/authorities/local/root.crt",
                    str(ca),
                ],
                capture_output=True,
            )
            if copied.returncode == 0:
                break
            if attempt == 29:
                raise ValueError("Local Caddy CA unavailable")
            time.sleep(1)
        context = ssl.create_default_context(cafile=ca)
        with httpx.Client(verify=context, trust_env=False, timeout=30) as client:
            for attempt in range(30):
                try:
                    response = client.get("https://localhost:8443/v1/health")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    if attempt == 29:
                        raise
                time.sleep(1)
            if response.json()["data_quality"] != "synthetic":
                raise ValueError("Fixture must declare synthetic")
            report["tls_verified"] = True
            probe = client.get(
                "https://localhost:8443/v1/aq/point",
                params={"lat": -6.2, "lon": 106.8, "privacy_probe": CANARY},
            )
            probe.raise_for_status()
            statuses = []
            for index in range(12):
                response = client.post(
                    "https://localhost:8443/v1/routes/plan",
                    json={},
                    headers={
                        "X-Hirup-Client-IP": f"192.0.2.{index + 1}",
                        "X-Forwarded-For": f"192.0.2.{index + 1}",
                    },
                )
                statuses.append(response.status_code)
                Problem.model_validate(response.json())
                if response.status_code == 429 and response.headers.get("retry-after") != "60":
                    raise ValueError("Rate rejection needs Retry-After")
            if 429 not in statuses or any(status not in {400, 429} for status in statuses):
                raise ValueError("Spoofed headers bypassed rate limiting or errors broke contract")
            report["route_limit_statuses"] = statuses
            report["ip_spoofing_bypass"] = False
        subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.contract.runner",
                "--base-url",
                "http://127.0.0.1:8003",
                "--date",
                "2026-10-14",
                "--fixture-aq",
                "--seed",
                "20261014",
                "--max-examples",
                "20",
                "--budget-s",
                "300",
                "--output",
                str(output / "contract.json"),
            ],
            cwd=ROOT,
            check=True,
            timeout=330,
        )
        logs = subprocess.check_output([*command, "logs", "--no-color"], env=env, text=True)
        if CANARY in logs:
            raise ValueError("Private query canary appeared in logs")
        report["privacy_canary_absent"] = True
        compose("stop", "api")
        subprocess.run(
            [
                sys.executable,
                "tests/integration/golden_runner.py",
                "--date",
                "2026-10-14",
                "--demo-min-pm25",
                "10",
                "--demo-max-pm25",
                "80",
                "--reference-pm25",
                "40",
                "--trunk-penalty",
                "2",
                "--cold-cache",
                "--profile-stages",
                "--otp-url",
                "http://127.0.0.1:18081/otp/gtfs/v1",
                "--osrm-car-url",
                "http://127.0.0.1:5100",
                "--osrm-moto-url",
                "http://127.0.0.1:5101",
                "--output",
                str(output / "golden.json"),
            ],
            cwd=ROOT,
            check=True,
            timeout=600,
        )
        report["success"] = True
    except Exception as error:
        report.update(success=False, failure_class=type(error).__name__)
        raise SystemExit(1) from None
    finally:
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        compose("--profile", "preview", "down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
