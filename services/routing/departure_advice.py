"""Bounded slot planning with pure comparisons; no persistent request data."""

import asyncio
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Protocol

from services.exposure.aq_provider import AQUnavailableError, DataQuality
from services.exposure.engine import Quantiles
from services.routing.models import PlanResult, Query, worst_quality


class SlotPlanner(Protocol):
    async def plan(self, query: Query) -> PlanResult: ...


@dataclass(frozen=True, slots=True)
class SlotEstimate:
    depart_at: datetime
    duration_s: int
    dose: Quantiles
    data_quality: DataQuality


@dataclass(frozen=True, slots=True)
class AdviceSlot:
    estimate: SlotEstimate
    delta_dose_pct: float
    delta_duration_s: int


@dataclass(frozen=True, slots=True)
class AdviceResult:
    slots: tuple[AdviceSlot, ...]
    best_slot: datetime
    data_quality: DataQuality


def compare_slots(estimates: tuple[SlotEstimate, ...], around: datetime) -> AdviceResult:
    baseline = next((slot for slot in estimates if slot.depart_at == around), None)
    expected = tuple(around + timedelta(minutes=15 * i) for i in range(-6, 7))
    if baseline is None or tuple(slot.depart_at for slot in estimates) != expected:
        raise AQUnavailableError("Advice requires complete coverage including the requested time")
    if baseline.dose.p50 == 0 and any(slot.dose.p50 > 0 for slot in estimates):
        # A percentage against zero is undefined; the frozen field cannot carry null/infinity.
        raise AQUnavailableError("Relative dose is undefined for a zero-dose baseline")
    slots = tuple(
        AdviceSlot(
            slot,
            (slot.dose.p50 / baseline.dose.p50 - 1) * 100 if baseline.dose.p50 else 0,
            slot.duration_s - baseline.duration_s,
        )
        for slot in estimates
    )
    if any(not math.isfinite(slot.delta_dose_pct) for slot in slots):
        raise AQUnavailableError("Relative dose exceeds the finite response range")
    best = min(
        estimates,
        key=lambda slot: (
            slot.dose.p50,
            slot.duration_s,
            abs((slot.depart_at - around).total_seconds()),
            slot.depart_at,
        ),
    )
    return AdviceResult(slots, best.depart_at, worst_quality(*(s.data_quality for s in estimates)))


class DepartureAdvice:
    def __init__(self, planner: SlotPlanner, *, concurrency: int = 2) -> None:
        if concurrency < 1:
            raise ValueError("Advice concurrency must be positive")
        self.planner = planner
        # Shared across concurrent advice requests to bound upstream and graph work.
        self.capacity = asyncio.Semaphore(concurrency)

    async def advise(self, query: Query) -> AdviceResult:
        if query.arrive_by:
            raise ValueError("Advice expects departure times")

        async def estimate(anchor: datetime) -> SlotEstimate:
            async with self.capacity:
                result = await self.planner.plan(
                    replace(query, anchor=anchor, include_comparison=False)
                )
            # Compare the balanced route selected by the requested sensitivity at each time.
            selected = next(item for item in result.options if "balanced" in item.labels)
            scored = selected.scored
            return SlotEstimate(
                anchor,
                round(scored.candidate.duration_s),
                scored.exposure.dose_ug,
                scored.data_quality,
            )

        anchors = tuple(query.anchor + timedelta(minutes=15 * i) for i in range(-6, 7))
        results = await asyncio.gather(*(estimate(ts) for ts in anchors), return_exceptions=True)
        estimates = []
        for result in results:
            if isinstance(result, BaseException):
                raise result
            estimates.append(result)
        return compare_slots(tuple(estimates), query.anchor)
