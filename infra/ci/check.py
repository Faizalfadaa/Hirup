"""Run HTTP contract and golden checks with isolated Docker engine URLs."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from infra.scripts.smoke import transit_duration, transit_payload

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://127.0.0.1:8003"
ENGINES = {
    "OTP_URL": "http://127.0.0.1:18081/otp/gtfs/v1",
    "OSRM_CAR_URL": "http://127.0.0.1:5100",
    "OSRM_MOTO_URL": "http://127.0.0.1:5101",
}


def warm_transit() -> None:
    """Initialize OTP transfer/JIT caches with real, sequential transit queries."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for reluctance in (1.5, 3, 6):
        payload = transit_payload(datetime.fromisoformat("2026-10-14T07:30:00+07:00"))
        payload["query"] = str(payload["query"]).replace(
            "numItineraries: 5,", f"numItineraries: 5, walkReluctance: {reluctance},"
        )
        request = urllib.request.Request(
            ENGINES["OTP_URL"],
            json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with opener.open(request, timeout=30) as response:
                transit_duration(json.load(response))
        except (OSError, ValueError, KeyError, TypeError):
            raise RuntimeError(
                "OTP initialization requires a successful transit query"
            ) from None


def wait_ready(process: subprocess.Popen[bytes], timeout: float = 180) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Contract fixture server exited before readiness")
        try:
            with opener.open(f"{BASE_URL}/v1/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise TimeoutError("Contract fixture server readiness timed out")


@contextmanager
def fixture_server() -> Iterator[None]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8003))
    # Only this child is terminated; never discover/kill a process by port or name.
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.contract.demo_backend:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8003",
            "--no-access-log",
        ],
        cwd=ROOT,
        env={**os.environ, **ENGINES},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_ready(process)
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def main() -> None:
    output = ROOT / "data/ci/reports"
    output.mkdir(parents=True, exist_ok=True)
    warm_transit()
    (output / "initialization.json").write_text(
        json.dumps(
            {
                "purpose": "engine initialization; excluded from latency",
                "otp_variants": 3,
                "success": True,
            }
        ),
        encoding="utf-8",
    )
    with fixture_server():
        subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.contract.runner",
                "--base-url",
                BASE_URL,
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
    # Release the fixture's graph before starting the cold benchmark runtime.
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
            ENGINES["OTP_URL"],
            "--osrm-car-url",
            ENGINES["OSRM_CAR_URL"],
            "--osrm-moto-url",
            ENGINES["OSRM_MOTO_URL"],
            "--output",
            str(output / "golden.json"),
        ],
        cwd=ROOT,
        check=True,
        timeout=600,
    )
    golden = json.loads((output / "golden.json").read_text())
    print(
        json.dumps(
            {
                key: golden[key]
                for key in ("golden_success", "plan_p95_ms", "aq_point_p95_ms")
            }
        )
    )


if __name__ == "__main__":
    main()
