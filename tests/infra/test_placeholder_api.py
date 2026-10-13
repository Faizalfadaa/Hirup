"""The infrastructure placeholder must never claim the product API is ready."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import HTTPServer

import pytest

from infra.scripts.placeholder_api import Handler


@pytest.fixture
def api() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_readiness_is_explicitly_a_placeholder(api: str) -> None:
    with urllib.request.urlopen(api + "/health", timeout=3) as response:
        body = json.load(response)
    assert body == {"status": "placeholder", "data_quality": "approximated"}


def test_product_request_returns_problem_without_logging_coordinates(
    api: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = urllib.request.Request(
        api + "/v1/routes/plan?origin=106.800123,-6.200456",
        data=b'{"origin": "private request"}',
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as failure:
        urllib.request.urlopen(request, timeout=3)
    response = failure.value
    assert response.code == 503
    assert response.headers["Content-Type"] == "application/problem+json"
    body = json.load(response)
    response.close()
    assert body["status"] == 503
    assert body["type"] == "about:blank"
    assert body["data_quality"] == "approximated"
    assert "106.800123" not in json.dumps(body)
    assert capsys.readouterr().err == ""


def test_repeated_post_bodies_are_consumed_without_socket_resets(api: str) -> None:
    for size in (26, 65536, 131072):
        request = urllib.request.Request(api + "/v1/routes/plan", data=b"x" * size)
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(request, timeout=3)
        response = failure.value
        assert response.code == 503
        assert json.load(response)["status"] == 503
        response.close()
