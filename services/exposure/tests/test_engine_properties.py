import pytest
from hypothesis import given
from hypothesis import strategies as st

from services.exposure.engine import LegInput, Mode, Quantiles, leg_exposure, trip_exposure
from services.exposure.params import ExposureParams

durations = st.floats(min_value=0, max_value=4 * 3600, allow_nan=False)
concentrations = st.floats(min_value=0, max_value=500, allow_nan=False)
deltas = st.floats(min_value=0, max_value=1000, allow_nan=False)
modes = st.sampled_from([m for m in Mode if m is not Mode.WAIT])


@st.composite
def quantiles(draw: st.DrawFn) -> Quantiles:
    lo, mid, hi = sorted(draw(concentrations) for _ in range(3))
    return Quantiles(lo, mid, hi)


@st.composite
def legs(draw: st.DrawFn) -> LegInput:
    return LegInput(draw(modes), draw(durations), draw(quantiles()))


@given(mode=modes, duration=durations, extra=deltas, c=concentrations)
def test_dose_increases_with_duration(
    params: ExposureParams, mode: Mode, duration: float, extra: float, c: float
) -> None:
    short = leg_exposure(LegInput(mode, duration, Quantiles(c, c, c)), params)
    long = leg_exposure(LegInput(mode, duration + extra, Quantiles(c, c, c)), params)

    assert long.dose_ug.p50 >= short.dose_ug.p50


@given(mode=modes, duration=durations, c=concentrations, extra=deltas)
def test_dose_increases_with_concentration(
    params: ExposureParams, mode: Mode, duration: float, c: float, extra: float
) -> None:
    low = leg_exposure(LegInput(mode, duration, Quantiles(c, c, c)), params)
    high = leg_exposure(LegInput(mode, duration, Quantiles(c, c + extra, c + extra)), params)

    assert high.dose_ug.p50 >= low.dose_ug.p50


@given(leg=legs())
def test_quantile_order_is_preserved(params: ExposureParams, leg: LegInput) -> None:
    dose = leg_exposure(leg, params).dose_ug

    assert dose.p10 <= dose.p50 <= dose.p90


@given(trip_legs=st.lists(legs(), max_size=8))
def test_trip_totals_are_sums_of_legs(params: ExposureParams, trip_legs: list[LegInput]) -> None:
    trip = trip_exposure(trip_legs, params)
    scored = [leg_exposure(leg, params) for leg in trip_legs]

    assert trip.duration_s == pytest.approx(sum(leg.duration_s for leg in scored))
    for q in ("p10", "p50", "p90"):
        expected = sum(getattr(leg.dose_ug, q) for leg in scored)
        assert getattr(trip.dose_ug, q) == pytest.approx(expected)
    assert trip.ct_ugh_m3 == pytest.approx(sum(leg.ct_ugh_m3 for leg in scored))
    assert trip.cig_eq == pytest.approx(trip.ct_ugh_m3 / params.ugh_m3_per_cigarette)
