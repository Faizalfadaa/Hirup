"""Deployment health/rollback checks never print untrusted requests or commands."""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from infra.deploy import ops

OLD = "hirup-api:" + "a" * 40
NEW = "hirup-api:" + "b" * 40


@pytest.mark.parametrize(
    "image",
    ["hirup-api:latest", "hirup-api:local-review", "", "image;rm -rf /", "https://secret@host"],
)
def test_release_rejects_mutable_or_command_like_image(image: str) -> None:
    with pytest.raises(ValueError, match="commit SHA"):
        ops.image_reference(image)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:password@example.com",
        "https://example.com?q=secret",
        "https://example.com/path",
        "",
    ],
)
def test_monitor_rejects_untrusted_origins(url: str) -> None:
    with pytest.raises(ValueError, match=r"origin|HTTPS|configuration"):
        ops.monitor(url)


@pytest.mark.parametrize(
    ("quality", "age", "state"),
    [
        ("real", 5400, "ok"),
        ("approximated", 1, "ok"),
        ("real", 5401, "degraded"),
        ("synthetic", 1, "degraded"),
        ("real", None, "degraded"),
        ([], 1, "degraded"),
        ("real", True, "degraded"),
    ],
)
def test_health_uses_quality_age_and_status_not_http_200(
    quality: Any, age: Any, state: str
) -> None:
    result = ops.health_summary(
        {
            "status": "ok",
            "data_quality": quality,
            "data_age_seconds": age,
            "url": "private coordinates",
        },
        5400,
    )
    assert result["state"] == state
    assert "private" not in json.dumps(result)


def test_failed_release_restores_previous_image_and_preserves_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops.record(tmp_path / "current-image", OLD)
    calls: list[str] = []

    def compose(settings: Path, image: str, *arguments: str) -> None:
        calls.append(image)
        if image == NEW:
            raise subprocess.CalledProcessError(1, ["private command"])

    monkeypatch.setattr(ops, "compose", compose)
    monkeypatch.setattr(ops, "monitor", lambda url: {"state": "ok"})
    result = ops.deploy(tmp_path / "settings", tmp_path, NEW, "https://api.example.com")
    assert result == {"state": "failed", "rollback": "restored"}
    assert calls == [NEW, OLD, OLD]
    assert (tmp_path / "current-image").read_text().strip() == OLD


def test_degraded_release_cannot_become_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ops, "compose", lambda *args: None)
    monkeypatch.setattr(ops, "monitor", lambda url: {"state": "degraded"})
    result = ops.deploy(tmp_path / "settings", tmp_path, NEW, "https://api.example.com")
    assert result == {"state": "failed", "rollback": "no_previous_release"}
    assert not (tmp_path / "current-image").exists()


def test_successful_release_records_reversible_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops.record(tmp_path / "current-image", OLD)
    monkeypatch.setattr(ops, "compose", lambda *args: None)
    monkeypatch.setattr(ops, "monitor", lambda url: {"state": "ok"})
    assert (
        ops.deploy(tmp_path / "settings", tmp_path, NEW, "https://api.example.com")["state"] == "ok"
    )
    assert (tmp_path / "current-image").read_text().strip() == NEW
    assert (tmp_path / "previous-image").read_text().strip() == OLD


def test_missing_p2_is_not_a_successful_job(tmp_path: Path) -> None:
    assert ops.pipeline(tmp_path / "not-provided.json") == {"state": "not_configured"}


def test_readiness_waits_for_network_but_rejects_degraded_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([{"state": "unreachable"}, {"state": "ok"}])
    monkeypatch.setattr(ops, "monitor", lambda url: next(responses))
    monkeypatch.setattr(time, "sleep", lambda duration: None)
    assert ops.readiness("https://api.example.com")["state"] == "ok"
    monkeypatch.setattr(ops, "monitor", lambda url: {"state": "degraded"})
    assert ops.readiness("https://api.example.com")["state"] == "degraded"


def test_pipeline_uses_argv_and_discards_sensitive_job_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = tmp_path / "job.json"
    command.write_text(json.dumps([str(tmp_path / "python"), "script.py"]))

    def run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert arguments == [str(tmp_path / "python"), "script.py"]
        assert kwargs.get("shell") is None
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["timeout"] == 3300
        return subprocess.CompletedProcess(arguments, 7)

    monkeypatch.setattr(subprocess, "run", run)
    assert ops.pipeline(command) == {"state": "failed", "exit_code": 7}


@pytest.mark.parametrize("command", ["python job.py", [], ["relative-python", "job.py"], [123]])
def test_pipeline_rejects_shell_strings_and_invalid_argv(tmp_path: Path, command: Any) -> None:
    path = tmp_path / "job.json"
    path.write_text(json.dumps(command))
    with pytest.raises(ValueError, match="argv"):
        ops.pipeline(path)


def test_compose_contract_and_public_ports() -> None:
    yaml = pytest.importorskip("yaml")
    config = yaml.safe_load((ops.DEPLOY / "compose.yml").read_text())
    services = config["services"]
    assert {name for name, service in services.items() if "ports" in service} == {"caddy"}
    assert services["caddy"]["ports"] == ["80:80", "443:443"]
    assert services["api"]["environment"]["HIRUP_DEMO"] == "false"
    assert services["otp"]["environment"]["JAVA_TOOL_OPTIONS"] == "-Xmx8g"
    assert all(
        service["restart"] == "unless-stopped" and "healthcheck" in service
        for service in services.values()
    )
    nginx = (ops.DEPLOY / "nginx.conf").read_text()
    assert "access_log off" in nginx
    assert "error_log /dev/null" in nginx
    assert nginx.count("limit_req zone=") == 2
    assert "location = /v1/routes/plan" in nginx
    assert "location = /v1/routes/departure-advice" in nginx
    assert "proxy_intercept_errors on" not in nginx
