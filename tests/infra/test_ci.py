"""CI rejects corrupt caches/resources and cleans only processes it owns."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from infra.ci import check, graphs


@pytest.mark.parametrize("has_transit", [True, False])
def test_otp_initialization_is_bounded_and_requires_transit(
    monkeypatch: pytest.MonkeyPatch, has_transit: bool
) -> None:
    queries: list[dict[str, Any]] = []

    class Opener:
        def open(self, request: urllib.request.Request, timeout: int) -> io.BytesIO:
            assert timeout == 30
            assert isinstance(request.data, bytes)
            queries.append(json.loads(request.data))
            response = {
                "data": {
                    "plan": {
                        "itineraries": [{"duration": 120, "legs": [{"transitLeg": has_transit}]}]
                    }
                }
            }
            return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    if has_transit:
        check.warm_transit()
        assert len(queries) == 3
    else:
        with pytest.raises(RuntimeError, match="successful transit"):
            check.warm_transit()
        assert len(queries) == 1


@pytest.mark.parametrize("failures", [1, 3])
def test_initialization_transport_retries_are_bounded_and_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failures: int
) -> None:
    calls = 0

    class Opener:
        def open(self, request: urllib.request.Request, timeout: int) -> io.BytesIO:
            nonlocal calls
            calls += 1
            if calls <= failures:
                raise TimeoutError("upstream private URL must not be logged")
            return io.BytesIO(
                json.dumps(
                    {
                        "data": {
                            "plan": {
                                "itineraries": [{"duration": 120, "legs": [{"transitLeg": True}]}]
                            }
                        }
                    }
                ).encode()
            )

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    path = tmp_path / "initialization.json"
    if failures == 3:
        with pytest.raises(RuntimeError, match="successful transit"):
            check.warm_transit(path)
    else:
        check.warm_transit(path)
    report = json.loads(path.read_text())
    assert report["success"] is (failures == 1)
    assert len(report["attempts"]) == (4 if failures == 1 else 3)
    assert report["attempts"][0]["outcome"] == "transport_error"
    assert "private URL" not in path.read_text()


@pytest.fixture
def graph_repo(tmp_path: Path) -> Path:
    inputs = (
        "uv.lock",
        "contracts/golden_od.json",
        "contracts/exposure_params.yaml",
        "infra/images.env",
        "infra/tools/Dockerfile",
        "infra/otp/build-config.json",
        "services/routing/build_active_graph.py",
        "services/exposure/geometry.py",
    )
    artifacts = list(graphs.REQUIRED)
    for profile in ("car", "motorcycle"):
        artifacts.extend(
            f"data/osrm/{profile}/pilot.osrm{suffix}"
            for suffix in (".partition", ".cells", ".cell_metrics", ".mldgr", ".properties")
        )
    for filename in (*inputs, *artifacts, *(item[1] for item in graphs.SOURCES.values())):
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(filename.encode())
    return tmp_path


def test_cache_round_trip_does_not_require_raw_downloads_on_restore(graph_repo: Path) -> None:
    expected = graphs.write_manifest(graph_repo, "test-v1")
    for _, filename in graphs.SOURCES.values():
        (graph_repo / filename).unlink()
    assert graphs.verify_manifest(graph_repo, "test-v1") == expected
    # Changes in a build's numerical/grid configuration cannot reuse old graphs.
    (graph_repo / "services/exposure/geometry.py").write_text("changed")
    with pytest.raises(ValueError, match="identity"):
        graphs.verify_manifest(graph_repo, "test-v1")


@pytest.mark.parametrize("change", ["modified", "removed", "extra", "empty", "incomplete"])
def test_corrupt_graph_cache_fails_closed(graph_repo: Path, change: str) -> None:
    graphs.write_manifest(graph_repo, "test-v1")
    graph = graph_repo / "data/otp/graph.obj"
    if change == "modified":
        graph.write_bytes(b"other graph of the same size".ljust(graph.stat().st_size))
    elif change == "removed":
        graph.unlink()
    elif change == "extra":
        (graph.parent / "untracked.json").write_text("{}")
    elif change == "empty":
        graph.write_bytes(b"")
    else:
        (graph.parent / ".build-incomplete").touch()
    with pytest.raises(ValueError, match=r"graph|Graph|artifact"):
        graphs.verify_manifest(graph_repo, "test-v1")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("otp_heap", "8g"),
        ("dataset_version", "different"),
        ("schema", 2),
        ("images", ["otp:latest"]),
        ("sources", {}),
        ("built_at", "2099-01-01T00:00:00+00:00"),
    ],
)
def test_wrong_cache_provenance_fails(graph_repo: Path, field: str, value: Any) -> None:
    manifest = graphs.write_manifest(graph_repo, "test-v1")
    manifest[field] = value
    (graph_repo / graphs.MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=r"cache|provenance|timestamp"):
        graphs.verify_manifest(graph_repo, "test-v1")


@pytest.mark.parametrize("version", ["", "../main", "a;echo secret", "bad\ninput", "A", "a" * 41])
def test_dataset_version_rejects_shell_path_and_multiline_inputs(
    graph_repo: Path, version: str
) -> None:
    with pytest.raises(ValueError, match="slug"):
        graphs.identity(graph_repo, version)


def test_runner_resource_boundaries() -> None:
    # Exact floor fits the declared CI policy: host/Docker 7 GiB, free disk 9 GiB.
    assert graphs.resource_report(7 * graphs.GIB, 7 * graphs.GIB, 9 * graphs.GIB) == {
        "host_memory_bytes": 7516192768,
        "docker_memory_bytes": 7516192768,
        "free_disk_bytes": 9663676416,
    }
    for memory, docker_memory, disk in (
        (7 * graphs.GIB - 1, 8 * graphs.GIB, 10 * graphs.GIB),
        (8 * graphs.GIB, 7 * graphs.GIB - 1, 10 * graphs.GIB),
        (8 * graphs.GIB, 8 * graphs.GIB, 9 * graphs.GIB - 1),
    ):
        with pytest.raises(ValueError, match="CI needs"):
            graphs.resource_report(memory, docker_memory, disk)


class Child:
    def __init__(self, stubborn: bool = False) -> None:
        self.calls: list[str] = []
        self.stubborn = stubborn

    def terminate(self) -> None:
        self.calls.append("terminate")

    def wait(self, timeout: float) -> int:
        self.calls.append("wait")
        if self.stubborn:
            self.stubborn = False
            raise subprocess.TimeoutExpired("fixture", timeout)
        return 0

    def kill(self) -> None:
        self.calls.append("kill")


@pytest.mark.parametrize("stubborn", [False, True])
def test_fixture_child_is_cleaned_after_failed_readiness(
    monkeypatch: pytest.MonkeyPatch, stubborn: bool
) -> None:
    child = Child(stubborn)
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: child)

    def failure(process: object) -> None:
        raise TimeoutError("not ready")

    monkeypatch.setattr(check, "wait_ready", failure)
    with pytest.raises(TimeoutError), check.fixture_server():
        pytest.fail("Server must never yield after failed startup")
    assert child.calls == (
        ["terminate", "wait", "kill", "wait"] if stubborn else ["terminate", "wait"]
    )


def test_fixture_child_is_cleaned_after_contract_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    child = Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: child)
    monkeypatch.setattr(check, "wait_ready", lambda process: None)
    with pytest.raises(RuntimeError), check.fixture_server():
        raise RuntimeError("contract failed")
    assert child.calls == ["terminate", "wait"]


def test_workflow_manual_only_exact_cache_and_unconditional_cleanup() -> None:
    yaml = pytest.importorskip("yaml", reason="Root backend environment validates workflow YAML")
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/routing-golden.yml").read_text())
    # PyYAML 1.1 resolves 'on' as True; GitHub's YAML 1.2 treats it as a string.
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["routing"]
    assert job["env"]["HIRUP_OTP_BUILD_HEAP"] == "4g"
    assert job["runs-on"] == "ubuntu-24.04"
    steps = job["steps"]
    restore, save = [step for step in steps if "actions/cache/" in step.get("uses", "")]
    assert restore["with"] == save["with"]
    assert "restore-keys" not in restore["with"]
    assert "java-latest" not in restore["with"]["path"]
    assert all(len(step["uses"].split("@")[1]) == 40 for step in steps if "uses" in step)
    assert steps[-1]["if"] == "always()"
    assert steps[-1]["run"] == "make -f infra/Makefile ci-down"


def test_regular_ci_checks_develop_and_all_python_packages() -> None:
    yaml = pytest.importorskip("yaml")
    workflow = yaml.safe_load((graphs.ROOT / ".github/workflows/ci.yml").read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers["push"]["branches"]) == {"main", "develop"}
    assert set(triggers["pull_request"]["branches"]) == {"main", "develop"}
    assert "workflow_dispatch" in triggers
    commands = "\n".join(step.get("run", "") for step in workflow["jobs"]["python"]["steps"])
    assert "mypy services" in commands
    assert "pipelines/src ml/src" in commands
    assert "infra/scripts infra/ci infra/deploy" in commands
    assert 'pytest -q -m "not integration"' in commands


@pytest.mark.parametrize("platform", ["Linux", "MINGW64_NT-10.0", "Darwin"])
def test_tools_bind_mounts_use_host_identity_only_on_linux(tmp_path: Path, platform: str) -> None:
    bash = (
        Path("C:/Program Files/Git/bin/bash.exe")
        if os.name == "nt"
        else Path(shutil.which("bash") or "/missing")
    )
    if not bash.is_file():
        pytest.skip("Git Bash/bash unavailable")
    script = (
        'uname() { printf "%s\\n" "$TEST_PLATFORM"; }; '
        'id() { if [[ "$1" == -u ]]; then echo 1234; else echo 2345; fi; }; '
        'docker() { printf "<%s>\\n" "$@"; }; '
        "source infra/scripts/common.sh; run_python infra/scripts/routing_data.py bbox"
    )
    result = subprocess.run(
        [str(bash), "-c", script],
        cwd=graphs.ROOT,
        env={**os.environ, "TEST_PLATFORM": platform},
        capture_output=True,
        text=True,
        check=True,
    )
    assert ("<--user>\n<1234:2345>" in result.stdout) is (platform == "Linux")
    assert "<--mount>" in result.stdout
    assert "<python>" in result.stdout


@pytest.mark.parametrize(
    ("project", "compose_failure"),
    [
        ("hirup-ci-unit", False),
        ("hirup-ci-unit", True),
        ("hirup-routing", False),
        ("", False),
        ("hirup-ci-a;touch pwned", False),
    ],
)
def test_stack_cleanup_restricts_docker_to_its_ci_project(
    tmp_path: Path, project: str, compose_failure: bool
) -> None:
    if os.name == "nt":
        bash = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Git/bin/bash.exe"
    else:
        bash = Path(shutil.which("bash") or "/missing-bash")
    if not bash.is_file():
        pytest.skip("Git Bash/bash unavailable")
    stub = tmp_path / "docker"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s " "$@" >> "$STUB_LOG"; printf "\\n" >> "$STUB_LOG"\n'
        'if [[ "$1" == compose && "$STUB_COMPOSE_FAIL" == 1 ]]; then exit 9; fi\n'
        'if [[ "$1" == ps ]]; then printf "ci-build-id\\n"; fi\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    log = tmp_path / "calls.txt"
    env = {
        **os.environ,
        "HIRUP_CI_PROJECT": project,
        "STUB_DIR": tmp_path.as_posix(),
        "STUB_LOG": log.as_posix(),
        "STUB_COMPOSE_FAIL": "1" if compose_failure else "0",
    }
    command = (
        'if command -v cygpath >/dev/null; then STUB_DIR="$(cygpath -u "$STUB_DIR")"; fi; '
        'export PATH="$STUB_DIR:$PATH"; bash infra/ci/stack.sh down'
    )
    result = subprocess.run(
        [str(bash), "-c", command], cwd=graphs.ROOT, env=env, capture_output=True
    )
    if project != "hirup-ci-unit":
        assert result.returncode != 0
        assert not log.exists()
    else:
        assert result.returncode == (9 if compose_failure else 0), result.stderr.decode()
        calls = log.read_text().splitlines()
        assert len(calls) == 3
        assert "--project-name hirup-ci-unit" in calls[0]
        assert "down --remove-orphans" in calls[0]
        assert calls[1] == "ps -aq --filter label=hirup.ci.project=hirup-ci-unit "
        assert calls[2] == "rm -f ci-build-id "


@pytest.mark.parametrize(
    ("project", "heap", "expected"),
    [
        ("", "8g", True),
        ("hirup-ci-unit", "4g", True),
        ("", "4g", False),
        ("hirup-routing", "4g", False),
        ("hirup-ci-unit", "16g", False),
    ],
)
def test_graph_build_heap_override_requires_isolated_ci(
    tmp_path: Path, project: str, heap: str, expected: bool
) -> None:
    bash = (
        Path("C:/Program Files/Git/bin/bash.exe")
        if os.name == "nt"
        else Path(shutil.which("bash") or "/missing")
    )
    if not bash.is_file():
        pytest.skip("Git Bash/bash unavailable")
    script = tmp_path / "build_graphs.sh"
    script.write_text((graphs.ROOT / "infra/scripts/build_graphs.sh").read_text(), encoding="utf-8")
    (tmp_path / "common.sh").write_text(
        'REPO_ROOT="$TEST_ROOT"; REPO_HOST="$TEST_ROOT"; INFRA_HOST="$TEST_ROOT"\n'
        "OSRM_IMAGE=osrm:test; OTP_IMAGE=otp:test\n"
        'ensure_tools() { :; }; run_python() { mkdir -p "$TEST_ROOT/data/otp"; }\n'
        'docker() { printf "%s " "$@" >> "$STUB_LOG"; printf "\\n" >> "$STUB_LOG"; }\n'
        'compose() { docker compose --project-name hirup-routing "$@"; }\n',
        encoding="utf-8",
    )
    osm = tmp_path / "data/osm/pilot.osm.pbf"
    osm.parent.mkdir(parents=True)
    osm.write_bytes(b"test osm")
    log = tmp_path / "calls.txt"
    result = subprocess.run(
        [str(bash), str(script)],
        capture_output=True,
        env={
            **os.environ,
            "HIRUP_CI_PROJECT": project,
            "HIRUP_OTP_BUILD_HEAP": heap,
            "TEST_ROOT": tmp_path.as_posix(),
            "STUB_LOG": log.as_posix(),
        },
    )
    assert (result.returncode == 0) is expected, result.stderr.decode()
    if not expected:
        assert not log.exists()
        assert not (tmp_path / "data/otp").exists()
    else:
        calls = log.read_text()
        assert f"JAVA_TOOL_OPTIONS=-Xmx{heap}" in calls
        assert f"--project-name {project or 'hirup-routing'}" in calls
        if project:
            assert "--project-name hirup-routing " not in calls
            assert "--label hirup.ci.project=hirup-ci-unit" in calls
