import json
from datetime import UTC, datetime

import httpx
import pandas as pd
import pytest

from hirup_pipelines import paths, schemas, store, tasks
from hirup_pipelines.http import Client, HttpError
from hirup_pipelines.ingest import openaq, openmeteo, waqi
from hirup_pipelines.settings import pilot_bbox


def mock_client(handler, **kwargs):
    return Client(transport=httpx.MockTransport(handler), backoff_s=0.0, **kwargs)


def test_http_errors_never_leak_the_query_string():
    def handler(request):
        return httpx.Response(403)

    with mock_client(handler) as http, pytest.raises(HttpError) as info:
        http.get_json("https://api.example.org/feed/", params={"token": "s3cret"})
    assert "s3cret" not in str(info.value)
    assert "api.example.org" in str(info.value)


def test_http_retries_transient_failures():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"ok": True})

    with mock_client(handler) as http:
        assert http.get_json("https://api.example.org/x") == {"ok": True}
    assert len(calls) == 3


def test_openaq_stations_and_hours():
    def handler(request):
        assert request.headers["X-API-Key"] == "k"
        if request.url.path.endswith("/locations"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 11,
                            "name": "Embassy",
                            "isMonitor": True,
                            "isMobile": False,
                            "provider": {"name": "AirNow"},
                            "coordinates": {"latitude": -6.18, "longitude": 106.83},
                            "sensors": [
                                {"id": 500, "parameter": {"name": "o3"}},
                                {"id": 501, "parameter": {"name": "pm25"}},
                            ],
                        },
                        {
                            "id": 12,
                            "name": "No PM",
                            "coordinates": {"latitude": -6.2, "longitude": 106.8},
                            "sensors": [{"id": 502, "parameter": {"name": "no2"}}],
                        },
                    ]
                },
            )
        assert request.url.path.endswith("/sensors/501/hours")
        return httpx.Response(
            200,
            json={
                "results": [
                    {"value": 41.5, "period": {"datetimeFrom": {"utc": "2026-10-13T00:00:00Z"}}},
                    {"value": 39.0, "period": {"datetimeFrom": {"utc": "2026-10-13T01:00:00Z"}}},
                ]
            },
        )

    with mock_client(handler, headers={"X-API-Key": "k"}) as http:
        stations = openaq.fetch_stations(http, pilot_bbox())
        assert stations["station_id"].tolist() == ["openaq:11"]
        assert stations["type"].item() == "reference"
        assert stations["sensor_id"].item() == 501
        schemas.validate(stations, schemas.STATIONS)
        hours = openaq.fetch_hours(
            http, "openaq:11", 501, datetime(2026, 10, 13, tzinfo=UTC), datetime.now(UTC)
        )
    assert hours["value_raw"].tolist() == [41.5, 39.0]
    schemas.validate(hours, schemas.RAW_OBSERVATIONS)


def test_waqi_aqi_is_converted_to_concentration():
    assert waqi.aqi_to_pm25(0) == 0
    assert waqi.aqi_to_pm25(50) == pytest.approx(12.0)
    assert waqi.aqi_to_pm25(100) == pytest.approx(35.4)
    assert waqi.aqi_to_pm25(150) == pytest.approx(55.4)
    assert waqi.aqi_to_pm25(175) == pytest.approx(55.5 + 24 / 49 * (150.4 - 55.5))
    assert pd.isna(waqi.aqi_to_pm25(-1))
    assert pd.isna(waqi.aqi_to_pm25(900))


def test_waqi_latest_reading():
    def handler(request):
        assert request.url.params["token"] == "t"
        if "map/bounds" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "data": [{"uid": 7, "lat": -6.2, "lon": 106.8, "station": {"name": "A"}}],
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "iaqi": {"pm25": {"v": 100}},
                    "time": {"iso": "2026-10-13T20:25:00+07:00"},
                },
            },
        )

    with mock_client(handler) as http:
        stations = waqi.fetch_stations(http, pilot_bbox(), token="t")
        latest = waqi.fetch_latest(http, stations["station_id"].tolist(), token="t")
    assert latest["ts"].item() == pd.Timestamp("2026-10-13T13:00:00Z")
    assert latest["value_raw"].item() == pytest.approx(35.4)
    schemas.validate(latest, schemas.RAW_OBSERVATIONS)


