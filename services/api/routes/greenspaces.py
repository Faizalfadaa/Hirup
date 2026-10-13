from typing import Annotated

from fastapi import APIRouter, Query

from services.api.errors import not_implemented, problem_responses
from services.api.schemas.aq import GreenSpacesResponse
from services.api.schemas.common import Latitude, Longitude
from services.api.schemas.examples import GREENSPACES

router = APIRouter(prefix="/greenspaces", tags=["greenspaces"])


@router.get(
    "/nearby",
    summary="Nearest green spaces with PM2.5 and today's best hour (Could)",
    responses={
        200: {"content": {"application/json": {"example": GREENSPACES}}},
        **problem_responses(400, 404, 503),
    },
    openapi_extra={"x-priority": "C"},
)
async def nearby(
    lat: Annotated[Latitude, Query()],
    lon: Annotated[Longitude, Query()],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> GreenSpacesResponse:
    raise not_implemented("not scheduled (Could)")
