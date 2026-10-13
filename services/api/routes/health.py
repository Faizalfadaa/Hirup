from importlib.metadata import version
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["health"])


# Provisional shape. T1 moves this into services/api/schemas/ and freezes it in contracts/.
class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: Literal["ok", "degraded"]
    version: str
    model_version: str | None
    data_age_seconds: int | None


@router.get("/health")
async def health() -> HealthResponse:
    # No raster or model is loaded yet, so their version and age are unknown.
    return HealthResponse(
        status="ok",
        version=version("hirup"),
        model_version=None,
        data_age_seconds=None,
    )
