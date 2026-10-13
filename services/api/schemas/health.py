from typing import Literal

from pydantic import Field

from services.api.schemas.common import ContractModel, DataQuality


class HealthResponse(ContractModel):
    status: Literal["ok", "degraded"]
    version: str
    model_version: str | None
    data_age_seconds: int | None = Field(ge=0, description="Age of the latest PM2.5 raster")
    data_quality: DataQuality
