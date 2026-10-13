from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Query, Request
from pydantic import AwareDatetime

from services.api.dependencies import get_runtime, unavailable
from services.api.errors import not_implemented, problem_responses
from services.api.schemas.common import Latitude, Longitude, Sensitivity
from services.api.schemas.examples import DEPARTURE_ADVICE, PLAN_REQUEST, PLAN_RESPONSE
from services.api.schemas.routes import (
    DepartureAdviceResponse,
    PlanMode,
    PlanRequest,
    PlanResponse,
)
from services.api.serialize import response
from services.exposure.aq_provider import AQUnavailableError, OutOfServiceAreaError
from services.exposure.engine import Mode
from services.exposure.geometry import Point
from services.routing.models import Query as DomainQuery

router = APIRouter(prefix="/routes", tags=["routes"])


@router.post(
    "/plan",
    summary="Plan up to 3 labelled options plus motorcycle and car comparison",
    responses={
        200: {"content": {"application/json": {"example": PLAN_RESPONSE}}},
        **problem_responses(400, 404, 429, 503),
    },
    openapi_extra={"x-priority": "M"},
)
async def plan(
    request: Request,
    body: Annotated[
        PlanRequest,
        Body(openapi_examples={"lebak_bulus_to_sudirman": {"value": PLAN_REQUEST}}),
    ],
) -> PlanResponse:
    runtime = get_runtime(request)
    origin, destination = (
        Point(body.origin.lon, body.origin.lat),
        Point(body.destination.lon, body.destination.lat),
    )
    if not runtime.aq.bounds.contains(origin) or not runtime.aq.bounds.contains(destination):
        raise unavailable(OutOfServiceAreaError())
    if runtime.planner is None or runtime.params is None:
        raise unavailable(AQUnavailableError())
    anchor = (
        body.depart_at or body.arrive_by or datetime.now(ZoneInfo("Asia/Jakarta"))
    ).astimezone(ZoneInfo("Asia/Jakarta"))
    query = DomainQuery(
        origin,
        destination,
        anchor,
        body.mode.value,
        body.profile.sensitivity.value,
        body.arrive_by is not None,
        body.profile.max_walk_m,
        tuple(Mode(mode.value) for mode in body.profile.excluded_modes),
        body.profile.avoid_transfers,
        body.include_comparison,
    )
    try:
        result = await runtime.planner.plan(query)
    except (AQUnavailableError, OutOfServiceAreaError) as exc:
        raise unavailable(exc) from None
    return response(
        result,
        runtime.params,
        request.state.request_id,
        body.profile.sensitivity,
        body.include_comparison,
    )


@router.get(
    "/departure-advice",
    summary="Dose per 15-minute departure slot within +-90 minutes",
    responses={
        200: {"content": {"application/json": {"example": DEPARTURE_ADVICE}}},
        **problem_responses(400, 404, 429, 503),
    },
    openapi_extra={"x-priority": "S"},
)
async def departure_advice(
    origin_lat: Annotated[Latitude, Query()],
    origin_lon: Annotated[Longitude, Query()],
    destination_lat: Annotated[Latitude, Query()],
    destination_lon: Annotated[Longitude, Query()],
    around: Annotated[
        AwareDatetime | None, Query(description="Centre of the window; defaults to now")
    ] = None,
    mode: PlanMode = PlanMode.TRANSIT,
    sensitivity: Sensitivity = Sensitivity.UMUM,
) -> DepartureAdviceResponse:
    raise not_implemented("T6")
