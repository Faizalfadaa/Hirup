"""A small throttled HTTP client with retries. API keys are never logged."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from hirup_pipelines.settings import USER_AGENT

log = logging.getLogger(__name__)
# httpx logs full request URLs at INFO, and the WAQI token travels in the query string.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    """A request failed for good. The message never contains the URL path or query."""


class Client:
    def __init__(
        self,
        *,
        min_interval_s: float = 0.0,
        retries: int = 4,
        backoff_s: float = 2.0,
        timeout_s: float = 60.0,
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.min_interval_s = min_interval_s
        self.retries = retries
        self.backoff_s = backoff_s
        self._last = 0.0
        self._http = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": USER_AGENT, **(headers or {})},
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _wait(self) -> None:
        pause = self._last + self.min_interval_s - time.monotonic()
        if pause > 0:
            time.sleep(pause)
        self._last = time.monotonic()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        # Errors name the host only: URLs and query strings can carry tokens.
        host = httpx.URL(url).host
        error = "no attempt made"
        for attempt in range(self.retries + 1):
            self._wait()
            try:
                response = self._http.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                error = f"{type(exc).__name__} contacting {host}"
            else:
                if response.status_code < 400:
                    return response
                error = f"HTTP {response.status_code} from {host}"
                if response.status_code not in RETRY_STATUS:
                    break
            if attempt < self.retries:
                delay = min(60.0, self.backoff_s * 2.0**attempt)
                log.warning("%s; retrying in %.0fs", error, delay)
                time.sleep(delay)
        raise HttpError(error)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs).json()
