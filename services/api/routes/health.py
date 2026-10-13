import asyncio
from datetime import datetime
from importlib.metadata import version
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

from services.api.dependencies import get_runtime
from services.api.schemas.common import DataQuality
from services.api.schemas.examples import HEALTH
from services.api.schemas.health import HealthResponse
from services.exposure.aq_provider import AQUnavailableError
from services.exposure.geometry import Point

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service status, model version and data age",
    responses={200: {"content": {"application/json": {"example": HEALTH}}}},
    openapi_extra={"x-priority": "M"},
)
async def health(request: Request) -> HealthResponse:
    runtime = get_runtime(request)
    bounds = runtime.aq.bounds
    location = Point((bounds.min_lon + bounds.max_lon) / 2, (bounds.min_lat + bounds.max_lat) / 2)
    clock = datetime.now(ZoneInfo("Asia/Jakarta"))
    age = None
    quality = (
        DataQuality.SYNTHETIC if runtime.aq.demo_range is not None else DataQuality.APPROXIMATED
    )
    ready = False
    model_version = None
    try:
        sampled = await asyncio.to_thread(runtime.aq.point, location, clock)
        quality = DataQuality(sampled.data_quality)
        age = (
            max(0, round((clock - sampled.generated_at).total_seconds()))
            if sampled.generated_at is not None
            else runtime.data_age(clock, sampled.source)
        )
        model_version = sampled.model_version
        ready = runtime.planner is not None
    except AQUnavailableError:
        pass
    return HealthResponse(
        status="ok" if ready else "degraded",
        version=version("hirup"),
        model_version=model_version,
        data_age_seconds=age,
        data_quality=quality,
    )
