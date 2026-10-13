import struct
from dataclasses import replace
from datetime import datetime

import httpx
import numpy as np
import pytest

from services.api.main import create_app
from services.api.runtime import Runtime
from services.api.schemas.routes import PlanResponse
from services.exposure.aq_provider import IdwAQProvider, Pm25Samples, SyntheticAQProvider
from services.exposure.aq_service import AQService
from services.exposure.engine import Mode
from services.exposure.geometry import BoundingBox, Point, hour_key
from services.exposure.params import UnverifiedParamsWarning, load_params
from services.routing.models import Candidate, Query, RouteLeg, TransitInfo
from services.routing.plan import Planner
from services.routing.rerank import load_ranking_params

TS = datetime.fromisoformat("2026-10-14T06:30:00+07:00")
BOUNDS = BoundingBox(-6.3, -6.13, 106.76, 106.85)
POINTS = (Point(106.8, -6.2), Point(106.801, -6.201))


class FixedRouter:
    def __init__(self, items: tuple[Candidate, ...] = ()) -> None:
        self.items = items

    async def candidates(self, query: Query) -> tuple[Candidate, ...]:
        return self.items


class FlatAQ:
    def sample(self, points: tuple[Point, ...], ts: datetime) -> Pm25Samples:
        values = np.full(len(points), 60.0)
        return Pm25Samples(values, values, values, ts, "synthetic", "hand-computed test")


def runtime() -> Runtime:
    with pytest.warns(UnverifiedParamsWarning):
        params = load_params()
    transit = Candidate(
        (RouteLeg(Mode.BUS, 600, 1000, POINTS, route=TransitInfo("test:1"), headway_s=600),),
        TS,
        "approximated",
    )
    road = Candidate((RouteLeg(Mode.MOTORCYCLE, 3000, 1000, POINTS),), TS, "approximated")
    aq = FlatAQ()
    planner = Planner(
        bounds=BOUNDS,
        aq=aq,
        params=params,
        ranking={p: load_ranking_params(p) for p in ("umum", "rentan")},
        sample_spacing_m=25,
        transit=FixedRouter((transit,)),
        active=FixedRouter(),
        motorcycle=FixedRouter((road,)),
        car=FixedRouter(),
    )
    return Runtime(AQService(aq, BOUNDS), planner=planner, params=params)


def request() -> dict[str, object]:
    return {
        "origin": {"lon": POINTS[0].lon, "lat": POINTS[0].lat},
        "destination": {"lon": POINTS[1].lon, "lat": POINTS[1].lat},
        "depart_at": TS.isoformat(),
        "mode": "transit",
    }


async def test_request_to_per_leg_dose_comparison_and_labels() -> None:
    app = create_app(runtime())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/v1/routes/plan", json=request())
    assert result.status_code == 200
    body = PlanResponse.model_validate(result.json())
    assert body.request_id == result.headers["X-Request-ID"]
    assert body.data_quality == "synthetic"
    option = body.options[0]
    assert option.labels == ["fastest", "cleanest", "balanced"]
    assert [leg.mode for leg in option.legs] == ["WAIT", "BUS"]
    assert option.legs[0].duration_s == 300
    assert option.duration_s == 900
    assert option.dose_ug == pytest.approx(sum(leg.dose_ug for leg in option.legs))
    assert option.cig_eq == pytest.approx(option.ct_ugh_m3 / 528)
    assert body.comparison is not None
    assert body.comparison.motorcycle is not None
    assert body.comparison.motorcycle.dose_ug == pytest.approx(39)
    assert body.comparison.motorcycle.congestion_factor is None
    assert body.comparison.motorcycle.co2_kg is None
    assert body.comparison.motorcycle.cost_idr is None


async def test_point_quality_header_and_outside_area_problem() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(runtime())), base_url="http://test"
    ) as client:
        result = await client.get(
            "/v1/aq/point", params={"lat": -6.2, "lon": 106.8, "ts": TS.isoformat()}
        )
        assert result.status_code == 200
        assert result.json()["pm25"] == {"p10": 60, "p50": 60, "p90": 60}
        assert result.json()["ispu_category"] is None
        assert "X-Data-Age-Seconds" in result.headers
        outside = await client.get("/v1/aq/point", params={"lat": 0, "lon": 0})
        assert outside.status_code == 404
        assert outside.json()["type"] == "out_of_service_area"


async def test_no_aq_returns_503_without_synthetic_substitution() -> None:
    configured = runtime()
    assert configured.planner is not None
    configured.planner.aq = IdwAQProvider([], BOUNDS)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        result = await client.post("/v1/routes/plan", json=request())
    assert result.status_code == 503
    assert result.headers["content-type"] == "application/problem+json"


async def test_plan_outside_area_is_404_even_with_unconfigured_runtime() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        result = await client.post(
            "/v1/routes/plan", json={**request(), "origin": {"lat": 0, "lon": 0}}
        )
        assert result.status_code == 404
        assert result.json()["type"] == "out_of_service_area"
        no_data = await client.post("/v1/routes/plan", json=request())
        assert no_data.status_code == 503


async def test_arrive_by_estimated_timeline_and_no_comparison() -> None:
    configured = runtime()
    assert configured.planner is not None
    query = Query(*POINTS, TS, arrive_by=True, include_comparison=False)
    result = await configured.planner.plan(query)
    candidate = result.options[0].scored.candidate
    assert (TS - candidate.depart_at).total_seconds() == 900
    assert result.valid_hour == hour_key(candidate.depart_at)
    assert result.motorcycle is None


async def test_demo_tile_is_valid_png_and_clearly_synthetic() -> None:
    configured = runtime()
    configured.aq = AQService(SyntheticAQProvider(10, 80), BOUNDS, demo_range=(10, 80))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        # Jakarta pilot at z=0 overlaps the world tile; demo outside area stays transparent.
        result = await client.get("/v1/aq/tiles/0/0/0.png", params={"ts": TS.isoformat()})
        assert result.status_code == 200
        assert result.headers["content-type"] == "image/png"
        assert result.headers["X-Data-Quality"] == "synthetic"
        assert result.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack("!2I", result.content[16:24]) == (256, 256)
        invalid = await client.get("/v1/aq/tiles/0/1/0.png")
        assert invalid.status_code == 400
        outside = await client.get("/v1/aq/tiles/10/0/0.png")
        assert outside.status_code == 404


async def test_transit_without_verified_headway_is_dropped() -> None:
    configured = runtime()
    assert configured.planner is not None
    leg = replace(runtime().planner.transit.items[0].legs[0], headway_s=None)
    configured.planner.transit = FixedRouter((Candidate((leg,), TS, "approximated"),))
    with pytest.raises(ValueError, match="No route"):
        await configured.planner.plan(Query(*POINTS, TS))
