"""Air quality contract: point, forecast, daily summary, green spaces."""

import datetime as dt
from enum import StrEnum

from pydantic import AwareDatetime, Field

from services.api.schemas.common import (
    ContractModel,
    DataQuality,
    IspuCategory,
    Latitude,
    Longitude,
    Pm25,
    Pm25Quantiles,
)


class AqPointResponse(ContractModel):
    lat: Latitude
    lon: Longitude
    cell_id: str = Field(description="100 m grid cell (EPSG:32748)")
    valid_hour: AwareDatetime
    pm25: Pm25Quantiles
    ispu_category: IspuCategory | None = Field(
        description="Category of pm25.p50. Null while ISPU breakpoints are unverified."
    )
    data_quality: DataQuality


class ForecastSource(StrEnum):
    MODEL_CORRECTED = "model_corrected"
    HISTORICAL_MEAN = "historical_mean"


class ForecastHour(ContractModel):
    valid_hour: AwareDatetime
    pm25: Pm25Quantiles


class AqForecastResponse(ContractModel):
    lat: Latitude
    lon: Longitude
    source: ForecastSource
    hours: list[ForecastHour] = Field(max_length=24)
    data_quality: DataQuality


class DailySummaryResponse(ContractModel):
    lat: Latitude
    lon: Longitude
    date: dt.date
    mean_pm25: Pm25
    cig_eq_day: float = Field(ge=0, description="mean_pm25 * 24 / 528")
    ispu_category: IspuCategory | None
    data_quality: DataQuality


class GreenSpace(ContractModel):
    name: str
    lat: Latitude
    lon: Longitude
    distance_m: float = Field(ge=0)
    pm25_now: Pm25
    best_hour_today: AwareDatetime | None


class GreenSpacesResponse(ContractModel):
    items: list[GreenSpace]
    data_quality: DataQuality
