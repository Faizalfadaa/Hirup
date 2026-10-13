import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from services.api.errors import not_implemented, problem_responses
from services.api.schemas.examples import KELURAHAN_INSIGHTS
from services.api.schemas.insights import KelurahanInsightsResponse

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get(
    "/kelurahan",
    summary="Mean PM2.5 and inequality index per kelurahan (Insight Kota tab)",
    responses={
        200: {"content": {"application/json": {"example": KELURAHAN_INSIGHTS}}},
        **problem_responses(400, 503),
    },
    openapi_extra={"x-priority": "S"},
)
async def kelurahan(
    from_: Annotated[dt.date, Query(alias="from")],
    to: Annotated[dt.date, Query()],
) -> KelurahanInsightsResponse:
    raise not_implemented("T6")
