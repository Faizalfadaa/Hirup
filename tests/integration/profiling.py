"""Opt-in local wall-time counters; nested stages overlap and must not be added."""

import threading
from contextlib import ExitStack
from time import perf_counter
from typing import Any
from unittest.mock import patch

from services.api.routes import routes
from services.routing import active_router, plan


class StageProfiler:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._times: dict[str, float] = {}

    def reset(self) -> None:
        with self._lock:
            self._times.clear()

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._times)

    def _record(self, name: str, start: float) -> None:
        with self._lock:
            self._times[name] = self._times.get(name, 0) + (perf_counter() - start) * 1000

    def sync(self, name: str, method: Any) -> Any:
        def timed(*args: Any, **kwargs: Any) -> Any:
            start = perf_counter()
            try:
                return method(*args, **kwargs)
            finally:
                self._record(name, start)

        return timed

    def async_method(self, name: str, method: Any) -> Any:
        async def timed(*args: Any, **kwargs: Any) -> Any:
            start = perf_counter()
            try:
                return await method(*args, **kwargs)
            finally:
                self._record(name, start)

        return timed

    def install(self, runtime: Any) -> ExitStack:
        stack = ExitStack()
        planner = runtime.planner
        for name in ("transit", "active", "car", "motorcycle"):
            router = getattr(planner, name)
            stack.enter_context(
                patch.object(router, "candidates", self.async_method(name, router.candidates))
            )
        for name in ("_score_many", "_optimize_many"):
            stack.enter_context(
                patch.object(planner, name, self.sync(name, getattr(planner, name)))
            )
        stack.enter_context(
            patch.object(runtime, "plan", self.async_method("domain_plan", runtime.plan))
        )
        stack.enter_context(
            patch.object(planner.aq, "sample", self.sync("aq_sample", planner.aq.sample))
        )
        for module in (plan, active_router):
            stack.enter_context(
                patch.object(
                    module, "sample_polyline", self.sync("sampling", module.sample_polyline)
                )
            )
        stack.enter_context(patch.object(routes, "response", self.sync("mapping", routes.response)))
        return stack
