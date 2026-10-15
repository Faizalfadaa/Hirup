"""Test-only P2 model -> immutable COG -> P1 runtime, using seeded toy data."""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI

from hirup_ml import dataset, insights, predict, raster, train
from hirup_ml.config import load_config
from ml.tests import conftest as seeded
from services.api.main import create_app
from services.api.runtime import ROOT, Runtime
from services.exposure.aq_provider import CogAQProvider
from services.exposure.daily_summary import DailySummaryService
from services.exposure.forecast import ForecastService
from services.exposure.geometry import hour_key
from services.exposure.kelurahan import KelurahanService
from services.exposure.publication import Publication

Factory = Callable[[httpx.AsyncClient, dict[str, str]], Awaitable[Runtime]]


def seed(root: Path, day: date) -> Publication:
    """Never downloads observations, reads credentials or writes the real model registry."""
    at = datetime.fromisoformat(f"{day}T00:00:00+07:00")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HIRUP_DATA_DIR", str(root))
        patch.setattr(seeded, "LAST_HOUR", pd.Timestamp(at).tz_convert("UTC"))
        patch.setitem(load_config()["lightgbm"], "n_estimators", 40)
        patch.setitem(load_config()["tiles"]["ispu"], "verified_by", None)
        toy = seeded.toy.__wrapped__(root)
        train.train(dataset.load(), n_trials=0)
        write_set = raster.write_set

        def labelled(value, *args, **kwargs):
            return write_set(
                replace(value, data_quality="synthetic", model_version="synthetic-p2-integration"),
                *args,
                **kwargs,
            )

        patch.setattr(raster, "write_set", labelled)
        for offset in (2, 1):
            previous = at - timedelta(days=offset)
            for hour in range(24):
                valid = previous + timedelta(hours=hour)
                insights.record_hour(
                    toy["cells"],
                    np.full(toy["grid"].shape, 10.0 + hour),
                    valid,
                    "synthetic",
                    manifest={
                        "generated_at": valid.isoformat(),
                        "kind": "nowcast",
                        "model_version": "synthetic-p2-integration",
                    },
                )
        predict.run(at, now=at + timedelta(minutes=5))
    return Publication.load(root, root / "aq_publication.json")


@asynccontextmanager
async def fixture(day: date) -> AsyncIterator[Factory]:
    loop = asyncio.get_running_loop()
    with TemporaryDirectory(prefix="hirup-p2-synthetic-") as folder:
        root = Path(folder)
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="hirup-p2-test-owner") as owner:
            pub = await loop.run_in_executor(owner, seed, root, day)
            readers = []

            async def factory(http: httpx.AsyncClient, settings: dict[str, str]) -> Runtime:
                settings = {
                    **settings,
                    "HIRUP_DATA_DIR": os.environ.get("HIRUP_DATA_DIR", str(ROOT / "data")),
                }
                runtime = await loop.run_in_executor(owner, Runtime.from_env, http, settings)
                cog = await loop.run_in_executor(
                    owner,
                    partial(
                        CogAQProvider,
                        root,
                        pub.manifests,
                        bounds=runtime.aq.bounds,
                        allow_synthetic=True,
                    ),
                )
                readers.append(cog)
                assert runtime.planner is not None
                assert runtime.params is not None
                runtime.cog, runtime.aq.provider, runtime.planner.aq = cog, cog, cog
                if runtime.active is not None:
                    runtime.active.aq = cog
                runtime.demo_reference = None
                runtime.references = {
                    hour_key(datetime.fromisoformat(key)): float(item["value"])
                    for key, item in json.loads(pub.medians.read_text()).items()
                }
                runtime.model_version = runtime.planner.model_version = "synthetic-p2-integration"
                clock = datetime.fromisoformat(f"{day}T07:15:00+07:00")
                runtime.configure_advice(demo=True)
                runtime.forecast = ForecastService(
                    cog.bounds, cog, allow_synthetic=True, now=lambda: clock
                )
                runtime.daily_summary = DailySummaryService(
                    cog.bounds, runtime.params, cog, allow_synthetic=True, now=lambda: clock
                )
                runtime.kelurahan = KelurahanService(
                    pub.kelurahan, allow_synthetic=True, now=lambda: clock
                )
                runtime.kelurahan.reload()
                # Mirror production startup before serving the fixture's clock hour.
                await loop.run_in_executor(owner, runtime.prepare_hour, clock)
                return runtime

            try:
                yield factory
            finally:
                for reader in readers:
                    await loop.run_in_executor(owner, reader.close)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with (
        httpx.AsyncClient(trust_env=False) as upstream,
        fixture(date(2026, 10, 14)) as factory,
    ):
        app.state.runtime = await factory(
            upstream,
            {
                "HIRUP_DEMO": "true",
                "HIRUP_DEMO_MIN_PM25": "10",
                "HIRUP_DEMO_MAX_PM25": "80",
                "HIRUP_DEMO_REFERENCE_PM25": "40",
                "HIRUP_TRUNK_PENALTY": "2",
                "OTP_URL": os.environ.get("OTP_URL", "http://127.0.0.1:18080/otp/gtfs/v1"),
                "OSRM_CAR_URL": os.environ.get("OSRM_CAR_URL", "http://127.0.0.1:5000"),
                "OSRM_MOTO_URL": os.environ.get("OSRM_MOTO_URL", "http://127.0.0.1:5001"),
            },
        )
        yield


app = create_app(Runtime.unavailable())
app.router.lifespan_context = lifespan
