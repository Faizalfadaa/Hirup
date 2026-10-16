import asyncio
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query, Request

from services.api.dependencies import get_runtime, unavailable
from services.api.errors import ProblemError, problem_responses
from services.api.schemas.common import DataQuality
from services.api.schemas.examples import KELURAHAN_INSIGHTS
from services.api.schemas.insights import KelurahanInsight, KelurahanInsightsResponse
from services.api.schemas.problem import ProblemType
from services.exposure.aq_provider import AQUnavailableError

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
    request: Request,
    from_: Annotated[dt.date, Query(alias="from")],
    to: Annotated[dt.date, Query()],
) -> KelurahanInsightsResponse:
    if from_ > to:
        raise ProblemError(
            ProblemType.VALIDATION_ERROR,
            400,
            "Tanggal awal harus sebelum atau sama dengan tanggal akhir.",
        )
    runtime = get_runtime(request)
    if runtime.kelurahan is None:
        raise unavailable(AQUnavailableError())
    try:
        result = await asyncio.to_thread(runtime.kelurahan.summarize, from_, to)
    except AQUnavailableError as exc:
        raise unavailable(exc) from None
    return KelurahanInsightsResponse(
        from_=result.from_date,
        to=result.to_date,
        boundaries_version=result.boundaries_version,
        items=[
            KelurahanInsight(
                kelurahan_id=item.kelurahan_id,
                name=item.name,
                kecamatan=item.kecamatan,
                mean_pm25=item.mean_pm25,
                # TODO(verify): agree FR-31 normalization and sourced green/population inputs.
                inequality_index=None,
                priority_rank=None,
            )
            for item in result.items
        ],
        data_quality=DataQuality(result.data_quality),
    )
