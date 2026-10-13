import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Response
from pydantic import AwareDatetime

from services.api.errors import not_implemented, problem_responses
from services.api.schemas.aq import AqForecastResponse, AqPointResponse, DailySummaryResponse
from services.api.schemas.common import Latitude, Longitude
from services.api.schemas.examples import AQ_FORECAST, AQ_POINT, DAILY_SUMMARY

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
    lat: Annotated[Latitude, Query()], lon: Annotated[Longitude, Query()], ts: TsQuery = None
) -> AqPointResponse:
    raise not_implemented("T5")


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
    z: Annotated[int, Path(ge=0, le=20)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    ts: TsQuery = None,
) -> PngResponse:
    raise not_implemented("T5")


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
    lat: Annotated[Latitude, Query()],
    lon: Annotated[Longitude, Query()],
    hours: Annotated[int, Query(ge=1, le=24)] = 24,
) -> AqForecastResponse:
    raise not_implemented("T6")


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
