from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from services.api.errors import REQUEST_ID_HEADER
from services.api.main import create_app
from services.api.schemas.examples import PLAN_REQUEST


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _assert_problem(resp: httpx.Response, status: int, type_: str) -> dict[str, Any]:
    assert resp.status_code == status
    assert resp.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = resp.json()
    assert body["type"] == type_
    assert body["status"] == status
    assert body["title"]
    assert body["request_id"] == resp.headers[REQUEST_ID_HEADER]
    return body


async def test_validation_error_is_400_problem(client: httpx.AsyncClient) -> None:
    bad = {**PLAN_REQUEST, "origin": {"lat": -95, "lon": 106.8}}

    resp = await client.post("/v1/routes/plan", json=bad)

    body = _assert_problem(resp, 400, "validation_error")
    assert "origin.lat" in body["detail"]


async def test_depart_at_and_arrive_by_are_exclusive(client: httpx.AsyncClient) -> None:
    bad = {**PLAN_REQUEST, "arrive_by": "2026-10-16T08:00:00+07:00"}

    resp = await client.post("/v1/routes/plan", json=bad)

    _assert_problem(resp, 400, "validation_error")


async def test_naive_datetime_is_rejected(client: httpx.AsyncClient) -> None:
    bad = {**PLAN_REQUEST, "depart_at": "2026-10-16T07:00:00"}

    resp = await client.post("/v1/routes/plan", json=bad)

    _assert_problem(resp, 400, "validation_error")


async def test_unknown_request_field_is_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.post("/v1/routes/plan", json={**PLAN_REQUEST, "speed": "fast"})

    _assert_problem(resp, 400, "validation_error")


async def test_unimplemented_endpoint_is_501_problem(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/v1/routes/departure-advice",
        params={
            "origin_lat": -6.2,
            "origin_lon": 106.8,
            "destination_lat": -6.21,
            "destination_lon": 106.81,
        },
    )

    _assert_problem(resp, 501, "not_implemented")


async def test_unknown_path_is_404_problem(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/nope")

    _assert_problem(resp, 404, "not_found")
