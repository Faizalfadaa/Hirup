from typing import Annotated

from fastapi import APIRouter, Body, Query
from pydantic import AwareDatetime

from services.api.errors import not_implemented, problem_responses
from services.api.schemas.common import Latitude, Longitude, Sensitivity
from services.api.schemas.examples import DEPARTURE_ADVICE, PLAN_REQUEST, PLAN_RESPONSE
from services.api.schemas.routes import (
    DepartureAdviceResponse,
    PlanMode,
    PlanRequest,
    PlanResponse,
)

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
    body: Annotated[
        PlanRequest,
        Body(openapi_examples={"lebak_bulus_to_sudirman": {"value": PLAN_REQUEST}}),
    ],
) -> PlanResponse:
    raise not_implemented("T5")


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
