"""Versioned graph-cache integrity and runner preflight (standard library only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GIB = 1024**3
MANIFEST = "data/ci/graphs.json"
REQUIRED = (
    "data/osm/pilot.osm.pbf",
    "data/otp/graph.obj",
    "data/otp/pilot.osm.pbf",
    "data/otp/transjakarta.gtfs.zip",
    "data/otp/build-config.json",
    "data/otp/router-config.json",
    "data/otp/otp-config.json",
    "data/graphs/active.json.gz",
)
SOURCES = {
    "osm_java": (
        "https://download.geofabrik.de/asia/indonesia/java-latest.osm.pbf",
        "data/osm/java-latest.osm.pbf",
    ),
    "gtfs_bus": (
        "https://files.mobilitydatabase.org/mdb-1909/latest.zip",
        "data/gtfs/transjakarta.gtfs.zip",
    ),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint(root: Path) -> str:
    files = {
        root / "uv.lock",
        root / "contracts/golden_od.json",
        root / "infra/images.env",
        root / "contracts/exposure_params.yaml",
    }
    for folder in (
        "infra/scripts",
        "infra/otp",
        "infra/osrm",
        "infra/tools",
        "infra/ci",
        "services/routing",
        "services/exposure",
        "data_prep/gtfs_manual",
    ):
        directory = root / folder
        if directory.exists():
            files.update(
                path
                for path in directory.rglob("*")
                if path.is_file()
                and path.suffix
                in {".py", ".sh", ".json", ".lua", ".yml", ".txt", ".zip"}
                and "__pycache__" not in path.parts
            )
    files.add(root / "infra/tools/Dockerfile")
    encoded = [
        (path.relative_to(root).as_posix(), digest(path)) for path in sorted(files)
    ]
    return hashlib.sha256(json.dumps(encoded).encode()).hexdigest()


def inventory(root: Path) -> dict[str, dict[str, str | int]]:
    if (root / "data/otp/.build-incomplete").exists():
        raise ValueError("Incomplete graph build")
    files = {root / "data/osm/pilot.osm.pbf", root / "data/graphs/active.json.gz"}
    for folder in ("data/otp", "data/osrm/car", "data/osrm/motorcycle"):
        directory = root / folder
        if directory.is_symlink():
            raise ValueError("Cache directories must not be symlinks")
        files.update(path for path in directory.glob("*") if path.is_file())
    relative = {path.relative_to(root).as_posix() for path in files}
    required = set(REQUIRED)
    for profile in ("car", "motorcycle"):
        required.update(
            f"data/osrm/{profile}/pilot.osrm{suffix}"
            for suffix in (
                ".partition",
                ".cells",
                ".cell_metrics",
                ".mldgr",
                ".properties",
            )
        )
    if not required.issubset(relative):
        raise ValueError("Missing required graph artifacts")
    result: dict[str, dict[str, str | int]] = {}
    for path in sorted(files):
        if path.is_symlink() or not path.resolve().is_relative_to(
            (root / "data").resolve()
        ):
            raise ValueError("Unsafe graph artifact path")
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("Empty or absent graph artifact")
        name = path.relative_to(root).as_posix()
        if (
            path.suffix not in {".json", ".zip", ".pbf", ".obj", ".gz"}
            and "/pilot.osrm" not in name
        ):
            raise ValueError("Unexpected file in graph cache")
        result[name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return result


def identity(root: Path, version: str) -> dict[str, str | int]:
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", version) is None:
        raise ValueError("Dataset version must be a short lowercase slug")
    return {
        "schema": 1,
        "dataset_version": version,
        "build_fingerprint": fingerprint(root),
        "otp_heap": "4g",
    }


def write_manifest(root: Path, version: str) -> dict[str, Any]:
    sources = {
        name: {
            "url": url,
            "sha256": digest(root / filename),
            "bytes": (root / filename).stat().st_size,
            "download_completed_at": datetime.fromtimestamp(
                (root / filename).stat().st_mtime, UTC
            ).isoformat(),
        }
        for name, (url, filename) in SOURCES.items()
    }
    manifest = {
        **identity(root, version),
        "built_at": datetime.now(UTC).isoformat(),
        "images": (root / "infra/images.env").read_text().splitlines(),
        "sources": sources,
        "files": inventory(root),
    }
    output = root / MANIFEST
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_manifest(root: Path, version: str) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((root / MANIFEST).read_text())
    if any(
        manifest.get(key) != value for key, value in identity(root, version).items()
    ):
        raise ValueError("Graph cache identity mismatch")
    if manifest.get("images") != (root / "infra/images.env").read_text().splitlines():
        raise ValueError("Graph cache image mismatch")
    published = datetime.fromisoformat(manifest["built_at"])
    if published.tzinfo is None or published > datetime.now(UTC):
        raise ValueError("Invalid graph build timestamp")
    sources = manifest["sources"]
    if set(sources) != set(SOURCES):
        raise ValueError("Missing source provenance")
    for name, (url, _) in SOURCES.items():
        source = sources[name]
        if (
            source.get("url") != url
            or re.fullmatch(r"[a-f0-9]{64}", source.get("sha256", "")) is None
        ):
            raise ValueError("Invalid source provenance")
        if type(source.get("bytes")) is not int or source["bytes"] <= 0:
            raise ValueError("Invalid source size")
        completed = datetime.fromisoformat(source["download_completed_at"])
        if completed.tzinfo is None or completed > published:
            raise ValueError("Invalid source download timestamp")
    if manifest.get("files") != inventory(root):
        raise ValueError("Graph cache checksum/file inventory mismatch")
    return manifest


def resource_report(memory: int, docker_memory: int, disk: int) -> dict[str, int]:
    if min(memory, docker_memory) < 7 * GIB:
        raise ValueError("CI needs at least 7 GiB host/Docker RAM for OTP heap 4g")
    if disk < 9 * GIB:
        raise ValueError("CI needs at least 9 GiB free workspace disk before downloads")
    return {
        "host_memory_bytes": memory,
        "docker_memory_bytes": docker_memory,
        "free_disk_bytes": disk,
    }


def preflight(root: Path) -> dict[str, int]:
    docker_memory = int(
        subprocess.check_output(
            ["docker", "info", "--format", "{{.MemTotal}}"], text=True
        ).strip()
    )
    meminfo = Path("/proc/meminfo")
    memory = docker_memory
    if meminfo.exists():
        total = next(
            line
            for line in meminfo.read_text().splitlines()
            if line.startswith("MemTotal:")
        )
        memory = int(total.split()[1]) * 1024
    return resource_report(memory, docker_memory, shutil.disk_usage(root).free)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("key", "write", "verify", "preflight"))
    parser.add_argument("--dataset-version", default="2026-10-14-v1")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.action == "key":
        metadata = identity(ROOT, args.dataset_version)
        print(
            f"routing-linux-v1-{metadata['dataset_version']}-{metadata['build_fingerprint']}"
        )
    elif args.action == "preflight":
        print(json.dumps(preflight(ROOT)))
    else:
        if args.action == "write" and (
            os.environ.get("HIRUP_OTP_BUILD_HEAP") != "4g"
            or re.fullmatch(
                r"hirup-ci-[a-z0-9-]+", os.environ.get("HIRUP_CI_PROJECT", "")
            )
            is None
        ):
            parser.error("Write CI provenance only after an isolated 4g CI graph build")
        operation = write_manifest if args.action == "write" else verify_manifest
        result = operation(ROOT, args.dataset_version)
        summary = {key: value for key, value in result.items() if key != "files"}
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8"
            )
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
