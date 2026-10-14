"""Deployment operations with bounded jobs and reports that omit request URLs."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "infra/deploy"


def image_reference(value: str) -> str:
    # Mutable preview/latest tags are never accepted by the release/rollback path.
    if (
        re.fullmatch(r"[a-zA-Z0-9._:/-]+(?:@sha256:[a-f0-9]{64}|:[a-f0-9]{40})", value)
        is None
    ):
        raise ValueError("Release image needs a commit SHA tag or content digest")
    return value


def health_summary(body: Any, max_age: int) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError("Invalid health response")
    age = body.get("data_age_seconds")
    raw_quality = body.get("data_quality")
    quality = raw_quality if isinstance(raw_quality, str) else None
    fresh = type(age) is int and 0 <= age <= max_age
    return {
        "state": "ok"
        if body.get("status") == "ok" and fresh and quality in {"real", "approximated"}
        else "degraded",
        "data_age_seconds": age if type(age) is int and age >= 0 else None,
        "data_quality": quality
        if quality in {"real", "approximated", "synthetic"}
        else None,
    }


def monitor(
    url: str, max_age: int = 5400, *, local_http: bool = False
) -> dict[str, Any]:
    validate_origin(url, local_http=local_http)
    if max_age <= 0:
        raise ValueError("Invalid monitor configuration")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(url.rstrip("/") + "/v1/health", timeout=10) as response:
            return health_summary(json.load(response), max_age)
    except (OSError, ValueError, urllib.error.URLError):
        # Never print exception messages: they may contain URLs or credentials.
        return {"state": "unreachable", "data_age_seconds": None, "data_quality": None}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def validate_origin(url: str, *, local_http: bool = False) -> None:
    parsed = urlsplit(url)
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Health URL must be a bare origin without credentials")
    if parsed.scheme != "https" and not (
        local_http
        and parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        raise ValueError("Production monitoring requires HTTPS")
    if not parsed.hostname:
        raise ValueError("Invalid monitor configuration")


def readiness(url: str, max_wait: float = 60) -> dict[str, Any]:
    """Allow bounded ACME/network startup time, but never accept degraded AQ."""
    deadline = time.monotonic() + max_wait
    status = monitor(url)
    while status["state"] == "unreachable" and time.monotonic() < deadline:
        time.sleep(min(2, max(0, deadline - time.monotonic())))
        status = monitor(url)
    return status


def compose(settings: Path, image: str, *arguments: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            "hirup-prod",
            "--project-directory",
            str(DEPLOY),
            "--env-file",
            str(ROOT / "infra/images.env"),
            "--env-file",
            str(DEPLOY / "images.env"),
            "--env-file",
            str(settings),
            "-f",
            str(DEPLOY / "compose.yml"),
            *arguments,
        ],
        env={**os.environ, "HIRUP_API_IMAGE": image_reference(image)},
        check=True,
        timeout=600,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def record(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Release state must not be symlinked")
    temporary = path.with_suffix(".pending")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(value + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def deploy(settings: Path, state: Path, image: str, url: str) -> dict[str, Any]:
    image = image_reference(image)
    validate_origin(url)
    current = state / "current-image"
    previous = (
        image_reference(current.read_text().strip()) if current.exists() else None
    )
    try:
        compose(settings, image, "up", "-d", "--wait", "--wait-timeout", "300")
        # Re-resolve API DNS after replacement instead of retaining an old container IP.
        compose(
            settings,
            image,
            "up",
            "-d",
            "--force-recreate",
            "--no-deps",
            "--wait",
            "--wait-timeout",
            "120",
            "gateway",
            "caddy",
        )
        status = readiness(url)
        if status["state"] != "ok":
            raise ValueError("Production health is not ready")
    except (ValueError, OSError, subprocess.SubprocessError):
        if previous is None:
            return {"state": "failed", "rollback": "no_previous_release"}
        try:
            compose(settings, previous, "up", "-d", "--wait", "--wait-timeout", "300")
            compose(
                settings,
                previous,
                "up",
                "-d",
                "--force-recreate",
                "--no-deps",
                "--wait",
                "--wait-timeout",
                "120",
                "gateway",
                "caddy",
            )
            restored = readiness(url)["state"] == "ok"
            return {
                "state": "failed",
                "rollback": "restored" if restored else "degraded",
            }
        except (ValueError, OSError, subprocess.SubprocessError):
            return {"state": "failed", "rollback": "failed"}
    if previous is not None and previous != image:
        record(state / "previous-image", previous)
    record(current, image)
    return {"state": "ok", "image": image}


def pipeline(command_file: Path) -> dict[str, Any]:
    if not command_file.is_file():
        return {"state": "not_configured"}
    command = json.loads(command_file.read_text())
    if (
        not isinstance(command, list)
        or not command
        or not all(
            isinstance(argument, str) and argument and "\x00" not in argument
            for argument in command
        )
        or not Path(command[0]).is_absolute()
    ):
        raise ValueError(
            "Pipeline command must be an argv array with an absolute executable"
        )
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            timeout=3300,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "state": "ok" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"state": "timeout"}
    except OSError:
        return {"state": "failed"}


def preflight(data: Path) -> dict[str, Any]:
    total = next(
        line
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemTotal:")
    )
    if int(total.split()[1]) * 1024 < 14 * 1024**3 or (os.cpu_count() or 0) < 4:
        raise ValueError("Production needs the 4-vCPU/16-GB VM profile")
    if shutil.disk_usage(data).free < 10 * 1024**3:
        raise ValueError("Production needs at least 10 GiB free disk")
    if (data / "otp/.build-incomplete").exists() or not all(
        (data / path).is_file()
        for path in (
            "otp/graph.obj",
            "graphs/active.json.gz",
            "otp/transjakarta.gtfs.zip",
            "osrm/car/pilot.osrm.mldgr",
            "osrm/motorcycle/pilot.osrm.mldgr",
        )
    ):
        raise ValueError("Production routing graphs are incomplete")
    return {"state": "ok", "profile": "ubuntu-4cpu-16gb-otp8g"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("monitor", "pipeline", "release", "rollback", "preflight", "config"),
    )
    parser.add_argument("--url", default=os.getenv("HIRUP_PUBLIC_URL", ""))
    parser.add_argument("--max-age", type=int, default=5400)
    parser.add_argument("--local-http", action="store_true")
    parser.add_argument(
        "--command", type=Path, default=Path("/etc/hirup/pipeline-command.json")
    )
    parser.add_argument("--settings", type=Path, default=Path("/etc/hirup/deploy.env"))
    parser.add_argument("--state", type=Path, default=Path("/var/lib/hirup/releases"))
    parser.add_argument("--image")
    parser.add_argument("--data", type=Path, default=Path("/var/lib/hirup/data"))
    args = parser.parse_args()
    try:
        if args.action == "monitor":
            result = monitor(args.url, args.max_age, local_http=args.local_http)
        elif args.action == "pipeline":
            result = pipeline(args.command)
        elif args.action == "preflight":
            result = preflight(args.data)
        else:
            image = args.image
            if args.action == "rollback":
                image = (args.state / "previous-image").read_text().strip()
            elif image is None:
                image = (args.state / "current-image").read_text().strip()
            assert image is not None
            image = image_reference(image)
            if args.action == "config":
                compose(args.settings, image, "config", "--quiet")
                result = {"state": "ok"}
            else:
                result = deploy(args.settings, args.state, image, args.url)
    except (ValueError, OSError, subprocess.SubprocessError):
        result = {"state": "failed", "reason": "invalid_settings_or_operation_failed"}
    print(json.dumps({"at": datetime.now(UTC).isoformat(), **result}))
    if result["state"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
