"""Raster fixtures stay synthetic; startup/shutdown must respect GDAL ownership."""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from services.api import main as api_main
from services.api import refresh as aq_refresh
from services.api.main import create_app
from services.api.runtime import Runtime
from services.exposure.aq_provider import CogAQProvider
from services.exposure.geometry import unproject
from tests.test_aq_provider import BOUNDS, TS, raster_set


async def test_lifespan_closes_cog_on_its_opening_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = raster_set(tmp_path)
    for name in ("HIRUP_AQ_MANIFESTS", "HIRUP_AQ_INPUTS", "HIRUP_CITY_MEDIANS", "HIRUP_AQ_HISTORY"):
        monkeypatch.delenv(name, raising=False)

    def configured(http: httpx.AsyncClient) -> Runtime:
        runtime = Runtime.unavailable()
        runtime.cog = CogAQProvider(tmp_path, (manifest,), bounds=BOUNDS, allow_synthetic=True)
        return runtime

    monkeypatch.setattr(Runtime, "from_env", staticmethod(configured))
    app = create_app()
    async with app.router.lifespan_context(app):
        cog = app.state.runtime.cog
        samples = await asyncio.to_thread(cog.sample, (unproject(699050, 9313950),), TS)
        assert samples.data_quality == "synthetic"
        assert samples.p50[0] == 10

    def remove_raster() -> None:
        next(tmp_path.rglob("*.tif")).unlink()

    await asyncio.to_thread(remove_raster)


async def test_startup_reload_and_shutdown_share_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = raster_set(tmp_path)
    monkeypatch.setenv("HIRUP_AQ_MANIFESTS", json.dumps([str(manifest)]))
    refreshed = asyncio.Event()

    def configured(http: httpx.AsyncClient) -> Runtime:
        runtime = Runtime.unavailable()
        runtime.cog = CogAQProvider(tmp_path, (manifest,), bounds=BOUNDS, allow_synthetic=True)
        return runtime

    async def reload_once(runtime: Runtime, *unused: object, owner: ThreadPoolExecutor) -> None:
        assert runtime.cog is not None
        await asyncio.get_running_loop().run_in_executor(owner, runtime.cog.reload, (manifest,))
        refreshed.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(Runtime, "from_env", staticmethod(configured))
    monkeypatch.setattr(api_main, "hourly", reload_once)
    app = create_app()
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(refreshed.wait(), timeout=5)
        samples = await asyncio.to_thread(
            app.state.runtime.cog.sample, (unproject(699150, 9313850),), TS
        )
        assert samples.p50[0] == 40


async def test_hourly_cancellation_waits_for_pending_owner_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, released, finished = threading.Event(), threading.Event(), threading.Event()
    signatures = 0
    original_sleep = asyncio.sleep

    def signature(paths: tuple[Path, ...]) -> tuple[tuple[int, int], ...]:
        nonlocal signatures
        signatures += 1
        return ((min(signatures, 2), 0),)

    async def poll_without_minute_delay(delay: float) -> None:
        await original_sleep(0)

    def pending_io(*arguments: object) -> None:
        entered.set()
        assert released.wait(5)
        finished.set()

    monkeypatch.setattr(aq_refresh, "signature", signature)
    monkeypatch.setattr(aq_refresh, "refresh", pending_io)
    monkeypatch.setattr(asyncio, "sleep", poll_without_minute_delay)
    with ThreadPoolExecutor(max_workers=1) as owner:
        task = asyncio.create_task(
            aq_refresh.hourly(Runtime.unavailable(), (), None, None, owner=owner)
        )
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await original_sleep(0.05)
        assert not task.done()
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
