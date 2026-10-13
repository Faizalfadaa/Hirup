"""RFC 9457 Problem Details for every error response."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.api.schemas.examples import PROBLEMS
from services.api.schemas.problem import PROBLEM_MEDIA_TYPE, Problem, ProblemType

log = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

_TITLES: dict[ProblemType, str] = {
    ProblemType.VALIDATION_ERROR: "Permintaan tidak valid",
    ProblemType.NOT_FOUND: "Tidak ditemukan",
    ProblemType.OUT_OF_SERVICE_AREA: "Di luar area layanan",
    ProblemType.RATE_LIMITED: "Terlalu banyak permintaan",
    ProblemType.DATA_UNAVAILABLE: "Data kualitas udara belum tersedia",
    ProblemType.NOT_IMPLEMENTED: "Belum tersedia",
    ProblemType.INTERNAL_ERROR: "Terjadi kesalahan pada server",
}

_TYPE_BY_STATUS: dict[int, ProblemType] = {
    400: ProblemType.VALIDATION_ERROR,
    404: ProblemType.NOT_FOUND,
    429: ProblemType.RATE_LIMITED,
    501: ProblemType.NOT_IMPLEMENTED,
    503: ProblemType.DATA_UNAVAILABLE,
}


class ProblemError(Exception):
    """Raise from routers to return a Problem with a specific type."""

    def __init__(self, type_: ProblemType, status: int, detail: str | None = None) -> None:
        super().__init__(detail or type_.value)
        self.type = type_
        self.status = status
        self.detail = detail


def not_implemented(task: str) -> ProblemError:
    return ProblemError(ProblemType.NOT_IMPLEMENTED, 501, f"Endpoint dijadwalkan di {task}.")


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) else _new_request_id()


def _new_request_id() -> str:
    return f"rq_{uuid.uuid4().hex[:12]}"


def problem_response(
    request: Request, type_: ProblemType, status: int, detail: str | None = None
) -> JSONResponse:
    body = Problem(
        type=type_,
        title=_TITLES[type_],
        status=status,
        detail=detail,
        instance=request.url.path,
        request_id=_request_id(request),
    )
    return JSONResponse(
        body.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
    )


def _validation_detail(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{loc}: {err.get('msg', 'invalid')}" if loc else str(err.get("msg")))
    return "; ".join(parts)


async def _on_problem(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ProblemError)
    return problem_response(request, exc.type, exc.status, exc.detail)


async def _on_validation(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    return problem_response(request, ProblemType.VALIDATION_ERROR, 400, _validation_detail(exc))


async def _on_http(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    type_ = _TYPE_BY_STATUS.get(exc.status_code, ProblemType.INTERNAL_ERROR)
    detail = exc.detail if isinstance(exc.detail, str) else None
    return problem_response(request, type_, exc.status_code, detail)


async def _on_unhandled(request: Request, exc: Exception) -> Response:
    log.exception("unhandled error", exc_info=exc)
    return problem_response(request, ProblemType.INTERNAL_ERROR, 500)


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _assign_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = _new_request_id()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    app.add_exception_handler(ProblemError, _on_problem)
    app.add_exception_handler(RequestValidationError, _on_validation)
    app.add_exception_handler(StarletteHTTPException, _on_http)
    app.add_exception_handler(Exception, _on_unhandled)


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entries for Problem errors, with examples."""
    return {
        status: {
            "description": PROBLEMS[status]["title"],
            "content": {
                PROBLEM_MEDIA_TYPE: {
                    "schema": {"$ref": "#/components/schemas/Problem"},
                    "example": PROBLEMS[status],
                }
            },
        }
        for status in statuses
    }
