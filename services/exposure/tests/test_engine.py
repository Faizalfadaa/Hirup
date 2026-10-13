"""Hand-computed checks. F and VR come from contracts/exposure_params.yaml:
walk 1.15/1.2, wait_station 0.65/0.6, wait_stop 1.2/0.6, rail 0.55/0.5,
motorcycle 1.3/0.6, car 0.45/0.5; 528 ug*h/m3 per cigarette; 16 m3/day.
"""

import dataclasses
import math

import pytest

from services.exposure.engine import (
    LegInput,
    Mode,
    Quantiles,
    WaitPlace,
    assumptions,
    co2_kg,
    daily_cig_eq,
    daily_dose_share,
    daily_dose_ug,
    factors,
    leg_exposure,
    transit_fare_idr,
    trip_exposure,
    vehicle_cost_idr,
    wait_duration_s,
)
from services.exposure.params import ExposureParams


def flat(c: float) -> Quantiles:
    return Quantiles(c, c, c)


@pytest.fixture
def filled(params: ExposureParams) -> ExposureParams:
    """Contract params plus made-up optional values, only to exercise the arithmetic."""
    return dataclasses.replace(
        params,
        f_indoor=0.5,
        emission_factors={"motorcycle": 0.1, "car": 0.2, "rail": 0.05},
        fuel_cost_idr_per_km={"motorcycle": 300.0, "car": 1000.0},
        transit_fares_idr={"rail": 3000.0},
    )


def test_spec_12_5_motorcycle_example(params: ExposureParams) -> None:
    # 60 ug/m3 x 1.3 x 0.6 m3/h x 50/60 h = 39.0 ug; 60 x 1.3 x 50/60 / 528 = 0.1231 cig
    trip = trip_exposure([LegInput(Mode.MOTORCYCLE, 50 * 60, flat(60))], params)

    assert trip.dose_ug.p50 == pytest.approx(39.0)
    assert trip.ct_ugh_m3 == pytest.approx(65.0)
    assert trip.cig_eq == pytest.approx(0.1231, abs=1e-4)
    assert round(trip.cig_eq, 2) == 0.12


def test_spec_13_2_fastest_option(params: ExposureParams) -> None:
    legs = [
        LegInput(Mode.WALK, 420, Quantiles(45, 61, 83)),
        LegInput.wait(300, Quantiles(40, 55, 75), WaitPlace.STATION),
        LegInput(Mode.SUBWAY, 1500, Quantiles(37, 50, 68)),
        LegInput(Mode.WALK, 240, Quantiles(43, 58, 79)),
    ]

    trip = trip_exposure(legs, params)

    # 61x1.15x1.2x420/3600 = 9.821; 55x0.65x0.6x150/3600 = 0.894;
    # 50x0.55x0.5x1500/3600 = 5.729; 58x1.15x1.2x240/3600 = 5.336
    assert [leg.dose_ug.p50 for leg in trip.legs] == pytest.approx(
        [9.821, 0.894, 5.729, 5.336], abs=1e-3
    )
    assert trip.duration_s == 2310
    assert trip.dose_ug.p50 == pytest.approx(21.780, abs=1e-3)
    assert trip.dose_ug.p10 == pytest.approx(16.091, abs=1e-3)
    assert trip.dose_ug.p90 == pytest.approx(29.641, abs=1e-3)
    # CT 8.184 + 1.490 + 11.458 + 4.447 = 25.579; 25.6 / 528 = 0.048
    assert trip.ct_ugh_m3 == pytest.approx(25.579, abs=1e-3)
    assert round(trip.cig_eq, 2) == 0.05
    # (61x420 + 55x150 + 50x1500 + 58x240) / 2310 = 53.16
    assert trip.mean_pm25 == pytest.approx(53.16, abs=1e-2)


def test_wait_leg_uses_half_headway_and_place_factor(params: ExposureParams) -> None:
    station = leg_exposure(LegInput.wait(300, flat(50), WaitPlace.STATION), params)
    stop = leg_exposure(LegInput.wait(300, flat(50), WaitPlace.STOP), params)

    assert wait_duration_s(300) == 150
    assert station.duration_s == stop.duration_s == 150
    assert (station.f, station.vr_m3_h) == (0.65, 0.6)
    assert (stop.f, stop.vr_m3_h) == (1.2, 0.6)
    # 50 x 1.2 x 0.6 x 150/3600 = 1.5 ug at a kerbside stop
    assert stop.dose_ug.p50 == pytest.approx(1.5)


def test_wait_leg_without_place_fails(params: ExposureParams) -> None:
    with pytest.raises(ValueError, match="wait_place"):
        leg_exposure(LegInput(Mode.WAIT, 150, flat(50)), params)


@pytest.mark.parametrize(
    ("mode", "f", "vr"),
    [
        (Mode.WALK, 1.15, 1.2),
        (Mode.BICYCLE, 1.15, 2.0),
        (Mode.BUS, 0.65, 0.5),
        (Mode.SUBWAY, 0.55, 0.5),
        (Mode.RAIL, 0.55, 0.5),
        (Mode.MOTORCYCLE, 1.3, 0.6),
        (Mode.CAR, 0.45, 0.5),
    ],
)
def test_factors_follow_mode_mapping(
    params: ExposureParams, mode: Mode, f: float, vr: float
) -> None:
    assert factors(mode, params) == (f, vr)


