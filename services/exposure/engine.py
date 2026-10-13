"""Exposure Engine: inhaled PM2.5 dose per leg and per trip (SPEC 12.1 stage 3, 12.5, 12.6).

Pure functions, no I/O. Every constant comes from `ExposureParams`. Results are not rounded;
rounding belongs to the API layer.

    dose_leg_ug = C_leg * F_mode * VR_activity * duration_h   (P10, P50, P90 alike)
    ct_leg      = C_leg(P50) * F_mode * duration_h            (ug*h/m3)
    cig_eq      = sum(ct_leg) / ugh_m3_per_cigarette           (528)
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from services.exposure.params import ExposureParams

SECONDS_PER_HOUR = 3600.0
HOURS_PER_DAY = 24.0


class Mode(StrEnum):
    """Same values as the API contract's LegMode; exposure must not import the API."""

    WALK = "WALK"
    BICYCLE = "BICYCLE"
    WAIT = "WAIT"
    BUS = "BUS"
    SUBWAY = "SUBWAY"
    RAIL = "RAIL"
    MOTORCYCLE = "MOTORCYCLE"
    CAR = "CAR"


class WaitPlace(StrEnum):
    STOP = "stop"
    STATION = "station"


@dataclass(frozen=True, slots=True)
class Quantiles:
    p10: float
    p50: float
    p90: float

    def __add__(self, other: "Quantiles") -> "Quantiles":
        return Quantiles(self.p10 + other.p10, self.p50 + other.p50, self.p90 + other.p90)

    def scale(self, factor: float) -> "Quantiles":
        return Quantiles(self.p10 * factor, self.p50 * factor, self.p90 * factor)


