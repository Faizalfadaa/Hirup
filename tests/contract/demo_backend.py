"""Local contract-test server: real routers plus explicitly synthetic AQ fixtures."""

import asyncio
import os
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from fastapi import FastAPI

from services.api.main import create_app
from services.api.runtime import ROOT, Runtime
from services.exposure.aq_provider import CogAQProvider
from services.exposure.daily_summary import DailySummaryService
from services.exposure.forecast import ForecastService
from tests.test_aq_provider import BOUNDS
from tests.test_daily_summary import daily_cogs
from tests.test_forecast import NOW


@asynccontextmanager
async def synthetic_cog(root: Path) -> AsyncIterator[CogAQProvider]:
    paths = await asyncio.to_thread(daily_cogs, root)
    loop = asyncio.get_running_loop()
    # Rasterio's opened dataset environment must also be closed on its owner thread.
    with ThreadPoolExecutor(max_workers=1) as owner:
        cog = await loop.run_in_executor(
            owner, partial(CogAQProvider, root, paths, bounds=BOUNDS, allow_synthetic=True)
        )
        try:
            yield cog
        finally:
            await loop.run_in_executor(owner, cog.close)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient(trust_env=False) as upstream:
        runtime = await asyncio.to_thread(
            Runtime.from_env,
            upstream,
            {
                "HIRUP_DEMO": "true",
                "HIRUP_DEMO_MIN_PM25": "10",
                "HIRUP_DEMO_MAX_PM25": "80",
                "HIRUP_DEMO_SEED": "20261014",
                "HIRUP_DEMO_REFERENCE_PM25": "40",
                "HIRUP_TRUNK_PENALTY": "2",
                "HIRUP_DATA_DIR": str(ROOT / "data"),
                "OTP_URL": os.environ.get("OTP_URL", "http://127.0.0.1:18080/otp/gtfs/v1"),
                "OSRM_CAR_URL": os.environ.get("OSRM_CAR_URL", "http://127.0.0.1:5000"),
                "OSRM_MOTO_URL": os.environ.get("OSRM_MOTO_URL", "http://127.0.0.1:5001"),
            },
        )
        await asyncio.to_thread(runtime.prepare_hour, NOW)
        with TemporaryDirectory(prefix="hirup-aq-contract-") as folder:
            root = Path(folder)
            async with synthetic_cog(root) as cog:
                assert runtime.params is not None
                runtime.forecast = ForecastService(
                    BOUNDS, cog, allow_synthetic=True, now=lambda: NOW
                )
                runtime.daily_summary = DailySummaryService(
                    BOUNDS, runtime.params, cog, allow_synthetic=True, now=lambda: NOW
                )
                app.state.runtime = runtime
                yield


# Actual FastAPI routes/schemas and runtime orchestration; only AQ inputs are test fixtures.
# No environment-based fixture switch exists in production startup.
app = create_app(Runtime.unavailable())
app.router.lifespan_context = lifespan
