"""Domain inputs shared by routing edges and pure ranking; no API imports."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from services.exposure.aq_provider import DataQuality
from services.exposure.engine import Mode, TripExposure, WaitPlace
from services.exposure.geometry import Point

PlanMode = Literal["transit", "bike", "walk", "all"]
Profile = Literal["umum", "rentan"]


@dataclass(frozen=True, slots=True)
class Query:
    origin: Point
    destination: Point
    anchor: datetime
    mode: PlanMode = "transit"
    profile: Profile = "umum"
    arrive_by: bool = False
    max_walk_m: int = 1000
    excluded_modes: tuple[Mode, ...] = ()
    avoid_transfers: bool = False
    include_comparison: bool = True


@dataclass(frozen=True, slots=True)
class TransitInfo:
    id: str
    short_name: str | None = None
    long_name: str | None = None
    agency: str | None = None


@dataclass(frozen=True, slots=True)
class RouteLeg:
    mode: Mode
    duration_s: float
    distance_m: float
    points: tuple[Point, ...]
    from_name: str = "Asal"
    to_name: str = "Tujuan"
    route: TransitInfo | None = None
    trip_id: str | None = None
    stop_id: str | None = None
    scheduled_start: datetime | None = None
    headway_s: float | None = None
    wait_place: WaitPlace | None = None


@dataclass(frozen=True, slots=True)
class Candidate:
    legs: tuple[RouteLeg, ...]
    depart_at: datetime
    data_quality: DataQuality
    congestion_factor: float | None = None

    @property
    def duration_s(self) -> float:
        return sum(leg.duration_s for leg in self.legs)

    @property
    def distance_m(self) -> float:
        return sum(leg.distance_m for leg in self.legs)

    @property
    def transfers(self) -> int:
        return max(0, sum(leg.route is not None for leg in self.legs) - 1)


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: Candidate
    exposure: TripExposure
    data_quality: DataQuality
    # One P50 per encoded-polyline segment, not one entry per 25 m sample.
    segments_pm25: tuple[tuple[float, ...], ...]
    aq_sources: tuple[str, ...] = ()
    model_version: str | None = None


@dataclass(frozen=True, slots=True)
class Selected:
    scored: ScoredCandidate
    labels: tuple[str, ...]
    dose_delta_pct: float
    duration_delta_s: int


@dataclass(frozen=True, slots=True)
class PlanResult:
    options: tuple[Selected, ...]
    motorcycle: ScoredCandidate | None
    car: ScoredCandidate | None
    valid_hour: datetime
    model_version: str | None
    data_quality: DataQuality


def worst_quality(*qualities: DataQuality) -> DataQuality:
    return (
        "synthetic"
        if "synthetic" in qualities
        else ("approximated" if "approximated" in qualities else "real")
    )
