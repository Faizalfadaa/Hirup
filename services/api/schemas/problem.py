"""RFC 9457 Problem Details. `type` is a relative URI reference (a slug)."""

from enum import StrEnum

from pydantic import Field

from services.api.schemas.common import ContractModel

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemType(StrEnum):
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    OUT_OF_SERVICE_AREA = "out_of_service_area"
    RATE_LIMITED = "rate_limited"
    DATA_UNAVAILABLE = "data_unavailable"
    NOT_IMPLEMENTED = "not_implemented"
    INTERNAL_ERROR = "internal_error"


class Problem(ContractModel):
    type: ProblemType
    title: str
    status: int = Field(ge=400, le=599)
    detail: str | None = None
    instance: str | None = None
    request_id: str