def test_waqi_error_status_raises():
    def handler(request):
        return httpx.Response(200, json={"status": "error", "data": "Invalid key"})

    with mock_client(handler) as http, pytest.raises(RuntimeError, match="status"):
        waqi.fetch_stations(http, pilot_bbox(), token="bad")


def test_open_meteo_weather_and_cams_parse_multi_point_responses():
    points = openmeteo.lattice(pilot_bbox())
    assert len(points) == 6
    times = ["2026-10-13T00:00", "2026-10-13T01:00"]

    def handler(request):
        assert len(request.url.params["latitude"].split(",")) == 6
        if "air-quality" in request.url.host:
            hourly = {"time": times, "pm2_5": [50.0, 60.0]}
        else:
            hourly = {
                "time": times,
                "temperature_2m": [27.0, 26.5],
                "relative_humidity_2m": [80, 85],
                "precipitation": [0.0, 1.2],
                "wind_speed_10m": [2.0, 2.0],
                "wind_direction_10m": [90, 180],  # from east, then from south
                "boundary_layer_height": [300.0, 250.0],
            }
        return httpx.Response(200, content=json.dumps([{"hourly": hourly}] * 6))

    with mock_client(handler) as http:
        weather = openmeteo.fetch_weather(http, points, past_days=1, forecast_days=1)
        cams = openmeteo.fetch_cams(http, points, past_days=1, forecast_days=1)
    schemas.validate(weather, schemas.WEATHER_HOURLY)
    schemas.validate(cams, schemas.CAMS_HOURLY)
    first = weather.iloc[0]
    assert first["wind_u"] == pytest.approx(-2.0)  # wind from the east blows westward
    assert first["wind_v"] == pytest.approx(0.0, abs=1e-9)
    assert weather.iloc[1]["wind_v"] == pytest.approx(2.0)
    assert cams["pm25_cams"].tolist()[:2] == [50.0, 60.0]


def test_failed_step_is_logged_and_gate_g0_reports_failure(isolated_data_dir):
    with pytest.raises(RuntimeError, match="No stations found"):
        tasks.discover_stations()
    runs = pd.read_parquet(isolated_data_dir / "ingest_runs.parquet")
    assert runs["status"].tolist() == ["failed"]
    assert "No stations found" in runs["error"].item()
    report = tasks.gate_g0()
    assert report["passed"] is False
    assert report["stations_qualifying"] == 0


def test_gate_g0_counts_only_stations_with_a_week_of_ok_hours():
    hours = pd.date_range("2026-10-01", periods=200, freq="h", tz="UTC")
    ids = [f"openaq:{i}" for i in range(11)]
    stations = pd.DataFrame(
        {
            "station_id": ids,
            "name": "s",
            "type": "reference",
            "source": "openaq",
            "provider": "gov",
            "lat": -6.2,
            "lon": 106.8,
            "active": True,
            "merged_into": pd.Series([None] * 11, dtype="string"),
        }
    )
    store.write_parquet(stations, paths.stations())
    obs = pd.concat(
        [
            pd.DataFrame(
                {
                    "station_id": station,
                    "ts": hours[: 200 if i < 10 else 100],  # the 11th has too few hours
                    "value_raw": 40.0,
                    "value_cal": 40.0,
                    "qc_flag": "ok",
                    "source": "openaq",
                }
            )
            for i, station in enumerate(ids)
        ]
    )
    store.write_daily(obs, paths.observations(), ["station_id", "ts"], replace=True)
    report = tasks.gate_g0()
    assert report["stations_qualifying"] == 10
    assert report["passed"] is True
    assert len(store.read_daily(paths.observations(), start=hours[190].to_pydatetime())) == 10 * 10


