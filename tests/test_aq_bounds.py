import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from services.api.main import create_app
from services.api.runtime import Runtime, aq_bounds, pilot_bounds
from services.exposure.aq_provider import SyntheticAQProvider
from services.exposure.aq_service import AQService
from services.exposure.geometry import BoundingBox

WIDE = {"min_lat": -6.375, "max_lat": -6.085, "min_lon": 106.685, "max_lon": 106.975}
TS = datetime(2026, 10, 16, 7, tzinfo=ZoneInfo("Asia/Jakarta"))


def test_aq_bounds_default_to_the_pilot_and_must_contain_it() -> None:
    assert aq_bounds({}) == pilot_bounds()
    assert aq_bounds({"HIRUP_AQ_BOUNDS": json.dumps(WIDE)}) == BoundingBox(**WIDE)
    smaller = {"min_lat": -6.25, "max_lat": -6.20, "min_lon": 106.78, "max_lon": 106.80}
    with pytest.raises(ValueError, match="pilot"):
        aq_bounds({"HIRUP_AQ_BOUNDS": json.dumps(smaller)})


async def test_wider_map_serves_air_quality_but_routes_stay_in_the_pilot() -> None:
    bounds = BoundingBox(**WIDE)
    runtime = Runtime(AQService(SyntheticAQProvider(20, 80, seed=1), bounds))
    # Cempaka Putih: inside the DKI map, east of the pilot corridor (lon 106.85).
    east = {"lat": -6.18, "lon": 106.87}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(runtime)), base_url="http://test"
    ) as client:
        point = await client.get("/v1/aq/point", params={**east, "ts": TS.isoformat()})
        assert point.status_code == 200
        plan = await client.post(
            "/v1/routes/plan",
            json={
                "origin": east,
                "destination": {"lat": -6.2008, "lon": 106.8227},
                "depart_at": TS.isoformat(),
            },
        )
        assert plan.status_code == 404
        assert plan.json()["type"] == "out_of_service_area"
