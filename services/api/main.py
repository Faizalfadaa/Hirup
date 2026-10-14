import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi

from services.api import errors
from services.api.refresh import hourly
from services.api.routes import aq, greenspaces, health, insights, routes
from services.api.runtime import Runtime
from services.api.schemas.problem import Problem

CONTRACT_VERSION = "1.0.0"

_DESCRIPTION = """\
Hirup API v1. Plans multimodal trips in the Jakarta pilot area and ranks them by inhaled
PM2.5 dose. Exported from the Pydantic models in `services/api/schemas`; do not edit by hand.

Conventions: times ISO 8601 with offset (Asia/Jakarta, +07:00); coordinates WGS84;
polylines encoded with precision 6; every successful response carries `data_quality`
(real | approximated | synthetic); errors are RFC 9457 Problem Details
(`application/problem+json`). `x-priority` marks MoSCoW priority (M, S, C).
"""


def create_app(runtime: Runtime | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if runtime is not None:
            yield
            return
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="hirup-aq-owner") as owner:
            async with (
                httpx.AsyncClient(trust_env=False) as http,
                configured_runtime(http, owner) as configured,
            ):
                app.state.runtime = configured
                yield

    @asynccontextmanager
    async def configured_runtime(
        http: httpx.AsyncClient, owner: ThreadPoolExecutor
    ) -> AsyncIterator[Runtime]:
        loop = asyncio.get_running_loop()
        configured = Runtime.unavailable()
        try:
            try:
                configured = await loop.run_in_executor(owner, Runtime.from_env, http)
                await loop.run_in_executor(
                    owner, configured.prepare_hour, datetime.now(ZoneInfo("Asia/Jakarta"))
                )
            except (ValueError, OSError, KeyError):
                logging.getLogger(__name__).warning(
                    "Routing/AQ startup inputs unavailable; service degraded"
                )
                if configured.cog is not None:
                    await loop.run_in_executor(owner, configured.cog.close)
                configured = Runtime.unavailable()
            try:
                manifests = tuple(
                    Path(name) for name in json.loads(os.getenv("HIRUP_AQ_MANIFESTS") or "[]")
                )
            except (TypeError, ValueError):
                manifests = ()
            fallback = Path(os.environ["HIRUP_AQ_INPUTS"]) if os.getenv("HIRUP_AQ_INPUTS") else None
            references = (
                Path(os.environ["HIRUP_CITY_MEDIANS"]) if os.getenv("HIRUP_CITY_MEDIANS") else None
            )
            history = (
                Path(os.environ["HIRUP_AQ_HISTORY"]) if os.getenv("HIRUP_AQ_HISTORY") else None
            )
            worker = asyncio.create_task(
                hourly(configured, manifests, fallback, references, history, owner=owner)
            )
            try:
                yield configured
            finally:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker
        finally:
            if configured.cog is not None:
                await loop.run_in_executor(owner, partial(configured.cog.close))

    app = FastAPI(
        title="Hirup API",
        version=CONTRACT_VERSION,
        separate_input_output_schemas=False,
        lifespan=lifespan,
    )
    app.state.runtime = runtime or Runtime.unavailable()
    errors.install(app)
    v1 = APIRouter(prefix="/v1")
    for module in (routes, aq, insights, greenspaces, health):
        v1.include_router(module.router)
    app.include_router(v1)
    app.openapi = lambda: _openapi(app)  # type: ignore[method-assign]
    return app


def _openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    spec = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=_DESCRIPTION,
        routes=app.routes,
        separate_input_output_schemas=False,
    )
    spec["servers"] = [
        {"url": "http://localhost:8000", "description": "local API (make api)"},
        {"url": "http://localhost:4010", "description": "mock (make mock)"},
    ]
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    # Validation errors are returned as 400 Problem, not FastAPI's default 422.
    for path_item in spec["paths"].values():
        for operation in path_item.values():
            operation.get("responses", {}).pop("422", None)
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    schemas["Problem"] = Problem.model_json_schema(ref_template="#/components/schemas/{model}")
    schemas.update(schemas["Problem"].pop("$defs", {}))
    app.openapi_schema = spec
    return spec


app = create_app()
