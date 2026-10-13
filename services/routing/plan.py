"""Generate, optimize and score; external clients are injected and fakeable."""

import asyncio
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Protocol, cast

import numpy as np

from services.exposure.aq_provider import (
    AQProvider,
    AQUnavailableError,
    OutOfServiceAreaError,
)
from services.exposure.engine import LegInput, Mode, WaitPlace, trip_exposure
from services.exposure.geometry import BoundingBox, Point, distance_m, hour_key, sample_polyline
from services.exposure.params import ExposureParams
from services.routing.active_router import ActiveMode, ActiveRoute, ActiveRouter, NoActiveRouteError
from services.routing.gtfs import GtfsHeadways
from services.routing.models import (
    Candidate,
    PlanResult,
    Query,
    RouteLeg,
    ScoredCandidate,
    worst_quality,
)
from services.routing.rerank import RankingParams, select


class CandidateRouter(Protocol):
    async def candidates(self, query: Query) -> tuple[Candidate, ...]: ...


class ActiveCandidates:
    def __init__(self, router: ActiveRouter) -> None:
        self.router = router

    async def candidates(self, query: Query) -> tuple[Candidate, ...]:
        modes: tuple[ActiveMode, ...] = (
            ("WALK", "BICYCLE")
            if query.mode == "all"
            else ("BICYCLE",)
            if query.mode == "bike"
            else ("WALK",)
        )
        result = []
        for mode in modes:
            if Mode(mode) in query.excluded_modes:
                continue
            try:
                anchor = query.anchor
                if query.arrive_by:
                    _, _, base_duration = await asyncio.to_thread(
                        self.router.base_path, query.origin, query.destination, mode
                    )
                    anchor -= timedelta(seconds=base_duration)
                try:
                    optimized = await asyncio.to_thread(
                        self.router.plan, query.origin, query.destination, anchor, mode
                    )
                    paths = [
                        (r.points, r.distance_m, r.duration_s, r.data_quality)
                        for r in optimized
                        if not query.arrive_by
                        or hour_key(query.anchor - timedelta(seconds=r.duration_s))
                        == hour_key(anchor)
                    ]
                    if not paths:
                        raise AQUnavailableError("Arrival estimate crosses the cached AQ hour")
                except AQUnavailableError:
                    points, distance, duration = await asyncio.to_thread(
                        self.router.base_path, query.origin, query.destination, mode
                    )
                    paths = [(points, distance, duration, "approximated")]
                for points, distance, duration, quality in paths:
                    start = (
                        query.anchor - timedelta(seconds=duration)
                        if query.arrive_by
                        else query.anchor
                    )
                    result.append(
                        Candidate(
                            (RouteLeg(Mode(mode), duration, distance, points),),
                            start,
                            quality,
                        )
                    )
            except (NoActiveRouteError, OutOfServiceAreaError):
                continue
        return tuple(result)


