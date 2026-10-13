from collections.abc import AsyncIterator
from importlib.metadata import version

import httpx
import pytest

from services.api.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_ok_with_unknown_data_age(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/health")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "version": version("hirup"),
        "model_version": None,
        "data_age_seconds": None,
    }


async def test_unversioned_path_is_not_served(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")

    assert resp.status_code == 404
