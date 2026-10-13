"""City insight contract: GET /v1/insights/kelurahan (FR-30, FR-31)."""

import datetime as dt

from pydantic import Field

from services.api.schemas.common import ContractModel, DataQuality, Pm25


class KelurahanInsight(ContractModel):
    kelurahan_id: str = Field(description="Joins to the static kelurahan boundary GeoJSON")
    name: str
    kecamatan: str
    mean_pm25: Pm25
    inequality_index: float | None = Field(default=None, ge=0, le=1)
    priority_rank: int | None = Field(default=None, ge=1)


class KelurahanInsightsResponse(ContractModel):
    from_: dt.date = Field(alias="from")
    to: dt.date
    boundaries_version: str
    items: list[KelurahanInsight]
    data_quality: DataQuality