class Planner:
    def __init__(
        self,
        *,
        bounds: BoundingBox,
        aq: AQProvider,
        params: ExposureParams,
        ranking: dict[str, RankingParams],
        sample_spacing_m: float,
        transit: CandidateRouter,
        active: CandidateRouter,
        car: CandidateRouter,
        motorcycle: CandidateRouter,
        gtfs: GtfsHeadways | None = None,
        active_router: ActiveRouter | None = None,
        model_version: str | None = None,
    ) -> None:
        self.bounds, self.aq, self.params, self.ranking = bounds, aq, params, ranking
        self.transit, self.active, self.car, self.motorcycle = transit, active, car, motorcycle
        self.sample_spacing_m = sample_spacing_m
        self.gtfs, self.active_router, self.model_version = gtfs, active_router, model_version

    async def plan(self, query: Query) -> PlanResult:
        if not self.bounds.contains(query.origin) or not self.bounds.contains(query.destination):
            raise OutOfServiceAreaError("Origin or destination is outside the pilot service area")
        jobs = []
        if query.mode in {"transit", "all"}:
            jobs.append(self.transit.candidates(query))
        if query.mode in {"walk", "bike", "all"}:
            jobs.append(self.active.candidates(query))
        # Execute road comparisons concurrently with transit/active generation.
        road_jobs = (
            [self.motorcycle.candidates(query), self.car.candidates(query)]
            if query.include_comparison
            else []
        )
        batches = await asyncio.gather(*jobs, *road_jobs)
        main_batches = batches[: len(jobs)]
        candidates = [item for batch in main_batches for item in batch]
        prepared = []
        for candidate in candidates:
            waited = self._waits(candidate, query)
            if waited is not None:
                prepared.append(waited)
        # Expensive graph/raster work runs off the event loop, bounded to this request.
        scored = await asyncio.to_thread(self._score_many, prepared)
        # Optimization is opportunistic: no cold hourly refresh inside a request.
        if self.active_router is not None:
            optimized = await asyncio.to_thread(self._optimize_many, prepared, query)
            scored.extend(await asyncio.to_thread(self._score_many, optimized))
        options = select(scored, self.ranking[query.profile])
        if not options:
            raise AQUnavailableError("No route has both routing and current AQ coverage")
        comparisons: list[ScoredCandidate | None] = []
        for batch in batches[len(jobs) :]:
            scored_roads = await asyncio.to_thread(self._score_many, batch)
            comparisons.append(
                min(scored_roads, key=lambda item: item.candidate.duration_s)
                if scored_roads
                else None
            )
        motorcycle, car = comparisons if comparisons else (None, None)
        qualities = [option.scored.data_quality for option in options]
        qualities.extend(item.data_quality for item in comparisons if item is not None)
        return PlanResult(
            options,
            motorcycle,
            car,
            hour_key(options[0].scored.candidate.depart_at),
            options[0].scored.model_version,
            worst_quality(*qualities),
        )

    def _waits(self, candidate: Candidate, query: Query) -> Candidate | None:
        legs: list[RouteLeg] = []
        for leg in candidate.legs:
            if leg.route is not None:
                headway = leg.headway_s
                if headway is None and self.gtfs is not None and leg.trip_id and leg.stop_id:
                    headway = self.gtfs.headway(
                        leg.trip_id, leg.stop_id, leg.scheduled_start or query.anchor
                    )
                if headway is None:
                    return None  # TODO(verify): no headway; never infer one from OTP wait time.
                place = WaitPlace.STOP if leg.mode == Mode.BUS else WaitPlace.STATION
                legs.append(
                    RouteLeg(
                        Mode.WAIT,
                        headway / 2,
                        0,
                        (leg.points[0],),
                        leg.from_name,
                        leg.from_name,
                        headway_s=headway,
                        wait_place=place,
                    )
                )
            legs.append(leg)
        # Expected headway waits yield estimated timelines, not realtime boarding promises.
        duration = sum(leg.duration_s for leg in legs)
        depart = (
            query.anchor - timedelta(seconds=duration) if query.arrive_by else candidate.depart_at
        )
        return replace(candidate, legs=tuple(legs), depart_at=depart)

    def _optimize_many(self, candidates: Sequence[Candidate], query: Query) -> list[Candidate]:
        router = self.active_router
        if router is None:
            return []
        result = []
        # This memo lives only until this request finishes; detour limits remain per leg.
        paths: dict[tuple[Point, Point, datetime, Mode], tuple[ActiveRoute, ...] | None] = {}
        for candidate in candidates:
            if not any(leg.route is not None for leg in candidate.legs):
                continue
            legs = list(candidate.legs)
            clock = candidate.depart_at
            changed = False
            for index, leg in enumerate(legs):
                if leg.mode in {Mode.WALK, Mode.BICYCLE} and len(leg.points) >= 2:
                    try:
                        key = (leg.points[0], leg.points[-1], hour_key(clock), leg.mode)
                        if key not in paths:
                            try:
                                paths[key] = router.plan(
                                    leg.points[0],
                                    leg.points[-1],
                                    clock,
                                    cast(ActiveMode, leg.mode.value),
                                )
                            except (AQUnavailableError, NoActiveRouteError, OutOfServiceAreaError):
                                paths[key] = None
                        routes = paths[key]
                        if routes is None:
                            clock += timedelta(seconds=leg.duration_s)
                            continue
                        best = min(routes, key=lambda r: r.mean_pm25.p50 * r.duration_s)
                        if best.distance_m <= query.max_walk_m and (
                            best.duration_s <= leg.duration_s * (1 + router.params.max_detour_frac)
                            and best.duration_s <= leg.duration_s + router.params.max_detour_s
                        ):
                            legs[index] = replace(
                                leg,
                                points=best.points,
                                distance_m=best.distance_m,
                                duration_s=best.duration_s,
                            )
                            changed |= best.points != leg.points
                    except (AQUnavailableError, NoActiveRouteError, OutOfServiceAreaError):
                        pass
                clock += timedelta(seconds=legs[index].duration_s)
            if changed:
                duration = sum(leg.duration_s for leg in legs)
                depart = (
                    query.anchor - timedelta(seconds=duration)
                    if query.arrive_by
                    else candidate.depart_at
                )
                result.append(
                    replace(
                        candidate,
                        legs=tuple(legs),
                        depart_at=depart,
                        data_quality=worst_quality(candidate.data_quality, "approximated"),
                    )
                )
        return result

    def _score_many(self, candidates: Sequence[Candidate]) -> list[ScoredCandidate]:
        result = []
        for candidate in candidates:
            inputs: list[LegInput] = []
            segments, qualities, sources = [], [candidate.data_quality], []
            model_version = None
            clock = candidate.depart_at
            try:
                for leg in candidate.legs:
                    points = sample_polyline(leg.points, self.sample_spacing_m)
                    samples = self.aq.sample(points, clock)
                    if len(samples.p50) != len(points) or samples.valid_hour != hour_key(clock):
                        raise AQUnavailableError("AQ sample hour/count differs from route leg")
                    mean = samples.mean()
                    if not inputs:
                        model_version = samples.model_version
                    inputs.append(
                        LegInput(
                            leg.mode,
                            leg.duration_s,
                            mean,
                            wait_place=leg.wait_place,
                            distance_m=leg.distance_m,
                        )
                    )
                    # Interpolate the sampled concentration onto geometry segment midpoints.
                    cumulative = np.concatenate(
                        ([0.0], np.cumsum([distance_m(a, b) for a, b in pairwise(leg.points)]))
                    )
                    sample_positions = np.minimum(
                        np.arange(len(points)) * self.sample_spacing_m, cumulative[-1]
                    )
                    values = (
                        tuple(
                            float(v)
                            for v in np.interp(
                                (cumulative[:-1] + cumulative[1:]) / 2,
                                sample_positions,
                                samples.p50,
                            )
                        )
                        if len(leg.points) > 1
                        else ()
                    )
                    segments.append(values)
                    qualities.append(samples.data_quality)
                    sources.append(samples.source)
                    clock += timedelta(seconds=leg.duration_s)
                result.append(
                    ScoredCandidate(
                        candidate,
                        trip_exposure(inputs, self.params),
                        worst_quality(*qualities),
                        tuple(segments),
                        tuple(sources),
                        model_version,
                    )
                )
            except (AQUnavailableError, OutOfServiceAreaError):
                continue
        return result
