from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi

from services.api import errors
from services.api.routes import aq, greenspaces, health, insights, routes
from services.api.schemas.problem import Problem

CONTRACT_VERSION = "1.0.0"

_DESCRIPTION = """\
Hirup API v1. Plans multimodal trips in the Jakarta pilot area and ranks them by inhaled
PM2.5 dose. Exported from the Pydantic models in `services/api/schemas`; do not edit by hand.

Conventions: times ISO 8601 with offset (Asia/Jakarta, +07:00); coordinates WGS84;
polylines encoded with precision 6; every successful response carries `data_quality`
(real | approximated | synthetic); errors are RFC 9457 Problem Details
(`application/problem+json`). `x-priority` marks MoSCoW priority (M, S, C).
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hirup API",
        version=CONTRACT_VERSION,
        separate_input_output_schemas=False,
    )
    errors.install(app)
    v1 = APIRouter(prefix="/v1")
    for module in (routes, aq, insights, greenspaces, health):
        v1.include_router(module.router)
    app.include_router(v1)
    app.openapi = lambda: _openapi(app)  # type: ignore[method-assign]
    return app


def _openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    spec = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=_DESCRIPTION,
        routes=app.routes,
        separate_input_output_schemas=False,
    )
    spec["servers"] = [
        {"url": "http://localhost:8000", "description": "local API (make api)"},
        {"url": "http://localhost:4010", "description": "mock (make mock)"},
    ]
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    # Validation errors are returned as 400 Problem, not FastAPI's default 422.
    for path_item in spec["paths"].values():
        for operation in path_item.values():
            operation.get("responses", {}).pop("422", None)
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    schemas["Problem"] = Problem.model_json_schema(ref_template="#/components/schemas/{model}")
    schemas.update(schemas["Problem"].pop("$defs", {}))
    app.openapi_schema = spec
    return spec


app = create_app()