ZERO = Quantiles(0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class LegInput:
    """One leg. `pm25` is the mean concentration along the leg in ug/m3 (P10/P50/P90),
    sampled every 25 m by the AQ provider at the leg's hour."""

    mode: Mode
    duration_s: float
    pm25: Quantiles
    wait_place: WaitPlace | None = None
    distance_m: float | None = None

    @classmethod
    def wait(cls, headway_s: float, pm25: Quantiles, place: WaitPlace) -> "LegInput":
        return cls(Mode.WAIT, wait_duration_s(headway_s), pm25, wait_place=place)


@dataclass(frozen=True, slots=True)
class LegExposure:
    mode: Mode
    duration_s: float
    pm25: Quantiles
    f: float
    vr_m3_h: float
    dose_ug: Quantiles
    ct_ugh_m3: float


@dataclass(frozen=True, slots=True)
class TripExposure:
    legs: tuple[LegExposure, ...]
    duration_s: float
    mean_pm25: float
    dose_ug: Quantiles
    ct_ugh_m3: float
    cig_eq: float
    daily_dose_share: float | None


@dataclass(frozen=True, slots=True)
class Assumption:
    key: str
    value: float | None
    unit: str
    source: str


def wait_duration_s(headway_s: float) -> float:
    """Expected wait for a random arrival: half the GTFS headway."""
    _check_non_negative("headway_s", headway_s)
    return headway_s / 2


def micro_environment_key(mode: Mode, wait_place: WaitPlace | None = None) -> str:
    if mode is Mode.WAIT:
        if wait_place is None:
            raise ValueError("WAIT legs need wait_place (stop or station)")
        return f"WAIT_{wait_place.value}"
    return mode.value


def factors(
    mode: Mode, params: ExposureParams, wait_place: WaitPlace | None = None
) -> tuple[float, float]:
    """(F, VR in m3/h) for the leg's micro-environment."""
    env = params.micro_environment[params.mode_mapping[micro_environment_key(mode, wait_place)]]
    return env.f, env.vr_m3_h


def leg_exposure(leg: LegInput, params: ExposureParams) -> LegExposure:
    _check_non_negative("duration_s", leg.duration_s)
    for name in ("p10", "p50", "p90"):
        _check_non_negative(f"pm25.{name}", getattr(leg.pm25, name))
    f, vr = factors(leg.mode, params, leg.wait_place)
    hours = leg.duration_s / SECONDS_PER_HOUR
    return LegExposure(
        mode=leg.mode,
        duration_s=leg.duration_s,
        pm25=leg.pm25,
        f=f,
        vr_m3_h=vr,
        dose_ug=leg.pm25.scale(f * vr * hours),
        ct_ugh_m3=leg.pm25.p50 * f * hours,
    )


def trip_exposure(
    legs: Sequence[LegInput], params: ExposureParams, daily_mean_pm25: float | None = None
) -> TripExposure:
    scored = tuple(leg_exposure(leg, params) for leg in legs)
    duration_s = sum(leg.duration_s for leg in scored)
    dose = sum((leg.dose_ug for leg in scored), ZERO)
    ct = sum(leg.ct_ugh_m3 for leg in scored)
    mean_pm25 = (
        sum(leg.pm25.p50 * leg.duration_s for leg in scored) / duration_s if duration_s else 0.0
    )
    return TripExposure(
        legs=scored,
        duration_s=duration_s,
        mean_pm25=mean_pm25,
        dose_ug=dose,
        ct_ugh_m3=ct,
        cig_eq=ct / params.ugh_m3_per_cigarette,
        daily_dose_share=daily_dose_share(dose.p50, daily_mean_pm25, params),
    )


def daily_dose_ug(daily_mean_pm25: float, params: ExposureParams) -> float | None:
    """Estimated dose for a whole day: mean PM2.5 * F_indoor * VR_daily (SPEC 12.5)."""
    _check_non_negative("daily_mean_pm25", daily_mean_pm25)
    if params.f_indoor is None:
        return None
    return daily_mean_pm25 * params.f_indoor * params.vr_m3_day


def daily_dose_share(
    trip_dose_ug: float, daily_mean_pm25: float | None, params: ExposureParams
) -> float | None:
    """Trip dose as a fraction of the estimated daily dose; None when it cannot be computed."""
    if daily_mean_pm25 is None:
        return None
    daily = daily_dose_ug(daily_mean_pm25, params)
    if not daily:
        return None
    return trip_dose_ug / daily


def daily_cig_eq(daily_mean_pm25: float, params: ExposureParams) -> float:
    """Cigarettes per day for breathing the daily mean for 24 h (Berkeley Earth rule)."""
    _check_non_negative("daily_mean_pm25", daily_mean_pm25)
    return daily_mean_pm25 * HOURS_PER_DAY / params.ugh_m3_per_cigarette


def co2_kg(mode: Mode, distance_m: float, params: ExposureParams) -> float | None:
    """CO2 for the distance: per vehicle for MOTORCYCLE/CAR, per passenger for transit."""
    factor = _table_value(params.emission_factors, mode, params)
    return None if factor is None else factor * _km(distance_m)


def vehicle_cost_idr(mode: Mode, distance_m: float, params: ExposureParams) -> float | None:
    cost = _table_value(params.fuel_cost_idr_per_km, mode, params)
    return None if cost is None else cost * _km(distance_m)


def transit_fare_idr(mode: Mode, params: ExposureParams) -> float | None:
    return _table_value(params.transit_fares_idr, mode, params)


def assumptions(mode: Mode, params: ExposureParams) -> list[Assumption]:
    """Assumptions behind a comparison card (FR-05), including the ones still missing."""
    env = params.mode_mapping[micro_environment_key(mode)]
    f, vr = factors(mode, params)
    vehicle = mode in {Mode.MOTORCYCLE, Mode.CAR}
    cost_key, cost_table, cost_unit = (
        ("fuel_cost", params.fuel_cost_idr_per_km, "IDR/km")
        if vehicle
        else ("transit_fares", params.transit_fares_idr, "IDR")
    )
    return [
        Assumption("f_mode", f, "1", params.sources[f"micro_environment.{env}.f"]),
        Assumption("vr_m3_h", vr, "m3/h", params.sources[f"micro_environment.{env}.vr_m3_h"]),
        Assumption(
            "emission_factor",
            _lookup(params.emission_factors, env),
            "kg/km" if vehicle else "kg/passenger-km",
            params.sources["emission_factors"],
        ),
        Assumption(cost_key, _lookup(cost_table, env), cost_unit, params.sources[cost_key]),
    ]


def _table_value(
    table: Mapping[str, float] | None, mode: Mode, params: ExposureParams
) -> float | None:
    return _lookup(table, params.mode_mapping[micro_environment_key(mode)])


def _lookup(table: Mapping[str, float] | None, key: str) -> float | None:
    return None if table is None else table.get(key)


def _km(distance_m: float) -> float:
    _check_non_negative("distance_m", distance_m)
    return distance_m / 1000


def _check_non_negative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number, got {value!r}")
