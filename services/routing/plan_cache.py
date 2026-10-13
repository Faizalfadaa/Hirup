"""Bounded cache of plans for public grid representatives, never exact user endpoints."""

import asyncio
import math
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from time import monotonic
from typing import Protocol

from services.exposure.aq_provider import AQUnavailableError, OutOfServiceAreaError
from services.exposure.geometry import BoundingBox, project_points, unproject
from services.routing.models import PlanResult, Query, ScoredCandidate, worst_quality


class PlanProvider(Protocol):
    async def plan(self, query: Query) -> PlanResult: ...


@dataclass(frozen=True, slots=True)
class CacheKey:
    origin_cell: tuple[int, int]
    destination_cell: tuple[int, int]
    slot: datetime
    anchor: datetime
    mode: str
    profile: str
    arrive_by: bool
    max_walk_m: int
    excluded_modes: tuple[str, ...]
    avoid_transfers: bool
    include_comparison: bool


@dataclass(frozen=True, slots=True)
class CacheEntry:
    result: PlanResult
    expires_at: float


def approximate(result: PlanResult) -> PlanResult:
    def scored(item: ScoredCandidate) -> ScoredCandidate:
        return replace(
            item,
            candidate=replace(
                item.candidate,
                data_quality=worst_quality(item.candidate.data_quality, "approximated"),
            ),
            data_quality=worst_quality(item.data_quality, "approximated"),
        )

    return replace(
        result,
        options=tuple(replace(option, scored=scored(option.scored)) for option in result.options),
        motorcycle=scored(result.motorcycle) if result.motorcycle is not None else None,
        car=scored(result.car) if result.car is not None else None,
        data_quality=worst_quality(result.data_quality, "approximated"),
    )


class PlanCache:
    def __init__(
        self,
        planner: PlanProvider,
        bounds: BoundingBox,
        *,
        ttl_s: float = 600,
        capacity: int = 128,
        max_in_flight: int = 16,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if not math.isfinite(ttl_s) or ttl_s <= 0 or capacity < 1 or max_in_flight < 1:
            raise ValueError("Cache TTL and capacity must be positive and finite")
        self.planner, self.bounds = planner, bounds
        self.ttl_s, self.capacity, self.clock = ttl_s, capacity, clock
        self.max_in_flight = max_in_flight
        self._entries: OrderedDict[CacheKey, CacheEntry] = OrderedDict()
        self._flights: dict[tuple[int, CacheKey], asyncio.Task[PlanResult]] = {}
        self._lock = threading.RLock()
        self._generation = 0
        self._hits = self._misses = self._joins = 0

    def normalize(self, query: Query) -> tuple[CacheKey, Query]:
        if not self.bounds.contains(query.origin) or not self.bounds.contains(query.destination):
            raise OutOfServiceAreaError("Origin or destination is outside the pilot area")
        x, y = project_points((query.origin, query.destination))
        cells = tuple(
            (math.floor(float(a) / 100), math.floor(float(b) / 100))
            for a, b in zip(x, y, strict=True)
        )
        representatives = tuple(
            self.bounds.clamp(unproject((a + 0.5) * 100, (b + 0.5) * 100)) for a, b in cells
        )
        if query.anchor.utcoffset() is None:
            raise ValueError("Cache timestamps must include a timezone")
        anchor = query.anchor.astimezone(UTC)
        slot = anchor.replace(minute=anchor.minute // 15 * 15, second=0, microsecond=0)
        excluded = tuple(sorted(set(mode.value for mode in query.excluded_modes)))
        key = CacheKey(
            cells[0],
            cells[1],
            slot,
            anchor,
            query.mode,
            query.profile,
            query.arrive_by,
            query.max_walk_m,
            excluded,
            query.avoid_transfers,
            query.include_comparison,
        )
        canonical = replace(
            query,
            origin=representatives[0],
            destination=representatives[1],
            anchor=anchor,
        )
        return key, canonical

    def invalidate(self) -> None:
        # Refresh runs in a worker thread; versioned flights must not republish stale results.
        with self._lock:
            self._generation += 1
            self._entries.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "joins": self._joins,
                "entries": len(self._entries),
                "in_flight": len(self._flights),
            }

    async def _compute(self, generation: int, key: CacheKey, canonical: Query) -> PlanResult:
        result = approximate(await self.planner.plan(canonical))
        with self._lock:
            if generation == self._generation:
                now = self.clock()
                for old_key in tuple(self._entries):
                    if self._entries[old_key].expires_at <= now:
                        del self._entries[old_key]
                self._entries[key] = CacheEntry(result, now + self.ttl_s)
                self._entries.move_to_end(key)
                while len(self._entries) > self.capacity:
                    self._entries.popitem(last=False)
        return result

    def _finished(self, flight: tuple[int, CacheKey], task: asyncio.Task[PlanResult]) -> None:
        with self._lock:
            if self._flights.get(flight) is task:
                self._flights.pop(flight)
        if not task.cancelled():
            # Retrieve failures even if all HTTP callers disconnected; no request details logged.
            task.exception()

    async def plan(self, query: Query) -> PlanResult:
        key, canonical = self.normalize(query)
        for _ in range(2):
            with self._lock:
                generation = self._generation
                entry = self._entries.get(key)
                if entry is not None and entry.expires_at > self.clock():
                    self._entries.move_to_end(key)
                    self._hits += 1
                    return entry.result
                self._entries.pop(key, None)
                flight = (generation, key)
                task = self._flights.get(flight)
                if task is not None and task.done():
                    self._flights.pop(flight, None)
                    task = None
                if task is None:
                    if len(self._flights) >= self.max_in_flight:
                        raise AQUnavailableError("Plan cache has reached its in-flight capacity")
                    self._misses += 1
                    # Only the canonical query crosses into a shared task or retained state.
                    task = asyncio.create_task(self._compute(generation, key, canonical))
                    self._flights[flight] = task
                    task.add_done_callback(partial(self._finished, flight))
                else:
                    self._joins += 1
            result = await asyncio.shield(task)
            with self._lock:
                if generation == self._generation:
                    return result
        raise AQUnavailableError("AQ publication changed repeatedly during planning")
