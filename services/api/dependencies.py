from typing import cast

from fastapi import Request

from services.api.errors import ProblemError
from services.api.runtime import Runtime
from services.api.schemas.problem import ProblemType
from services.exposure.aq_provider import AQUnavailableError, OutOfServiceAreaError


def get_runtime(request: Request) -> Runtime:
    return cast(Runtime, request.app.state.runtime)


def unavailable(exc: AQUnavailableError | OutOfServiceAreaError) -> ProblemError:
    if isinstance(exc, OutOfServiceAreaError):
        return ProblemError(ProblemType.OUT_OF_SERVICE_AREA, 404, "Di luar area layanan Hirup.")
    return ProblemError(
        ProblemType.DATA_UNAVAILABLE,
        503,
        "Data rute/kualitas udara belum tersedia untuk waktu ini.",
    )
