"""Route planning contract: POST /v1/routes/plan and GET /v1/routes/departure-advice."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import AwareDatetime, Field, model_validator

from services.api.schemas.common import (
    ContractModel,
    DataQuality,
    Latitude,
    LatLon,
    Longitude,
    Pm25,
    Polyline6,
    RequestModel,
    Sensitivity,
)

DurationS = Annotated[int, Field(ge=0, description="Seconds")]
DoseUg = Annotated[float, Field(ge=0, description="Inhaled PM2.5 dose in ug")]
CtUghM3 = Annotated[
    float, Field(ge=0, description="Concentration-time integral sum(C * F * h) in ug*h/m3")
]


class LegMode(StrEnum):
    WALK = "WALK"
    BICYCLE = "BICYCLE"
    WAIT = "WAIT"
    BUS = "BUS"
    SUBWAY = "SUBWAY"
    RAIL = "RAIL"
    MOTORCYCLE = "MOTORCYCLE"
    CAR = "CAR"


class RouteLabel(StrEnum):
    FASTEST = "fastest"
    CLEANEST = "cleanest"
    BALANCED = "balanced"


class PlanMode(StrEnum):
    TRANSIT = "transit"
    BIKE = "bike"
    WALK = "walk"
    ALL = "all"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WaitPlace(StrEnum):
    STOP = "stop"
    STATION = "station"


# --- request -------------------------------------------------------------------------


class RouteProfile(RequestModel):
    sensitivity: Sensitivity = Sensitivity.UMUM
    max_walk_m: int = Field(default=1000, ge=100, le=3000)
    avoid_transfers: bool = Field(default=False, description="Priority S (FR-07)")
    excluded_modes: list[LegMode] = Field(default_factory=list, description="Priority S (FR-07)")


class PlanRequest(RequestModel):
    origin: LatLon
    destination: LatLon
    depart_at: AwareDatetime | None = Field(
        default=None, description="Departure time. Defaults to now when both times are absent."
    )
    arrive_by: AwareDatetime | None = Field(
        default=None, description="Arrival deadline. Mutually exclusive with depart_at."
    )
    mode: PlanMode = PlanMode.TRANSIT
    profile: RouteProfile = Field(default_factory=RouteProfile)
    include_comparison: bool = True

    @model_validator(mode="after")
    def _one_time_anchor(self) -> Self:
        if self.depart_at is not None and self.arrive_by is not None:
            raise ValueError("set depart_at or arrive_by, not both")
        return self


# --- response ------------------------------------------------------------------------


class Place(ContractModel):
    name: str
    lat: Latitude
    lon: Longitude


class TransitRoute(ContractModel):
    id: str
    short_name: str | None = None
    long_name: str | None = None
    agency: str | None = None


class Leg(ContractModel):
    mode: LegMode
    start_time: AwareDatetime
    end_time: AwareDatetime
    duration_s: DurationS
    distance_m: float | None = Field(default=None, ge=0)
    from_: Place = Field(alias="from")
    to: Place
    polyline: Polyline6 | None = None
    segments_pm25: list[Pm25] | None = Field(
        default=None, description="P50 per polyline segment for colouring (FR-04)"
    )
    mean_pm25: Pm25 = Field(description="Ambient P50 averaged along the leg (25 m samples)")
    mean_pm25_p10: Pm25
    mean_pm25_p90: Pm25
    dose_ug: DoseUg
    dose_ug_p10: DoseUg
    dose_ug_p90: DoseUg
    ct_ugh_m3: CtUghM3
    route: TransitRoute | None = Field(default=None, description="Transit legs only")
    wait_place: WaitPlace | None = Field(default=None, description="WAIT legs only")
    headway_s: int | None = Field(
        default=None, ge=0, description="WAIT legs only; duration_s = headway_s / 2"
    )


class RouteOption(ContractModel):
    option_id: str
    labels: list[RouteLabel] = Field(
        min_length=1, description="Identical options are merged into one option with labels"
    )
    depart_at: AwareDatetime
    arrive_at: AwareDatetime
    duration_s: DurationS
    transfers: int = Field(ge=0)
    distance_m: float = Field(ge=0)
    mean_pm25: Pm25 = Field(description="Duration-weighted mean of leg mean_pm25")
    dose_ug: DoseUg
    dose_ug_p10: DoseUg
    dose_ug_p90: DoseUg
    ct_ugh_m3: CtUghM3
    cig_eq: float = Field(ge=0, description="ct_ugh_m3 / 528 (cigarette equivalent)")
    daily_dose_share: float | None = Field(
        default=None,
        ge=0,
        description="Trip dose / estimated daily dose. Null while F_indoor is unverified.",
    )
    delta_vs_fastest_pct: float = Field(description="Dose change vs the fastest option, percent")
    delta_duration_vs_fastest_s: int
    exceeds_profile_threshold: bool | None = Field(
        default=None,
        description="Mean PM2.5 above the profile warning category. Null while ISPU "
        "breakpoints are unverified.",
    )
    co2_kg: float | None = Field(default=None, ge=0)
    cost_idr: int | None = Field(default=None, ge=0)
    data_quality: DataQuality
    legs: list[Leg] = Field(min_length=1)


class Assumption(ContractModel):
    key: str
    value: float | str | None
    unit: str
    source: str


class ComparisonOption(ContractModel):
    duration_s: DurationS
    distance_m: float = Field(ge=0)
    mean_pm25: Pm25
    dose_ug: DoseUg
    dose_ug_p10: DoseUg
    dose_ug_p90: DoseUg
    ct_ugh_m3: CtUghM3
    cig_eq: float = Field(ge=0)
    co2_kg: float | None = Field(default=None, ge=0)
    cost_idr: int | None = Field(default=None, ge=0)
    congestion_factor: float | None = Field(default=None, gt=0)
    polyline: Polyline6
    data_quality: DataQuality
    assumptions: list[Assumption] = Field(
        default_factory=list, description="Emission, congestion and cost assumptions (FR-05)"
    )


class Comparison(ContractModel):
    motorcycle: ComparisonOption | None
    car: ComparisonOption | None


class DataFreshness(ContractModel):
    aq_valid_hour: AwareDatetime
    model_version: str | None
    confidence: Confidence


class PlanResponse(ContractModel):
    request_id: str
    data_quality: DataQuality = Field(description="Worst data_quality among options")
    data_freshness: DataFreshness
    sensitivity: Sensitivity
    options: list[RouteOption] = Field(max_length=3)
    comparison: Comparison | None
    disclaimer: str


# --- departure advice (S) ------------------------------------------------------------


class DepartureSlot(ContractModel):
    depart_at: AwareDatetime
    duration_s: DurationS
    dose_ug: DoseUg
    dose_ug_p10: DoseUg
    dose_ug_p90: DoseUg
    delta_dose_pct: float = Field(description="Dose change vs the requested departure, percent")
    delta_duration_s: int


class DepartureAdviceResponse(ContractModel):
    requested_depart_at: AwareDatetime
    sensitivity: Sensitivity
    mode: PlanMode
    slots: list[DepartureSlot] = Field(description="15-minute slots within +-90 minutes")
    best_slot: AwareDatetime | None
    data_quality: DataQuality
