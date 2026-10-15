import numpy as np
import pandas as pd
import pytest

from hirup_pipelines import clean, qc

HOURS = pd.date_range("2026-10-01", periods=96, freq="h", tz="UTC", name="ts")


def stations_frame(rows):
    return pd.DataFrame(
        rows, columns=["station_id", "type", "source", "provider", "lat", "lon"]
    ).assign(name="x", active=True)


def wave(seed, n=96):
    rng = np.random.default_rng(seed)
    return 40 + 10 * np.sin(np.arange(n) / 4) + rng.normal(0, 1.5, n)


def test_range_and_flatline_flags():
    values = pd.DataFrame({"a": wave(1)}, index=HOURS)
    values.iloc[5, 0] = -3
    values.iloc[6, 0] = 1500
    values.iloc[20:27, 0] = 33.0
    assert qc.flag_range(values)["a"].sum() == 2
    flat = qc.flag_flatline(values)["a"]
    assert flat.iloc[20:27].all()
    assert flat.sum() == 7


def test_spike_is_flagged_unless_a_neighbour_confirms_it():
    stations = stations_frame(
        [
            ("a", "reference", "openaq", "p", -6.2000, 106.8000),
            ("b", "reference", "openaq", "p", -6.2050, 106.8000),  # ~550 m from a
            ("c", "reference", "openaq", "p", -6.3000, 106.9000),  # far away
        ]
    )
    values = pd.DataFrame({"a": wave(1), "b": wave(2), "c": wave(3)}, index=HOURS)
    values.loc[HOURS[60], "a"] += 150  # a alone: instrument spike
    values.loc[HOURS[80], ["a", "b"]] += 150  # a and b together: a real event
    values.loc[HOURS[70], "c"] += 150  # c has no neighbour within 3 km
    flags = qc.flag_spike(values, stations)
    assert flags.loc[HOURS[60], "a"]
    assert not flags.loc[HOURS[80], ["a", "b"]].any()
    assert flags.loc[HOURS[70], "c"]
    assert flags.to_numpy().sum() == 2


def test_only_short_inner_gaps_are_interpolated():
    values = pd.DataFrame({"a": np.arange(24.0)}, index=HOURS[:24])
    values.iloc[0, 0] = np.nan  # leading gap: no data before it
    values.iloc[5:7, 0] = np.nan  # 2 h: filled
    values.iloc[10:13, 0] = np.nan  # 3 h: left alone
    filled, mask = qc.fill_short_gaps(values)
    assert mask["a"].sum() == 2
    assert filled.iloc[5:7, 0].tolist() == [5.0, 6.0]
    assert filled.iloc[10:13, 0].isna().all()
    assert np.isnan(filled.iloc[0, 0])


def test_calibration_recovers_known_coefficients():
    rng = np.random.default_rng(7)
    n = 200
    index = pd.date_range("2026-09-01", periods=n, freq="h", tz="UTC")
    lcs = rng.uniform(10, 120, n)
    rh = rng.uniform(40, 95, n)
    ref = 0.6 * lcs - 0.1 * rh + 0.001 * lcs * rh + 4
    stations = stations_frame(
        [
            ("ref", "reference", "openaq", "gov", -6.2000, 106.8000),
            ("lcs", "lcs", "openaq", "acme", -6.2010, 106.8000),
        ]
    )
    values = pd.DataFrame({"ref": ref, "lcs": lcs}, index=index)
    humidity = pd.DataFrame({"ref": rh, "lcs": rh}, index=index)
    fitted = qc.fit_calibration(values, stations, humidity, "v-test")
    coef = fitted.coefficients["acme"]
    assert coef == pytest.approx({"a": 0.6, "b": -0.1, "c": 0.001, "d": 4.0}, abs=1e-6)
    assert fitted.apply("acme", lcs, rh) == pytest.approx(ref)
    assert fitted.apply("unknown", lcs, rh) is None
    weights = qc.sample_weights(stations, fitted)
    assert weights["ref"] > weights["lcs"]


def test_clean_merges_waqi_mirror_and_never_labels_interpolated_rows():
    stations = stations_frame(
        [
            ("openaq:1", "reference", "openaq", "gov", -6.2000, 106.8000),
            ("waqi:9", "lcs", "waqi", "waqi", -6.20001, 106.80001),  # same site
            ("openaq:2", "reference", "openaq", "gov", -6.2500, 106.8200),
        ]
    )
    base = wave(1)
    frames = []
    for station, series in (("openaq:1", base), ("waqi:9", base + 0.2), ("openaq:2", wave(5))):
        frames.append(
            pd.DataFrame(
                {
                    "station_id": station,
                    "ts": HOURS,
                    "value_raw": series,
                    "source": station.split(":")[0],
                }
            )
        )
    raw = pd.concat(frames, ignore_index=True)
    gap = (raw["station_id"] == "openaq:1") & raw["ts"].isin(HOURS[40:45])
    raw = raw[~gap]  # 5 h gap in OpenAQ that the WAQI mirror covers
    raw = raw[~((raw["station_id"] == "openaq:2") & raw["ts"].isin(HOURS[10:12]))]  # 2 h gap
    raw.loc[(raw["station_id"] == "openaq:2") & (raw["ts"] == HOURS[30]), "value_raw"] = -5.0

    result = clean.clean(raw, stations, pd.DataFrame(), "v-test")
    obs = result.observations
    assert set(obs["station_id"]) == {"openaq:1", "openaq:2"}
    merged = result.stations.set_index("station_id")["merged_into"]
    assert merged["waqi:9"] == "openaq:1"
    filled = obs[(obs["station_id"] == "openaq:1") & obs["ts"].isin(HOURS[40:45])]
    assert (filled["source"] == "waqi").all()
    assert (filled["qc_flag"] == "ok").all()
    two = obs[obs["station_id"] == "openaq:2"].set_index("ts")
    assert (two.loc[HOURS[10:12], "qc_flag"] == "interpolated").all()
    assert two.loc[HOURS[10:12], "value_raw"].isna().all()
    assert two.loc[HOURS[30], "qc_flag"] == "range"
    assert np.isnan(two.loc[HOURS[30], "value_cal"])
