import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import datetime

import httpx
import pytest

from services.exposure.engine import Mode
from services.exposure.geometry import Point
from services.routing.models import Query
from services.routing.osrm_client import OsrmClient
from services.routing.otp_client import OtpClient, parse_itinerary
from services.routing.polyline import decode, encode

TS = datetime.fromisoformat("2026-10-14T06:30:00+07:00")
POINTS = (Point(106.8, -6.2), Point(106.81, -6.21))
QUERY = Query(*POINTS, TS, max_walk_m=3000)


def itinerary() -> dict[str, object]:
    return {
        "startTime": int(TS.timestamp() * 1000),
        "legs": [
            {
                "mode": "BUS",
                "transitLeg": True,
                "duration": 120,
                "distance": 1000,
                "startTime": int(TS.timestamp() * 1000),
                "endTime": int(TS.timestamp() * 1000) + 120000,
                "from": {
                    "name": "A",
                    "lon": POINTS[0].lon,
                    "lat": POINTS[0].lat,
                    "stop": {"gtfsId": "test:stop"},
                },
                "to": {"name": "B", "lon": POINTS[1].lon, "lat": POINTS[1].lat},
                "legGeometry": {"points": encode(POINTS, 5)},
                "route": {"gtfsId": "test:route", "shortName": "1"},
                "trip": {"gtfsId": "test:trip"},
            }
        ],
    }


def test_precision_6_round_trip_and_known_google_precision_5() -> None:
    assert decode(encode(POINTS)) == POINTS
    assert decode("_p~iF~ps|U_ulLnnqC_mqNvxq`@", 5) == (
        Point(-120.2, 38.5),
        Point(-120.95, 40.7),
        Point(-126.453, 43.252),
    )
    with pytest.raises(ValueError, match="Invalid"):
        decode("_")


async def test_osrm_alternatives_and_missing_congestion_remains_null() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["geometries"] == "polyline6"
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [{"duration": 100, "distance": 500, "geometry": encode(POINTS)}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await OsrmClient(http, "http://osrm", Mode.CAR).candidates(QUERY)
        assert result[0].duration_s == 100
        assert result[0].congestion_factor is None
        assert result[0].data_quality == "approximated"
        calibrated = OsrmClient(http, "http://osrm", Mode.CAR, congestion_hourly={6: 1.5})
        assert (await calibrated.candidates(QUERY))[0].duration_s == 150


async def test_osrm_arrive_by_and_upstream_failure() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503))
    ) as http:
        assert await OsrmClient(http, "http://osrm", Mode.CAR).candidates(QUERY) == ()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "code": "Ok",
                    "routes": [{"duration": 100, "distance": 500, "geometry": encode(POINTS)}],
                },
            )
        )
    ) as http:
        result = await OsrmClient(http, "http://osrm", Mode.MOTORCYCLE).candidates(
            replace(QUERY, arrive_by=True)
        )
        assert (TS - result[0].depart_at).total_seconds() == 100


async def test_otp_nine_variants_run_concurrently_and_deduplicate() -> None:
    active, peak, calls = 0, 0, 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak, calls
        active += 1
        calls += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={"data": {"plan": {"itineraries": [itinerary()]}}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await OtpClient(http, "http://otp").candidates(QUERY)
    assert calls == 9
    assert peak == 9
    assert len(result) == 1
    assert result[0].legs[0].route is not None
    assert result[0].legs[0].points == POINTS


def test_otp_excluded_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="excluded"):
        parse_itinerary(itinerary(), replace(QUERY, excluded_modes=(Mode.BUS,)))


async def test_bus_only_gtfs_skips_empty_and_equivalent_mode_searches() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": {"plan": {"itineraries": [itinerary()]}}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await OtpClient(http, "http://otp", available_modes={"BUS"}).candidates(QUERY)
    assert calls == 3
    assert len(result) == 1


@pytest.mark.parametrize(
    "body", [[], {"data": {"plan": []}}, {"data": {"plan": {"itineraries": [None]}}}]
)
async def test_malformed_otp_response_degrades_to_empty(body: object) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as http:
        assert await OtpClient(http, "http://otp", available_modes={"BUS"}).candidates(QUERY) == ()


async def test_malformed_osrm_response_degrades_to_empty() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    ) as http:
        assert await OsrmClient(http, "http://osrm", Mode.CAR).candidates(QUERY) == ()


@pytest.mark.parametrize("engine", ["otp", "osrm"])
async def test_total_request_deadline_cancels_streaming_upstream(engine: str) -> None:
    closed = asyncio.Event()

    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            # Each read makes progress, but the entire response never completes.
            while True:
                yield b" "
                await asyncio.sleep(0.005)

        async def aclose(self) -> None:
            closed.set()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Trickle()))
    ) as http:
        router = (
            OtpClient(http, "http://otp", timeout_s=0.03, available_modes={"BUS"})
            if engine == "otp"
            else OsrmClient(http, "http://osrm", Mode.CAR, timeout_s=0.03)
        )
        assert await asyncio.wait_for(router.candidates(QUERY), timeout=1) == ()
        assert closed.is_set()


async def test_slow_otp_variant_does_not_discard_successful_variants() -> None:
    calls, cancelled = [], []

    async def respond(request: httpx.Request) -> httpx.Response:
        reluctance = json.loads(request.content)["variables"]["reluctance"]
        calls.append(reluctance)
        if reluctance == 6:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(reluctance)
        return httpx.Response(200, json={"data": {"plan": {"itineraries": [itinerary()]}}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await asyncio.wait_for(
            OtpClient(http, "http://otp", timeout_s=0.03, available_modes={"BUS"}).candidates(
                QUERY
            ),
            timeout=1,
        )
    assert len(result) == 1
    assert sorted(calls) == [1.5, 3, 6]
    assert cancelled == [6]


@pytest.mark.parametrize("engine", ["otp", "osrm"])
async def test_caller_cancellation_propagates_to_engine(engine: str) -> None:
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def respond(request: httpx.Request) -> httpx.Response:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        raise AssertionError("Unreachable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        router = (
            OtpClient(http, "http://otp", available_modes={"BUS"})
            if engine == "otp"
            else OsrmClient(http, "http://osrm", Mode.CAR)
        )
        task = asyncio.create_task(router.candidates(QUERY))
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()


@pytest.mark.parametrize("deadline_s", [0, -1, float("inf"), float("nan")])
async def test_invalid_engine_deadlines_are_rejected(deadline_s: float) -> None:
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError, match="timeout"):
            OtpClient(http, "http://otp", timeout_s=deadline_s)
        with pytest.raises(ValueError, match="timeout"):
            OsrmClient(http, "http://osrm", Mode.CAR, timeout_s=deadline_s)