def test_openaq_ingest_resumes_in_chunks_and_skips_a_failing_sensor(monkeypatch):
    stations = pd.DataFrame(
        {
            "station_id": ["openaq:1", "openaq:2"],
            "name": "s",
            "type": "reference",
            "source": "openaq",
            "provider": "gov",
            "lat": -6.2,
            "lon": 106.8,
            "active": True,
            "sensor_id": [10, 20],
            "first_seen": None,
            "last_seen": None,
        }
    )
    store.write_parquet(stations, paths.raw_stations())
    calls = []

    def fake_fetch(http, station_id, sensor_id, start, end):
        calls.append((station_id, start, end))
        if sensor_id == 20:
            raise HttpError("HTTP 408 from api.openaq.org")
        hour = pd.Timestamp(end).floor("h") - pd.Timedelta(hours=1)
        return pd.DataFrame(
            {"station_id": [station_id], "ts": [hour], "value_raw": [30.0], "source": ["openaq"]}
        )

    monkeypatch.setenv("OPENAQ_API_KEY", "k")
    monkeypatch.setattr(openaq, "fetch_hours", fake_fetch)
    assert tasks.ingest_openaq(days=200, chunk_days=90) == 3
    assert [c[0] for c in calls].count("openaq:1") == 3  # 200 days in 90-day windows
    assert [c[0] for c in calls].count("openaq:2") == 1  # failed once, then skipped
    # A second run resumes from the stored data (DuckDB returns tz-aware timestamps).
    last = tasks._last_seen()["openaq:1"]
    assert last.tzinfo is not None
    calls.clear()
    tasks.ingest_openaq(days=200, chunk_days=90)
    first_call = next(c for c in calls if c[0] == "openaq:1")
    assert first_call[1] >= (last - pd.Timedelta(hours=3)).to_pydatetime()
    assert first_call[2] <= datetime.now(UTC)


def test_openaq_ingest_ignores_a_stale_last_seen_on_active_stations(monkeypatch):
    now = datetime.now(UTC)
    stations = pd.DataFrame(
        {
            "station_id": ["openaq:1", "openaq:2"],
            "name": "s",
            "type": "reference",
            "source": "openaq",
            "provider": "gov",
            "lat": -6.2,
            "lon": 106.8,
            "active": True,
            "sensor_id": [10, 20],
            "first_seen": None,
            # Stamped at discovery two days ago vs. a station that ended last year.
            "last_seen": [now - pd.Timedelta(days=2), now - pd.Timedelta(days=365)],
        }
    )
    store.write_parquet(stations, paths.raw_stations())
    ends = {}

    def fake_fetch(http, station_id, sensor_id, start, end):
        ends[station_id] = end
        return pd.DataFrame(columns=["station_id", "ts", "value_raw", "source"])

    monkeypatch.setenv("OPENAQ_API_KEY", "k")
    monkeypatch.setattr(openaq, "fetch_hours", fake_fetch)
    monkeypatch.setattr(schemas, "validate", lambda frame, schema: frame)
    tasks.ingest_openaq(days=3)
    assert ends["openaq:1"] >= now
    assert "openaq:2" not in ends  # ended before the window: nothing to ask for


def test_atomic_writes_retry_a_briefly_locked_target(monkeypatch, tmp_path):
    real_replace, calls = store.os.replace, []

    def locked_twice(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError("locked by another process")
        real_replace(src, dst)

    monkeypatch.setattr(store.os, "replace", locked_twice)
    monkeypatch.setattr(store.time, "sleep", lambda s: None)
    store.write_json({"ok": True}, tmp_path / "x.json")
    assert store.read_json(tmp_path / "x.json") == {"ok": True}
    assert len(calls) == 3
    assert not list(tmp_path.glob(".x.json.*.tmp"))
