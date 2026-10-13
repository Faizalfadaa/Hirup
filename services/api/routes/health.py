from importlib.metadata import version

from fastapi import APIRouter

from services.api.schemas.common import DataQuality
from services.api.schemas.examples import HEALTH
from services.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service status, model version and data age",
    responses={200: {"content": {"application/json": {"example": HEALTH}}}},
    openapi_extra={"x-priority": "M"},
)
async def health() -> HealthResponse:
    # No raster or model is loaded yet, so their version and age are unknown.
    return HealthResponse(
        status="ok",
        version=version("hirup"),
        model_version=None,
        data_age_seconds=None,
        data_quality=DataQuality.REAL,
    )
