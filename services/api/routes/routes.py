from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Query, Request
from pydantic import AwareDatetime

from services.api.dependencies import get_runtime, unavailable
from services.api.errors import problem_responses
from services.api.schemas.common import DataQuality, Latitude, Longitude, Sensitivity
from services.api.schemas.examples import DEPARTURE_ADVICE, PLAN_REQUEST, PLAN_RESPONSE
from services.api.schemas.routes import (
    DepartureAdviceResponse,
    DepartureSlot,
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
        result = await runtime.plan(query)
    except (AQUnavailableError, OutOfServiceAreaError) as exc:
        raise unavailable(exc) from None
    body_response = response(
        result,
        runtime.params,
        request.state.request_id,
        body.profile.sensitivity,
        body.include_comparison,
    )
    if runtime.plan_cache is not None:
        body_response.disclaimer += (
            " Lokasi awal dan akhir rute diperkirakan pada sel 100 m; "
            "periksa akses jalan dari lokasi Anda."
        )
    return body_response


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
    request: Request,
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
    runtime = get_runtime(request)
    origin, destination = Point(origin_lon, origin_lat), Point(destination_lon, destination_lat)
    if not runtime.aq.bounds.contains(origin) or not runtime.aq.bounds.contains(destination):
        raise unavailable(OutOfServiceAreaError())
    if runtime.advice is None:
        raise unavailable(AQUnavailableError())
    anchor = (around or datetime.now(ZoneInfo("Asia/Jakarta"))).astimezone(ZoneInfo("Asia/Jakarta"))
    try:
        advice = await runtime.advice.advise(
            DomainQuery(origin, destination, anchor, mode.value, sensitivity.value)
        )
    except (AQUnavailableError, OutOfServiceAreaError) as exc:
        raise unavailable(exc) from None
    return DepartureAdviceResponse(
        requested_depart_at=anchor,
        sensitivity=sensitivity,
        mode=mode,
        slots=[
            DepartureSlot(
                depart_at=slot.estimate.depart_at,
                duration_s=slot.estimate.duration_s,
                dose_ug=slot.estimate.dose.p50,
                dose_ug_p10=slot.estimate.dose.p10,
                dose_ug_p90=slot.estimate.dose.p90,
                delta_dose_pct=slot.delta_dose_pct,
                delta_duration_s=slot.delta_duration_s,
            )
            for slot in advice.slots
        ],
        best_slot=advice.best_slot,
        data_quality=DataQuality(advice.data_quality),
    )
