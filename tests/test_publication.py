"""Atomic P2 input selection and failed-refresh rollback using labelled synthetic rasters."""

import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from services.api import runtime as runtime_module
from services.api.refresh import refresh
from services.api.runtime import Runtime
from services.exposure.aq_provider import AQUnavailableError, CogAQProvider
from services.exposure.geometry import unproject
from services.exposure.publication import Publication
from tests.test_aq_provider import TS, raster_set


def publication(root: Path, number: int = 1) -> Path:
    run = root / f"run-{number}"
    run.mkdir()
    manifest = raster_set(run)
    raw = json.loads(manifest.read_text())
    raw["files"] = {key: f"run-{number}/{value}" for key, value in raw["files"].items()}
    raw["model_version"] = f"synthetic-{number}"
    raw["generated_at"] = (TS + timedelta(minutes=number)).isoformat()
    manifest.write_text(json.dumps(raw))
    fallback = run / "inputs.json"
    fallback.write_text(json.dumps({"source": "unit-test-only", "data_quality": "approximated"}))
    median = run / "medians.json"
    median.write_text(
        json.dumps({TS.isoformat(): {"value": 25 * number, "source": "unit-test-only"}})
    )
    pointer = root / "aq_publication.json"
    pointer.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": raw["generated_at"],
                "manifests": [f"run-{number}/manifest.json"],
                "fallback": f"run-{number}/inputs.json",
                "medians": f"run-{number}/medians.json",
                "history": None,
                "kelurahan": None,
                "tiles_available": False,
            }
        )
    )
    return pointer


@pytest.mark.parametrize("name", ["../outside.json", "/etc/passwd", "missing.json"])
def test_publication_rejects_missing_and_escaping_paths(tmp_path: Path, name: str) -> None:
    pointer = publication(tmp_path)
    raw = json.loads(pointer.read_text())
    raw["fallback"] = name
    pointer.write_text(json.dumps(raw))
    with pytest.raises((AQUnavailableError, ValueError)):
        Publication.load(tmp_path, pointer)


async def test_missing_startup_publication_recovers_and_bad_refresh_retains_prior(tmp_path: Path):
    settings = {
        "HIRUP_DATA_DIR": str(tmp_path),
        "HIRUP_AQ_PUBLICATION": str(tmp_path / "aq_publication.json"),
        "HIRUP_AQ_MANIFESTS": "invalid legacy configuration must not be mixed in",
    }
    async with httpx.AsyncClient() as http:
        runtime = Runtime.from_env(http, settings)
        assert runtime.planner is not None
        assert runtime.cog is not None
        runtime.cog.allow_synthetic = (
            True  # Explicit test-only opt-in; no production switch exists.
        )
        try:
            pointer = publication(tmp_path)
            refresh(runtime, TS, (), None, None, publication_path=pointer)
            assert runtime.cog.manifest(TS).model_version == "synthetic-1"
            assert runtime.references[TS] == 25
            assert not runtime.aq.tiles_available
            with pytest.raises(AQUnavailableError):
                runtime.aq.point(unproject(699050, 9313950), TS)
            assert runtime.cog.sample((unproject(699050, 9313950),), TS).data_quality == "synthetic"
            publication(tmp_path, 2)
            (tmp_path / "run-2/medians.json").write_text(
                json.dumps({TS.isoformat(): {"value": 99}})
            )
            with pytest.raises(ValueError, match="source"):
                refresh(runtime, TS, (), None, None, publication_path=pointer)
            assert runtime.references[TS] == 25
            assert runtime.cog.manifest(TS).model_version == "synthetic-1"
            assert runtime.cog.sample((unproject(699050, 9313950),), TS).p50[0] == 10
            (tmp_path / "run-2/inputs.json").write_text("null")
            with pytest.raises(ValueError, match="structure"):
                refresh(runtime, TS, (), None, None, publication_path=pointer)
            assert runtime.cog.manifest(TS).model_version == "synthetic-1"
        finally:
            runtime.cog.close()


async def test_malformed_startup_publication_closes_readers_and_can_retry(tmp_path, monkeypatch):
    pointer = publication(tmp_path)
    (tmp_path / "run-1/inputs.json").write_text('{"data_quality":"approximated"}')
    closed = []

    class TestReader(CogAQProvider):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, allow_synthetic=True)

        def close(self):
            closed.append(self)
            super().close()

    monkeypatch.setattr(runtime_module, "CogAQProvider", TestReader)
    async with httpx.AsyncClient() as http:
        runtime = Runtime.from_env(
            http, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_AQ_PUBLICATION": str(pointer)}
        )
        try:
            assert runtime.planner is not None
            assert runtime.cog is not None
            assert len(closed) == 1
            next((tmp_path / "run-1/rasters").glob("*.tif")).unlink()
            publication(tmp_path, 2)
            refresh(runtime, TS, (), None, None, publication_path=pointer)
            assert runtime.cog.manifest(TS).model_version == "synthetic-2"
        finally:
            runtime.cog.close()
