import asyncio
import datetime as dt
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Path, Query, Request, Response
from pydantic import AwareDatetime

from services.api.dependencies import get_runtime, unavailable
from services.api.errors import ProblemError, not_implemented, problem_responses
from services.api.schemas.aq import (
    AqForecastResponse,
    AqPointResponse,
    DailySummaryResponse,
    ForecastHour,
    ForecastSource,
)
from services.api.schemas.common import DataQuality, Latitude, Longitude, Pm25Quantiles
from services.api.schemas.examples import AQ_FORECAST, AQ_POINT, DAILY_SUMMARY
from services.api.schemas.problem import ProblemType
from services.exposure.aq_provider import AQUnavailableError, OutOfServiceAreaError
from services.exposure.geometry import Point, project_points

router = APIRouter(prefix="/aq", tags=["air quality"])

DATA_AGE_HEADER: dict[str, Any] = {
    "X-Data-Age-Seconds": {
        "description": "Age of the PM2.5 raster behind this response",
        "schema": {"type": "integer", "minimum": 0},
    }
}

TsQuery = Annotated[
    AwareDatetime | None, Query(description="Time of interest; defaults to the current hour")
]


class PngResponse(Response):
    media_type = "image/png"


@router.get(
    "/point",
    summary="PM2.5 P10/P50/P90 at a point",
    responses={
        200: {
            "headers": DATA_AGE_HEADER,
            "content": {"application/json": {"example": AQ_POINT}},
        },
        **problem_responses(400, 404, 503),
    },
    openapi_extra={"x-priority": "M"},
)
async def point(
    request: Request,
    response: Response,
    lat: Annotated[Latitude, Query()],
    lon: Annotated[Longitude, Query()],
    ts: TsQuery = None,
) -> AqPointResponse:
    runtime = get_runtime(request)
    clock = ts or dt.datetime.now(ZoneInfo("Asia/Jakarta"))
    location = Point(lon, lat)
    try:
        samples = await asyncio.to_thread(runtime.aq.point, location, clock)
    except (AQUnavailableError, OutOfServiceAreaError) as exc:
        raise unavailable(exc) from None
    x, y = project_points([location])
    age = (
        max(
            0,
            round(
                (dt.datetime.now(ZoneInfo("Asia/Jakarta")) - samples.generated_at).total_seconds()
            ),
        )
        if samples.generated_at is not None
        else runtime.data_age(clock, samples.source)
    )
    response.headers["X-Data-Age-Seconds"] = str(age)
    return AqPointResponse(
        lat=lat,
        lon=lon,
        cell_id=f"{int(x[0] // 100)}:{int(y[0] // 100)}",
        valid_hour=samples.valid_hour.astimezone(ZoneInfo("Asia/Jakarta")),
        pm25=Pm25Quantiles(
            p10=float(samples.p10[0]), p50=float(samples.p50[0]), p90=float(samples.p90[0])
        ),
        ispu_category=None,
        data_quality=DataQuality(samples.data_quality),
    )


@router.get(
    "/tiles/{z}/{x}/{y}.png",
    summary="PM2.5 map tile (P50, ISPU colour scale)",
    response_class=PngResponse,
    responses={
        200: {
            "headers": DATA_AGE_HEADER,
            "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}},
        },
        **problem_responses(400, 404, 503),
    },
    openapi_extra={"x-priority": "M"},
)
async def tile(
    request: Request,
    z: Annotated[int, Path(ge=0, le=20)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    ts: TsQuery = None,
) -> PngResponse:
    runtime = get_runtime(request)
    clock = ts or dt.datetime.now(ZoneInfo("Asia/Jakarta"))
    try:
        data, quality = await asyncio.to_thread(runtime.aq.tile, z, x, y, clock)
    except (AQUnavailableError, OutOfServiceAreaError) as exc:
        raise unavailable(exc) from None
    except ValueError:
        raise ProblemError(ProblemType.VALIDATION_ERROR, 400, "Indeks tile tidak valid.") from None
    age = max(0, round((dt.datetime.now(ZoneInfo("Asia/Jakarta")) - clock).total_seconds()))
    return PngResponse(data, headers={"X-Data-Age-Seconds": str(age), "X-Data-Quality": quality})


@router.get(
    "/forecast",
    summary="Hourly PM2.5 forecast up to 24 hours",
    responses={
        200: {
            "headers": DATA_AGE_HEADER,
            "content": {"application/json": {"example": AQ_FORECAST}},
        },
        **problem_responses(400, 404, 503),
    },
    openapi_extra={"x-priority": "S"},
)
async def forecast(
    request: Request,
    response: Response,
    lat: Annotated[Latitude, Query()],
    lon: Annotated[Longitude, Query()],
    hours: Annotated[int, Query(ge=1, le=24)] = 24,
) -> AqForecastResponse:
    runtime = get_runtime(request)
    location = Point(lon, lat)
    if not runtime.aq.bounds.contains(location):
        raise unavailable(OutOfServiceAreaError())
    if runtime.forecast is None:
        raise unavailable(AQUnavailableError())
    try:
        result = await asyncio.to_thread(runtime.forecast.forecast, location, hours)
    except (AQUnavailableError, OutOfServiceAreaError) as exc:
        raise unavailable(exc) from None
    response.headers["X-Data-Age-Seconds"] = str(result.age_s)
    return AqForecastResponse(
        lat=lat,
        lon=lon,
        source=ForecastSource(result.source),
        hours=[
            ForecastHour(
                valid_hour=hour.valid_hour.astimezone(ZoneInfo("Asia/Jakarta")),
                pm25=Pm25Quantiles(p10=hour.pm25.p10, p50=hour.pm25.p50, p90=hour.pm25.p90),
            )
            for hour in result.hours
        ],
        data_quality=DataQuality(result.data_quality),
    )


@router.get(
    "/daily-summary",
    summary="Daily mean PM2.5 and cigarette equivalent for the day",
    responses={
        200: {
            "headers": DATA_AGE_HEADER,
            "content": {"application/json": {"example": DAILY_SUMMARY}},
        },
        **problem_responses(400, 404, 503),
    },
    openapi_extra={"x-priority": "S"},
)
async def daily_summary(
    lat: Annotated[Latitude, Query()],
    lon: Annotated[Longitude, Query()],
    date: Annotated[dt.date | None, Query(description="Defaults to today (WIB)")] = None,
) -> DailySummaryResponse:
    raise not_implemented("T6")