def test_zero_duration_gives_zero_dose(params: ExposureParams) -> None:
    trip = trip_exposure([LegInput(Mode.WALK, 0, flat(80))], params)

    assert trip.dose_ug == Quantiles(0, 0, 0)
    assert trip.cig_eq == 0
    assert trip.mean_pm25 == 0


def test_zero_concentration_gives_zero_dose(params: ExposureParams) -> None:
    trip = trip_exposure([LegInput(Mode.BICYCLE, 1800, flat(0))], params)

    assert trip.dose_ug.p50 == 0
    assert trip.ct_ugh_m3 == 0


def test_route_without_walking(params: ExposureParams) -> None:
    # Station-to-station: one rail leg only. 40 x 0.55 x 0.5 x 0.5 h = 5.5 ug
    trip = trip_exposure([LegInput(Mode.RAIL, 1800, flat(40))], params)

    assert [leg.mode for leg in trip.legs] == [Mode.RAIL]
    assert trip.dose_ug.p50 == pytest.approx(5.5)
    assert trip.ct_ugh_m3 == pytest.approx(11.0)


def test_empty_trip(params: ExposureParams) -> None:
    trip = trip_exposure([], params)

    assert trip.legs == ()
    assert trip.duration_s == 0
    assert trip.dose_ug == Quantiles(0, 0, 0)
    assert trip.daily_dose_share is None


@pytest.mark.parametrize(
    "leg",
    [
        LegInput(Mode.WALK, -1, flat(50)),
        LegInput(Mode.WALK, 60, Quantiles(-1, 50, 60)),
        LegInput(Mode.WALK, math.inf, flat(50)),
        LegInput(Mode.WALK, 60, flat(math.nan)),
    ],
)
def test_invalid_leg_input_fails(params: ExposureParams, leg: LegInput) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        leg_exposure(leg, params)


def test_negative_headway_fails() -> None:
    with pytest.raises(ValueError, match="headway_s"):
        wait_duration_s(-10)


def test_daily_share_is_none_while_f_indoor_unverified(params: ExposureParams) -> None:
    trip = trip_exposure([LegInput(Mode.WALK, 600, flat(50))], params, daily_mean_pm25=50)

    assert params.f_indoor is None
    assert trip.daily_dose_share is None
    assert daily_dose_ug(50, params) is None


def test_daily_share_with_f_indoor(filled: ExposureParams) -> None:
    # daily dose = 50 x 0.5 x 16 = 400 ug; trip 50 x 1.15 x 1.2 x 0.5 h = 34.5 ug -> 8.625 %
    trip = trip_exposure([LegInput(Mode.WALK, 1800, flat(50))], filled, daily_mean_pm25=50)

    assert daily_dose_ug(50, filled) == pytest.approx(400)
    assert trip.daily_dose_share == pytest.approx(0.08625)


def test_daily_share_edge_cases(filled: ExposureParams) -> None:
    assert daily_dose_share(10, None, filled) is None
    assert daily_dose_share(10, 0, filled) is None


def test_daily_cigarettes(params: ExposureParams) -> None:
    # SPEC 12.5: 50 ug/m3 for a day -> 50 x 24 / 528 = 2.27 cigarettes; 22 ug/m3 -> 1
    assert daily_cig_eq(50, params) == pytest.approx(2.2727, abs=1e-4)
    assert daily_cig_eq(22, params) == pytest.approx(1.0)


def test_co2_and_cost_are_none_without_factors(params: ExposureParams) -> None:
    assert co2_kg(Mode.CAR, 10_000, params) is None
    assert vehicle_cost_idr(Mode.MOTORCYCLE, 10_000, params) is None
    assert transit_fare_idr(Mode.SUBWAY, params) is None


def test_co2_and_cost_with_factors(filled: ExposureParams) -> None:
    assert co2_kg(Mode.CAR, 12_500, filled) == pytest.approx(2.5)
    assert co2_kg(Mode.SUBWAY, 10_000, filled) == pytest.approx(0.5)
    assert co2_kg(Mode.BUS, 10_000, filled) is None
    assert vehicle_cost_idr(Mode.MOTORCYCLE, 20_000, filled) == pytest.approx(6000)
    assert transit_fare_idr(Mode.RAIL, filled) == 3000


def test_negative_distance_fails(filled: ExposureParams) -> None:
    with pytest.raises(ValueError, match="distance_m"):
        co2_kg(Mode.CAR, -1, filled)


def test_assumptions_record_missing_values(params: ExposureParams) -> None:
    items = {a.key: a for a in assumptions(Mode.MOTORCYCLE, params)}

    assert items["f_mode"].value == 1.3
    assert items["vr_m3_h"].unit == "m3/h"
    assert items["emission_factor"].value is None
    assert items["emission_factor"].source.startswith("SPEC 12.6")
    assert items["fuel_cost"].value is None


def test_assumptions_for_transit_use_fares(filled: ExposureParams) -> None:
    items = {a.key: a for a in assumptions(Mode.RAIL, filled)}

    assert items["transit_fares"].value == 3000
    assert items["emission_factor"].unit == "kg/passenger-km"
