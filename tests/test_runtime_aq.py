import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pytest

from services.api.main import create_app
from services.api.runtime import Runtime, pilot_bounds
from services.exposure.aq_provider import AQUnavailableError, Pm25Samples
from services.exposure.aq_service import AQService, png_rgba
from services.exposure.geometry import Point, hour_key, unproject
from services.exposure.params import UnverifiedParamsWarning

TS = datetime.fromisoformat("2026-10-14T06:30:00+07:00")


class ProductionAQ:
    def sample(self, points: tuple[Point, ...], ts: datetime) -> Pm25Samples:
        values = np.full(len(points), 20.0)
        return Pm25Samples(values, values, values, hour_key(ts), "approximated", "idw")


async def test_missing_raster_manifest_still_uses_sourced_cams(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs.json"
    inputs.write_text(
        json.dumps(
            {
                "data_quality": "approximated",
                "source": "unit test",
                "cams": {TS.isoformat(): {"p10": 10, "p50": 20, "p90": 30}},
            }
        )
    )
    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(
                http,
                {
                    "HIRUP_DATA_DIR": str(tmp_path),
                    "HIRUP_AQ_INPUTS": str(inputs),
                    "HIRUP_AQ_MANIFESTS": json.dumps([str(tmp_path / "not-yet-published.json")]),
                },
            )
        assert configured.aq.point(Point(106.8, -6.2), TS).source == "cams"
        assert configured.planner is not None


async def test_production_is_unavailable_without_real_inputs(tmp_path: Path) -> None:
    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(http, {"HIRUP_DATA_DIR": str(tmp_path)})
        with pytest.raises(AQUnavailableError):
            configured.aq.point(Point(106.8, -6.2), TS)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
        ) as api:
            health = await api.get("/v1/health")
            assert health.json()["status"] == "degraded"
            assert health.json()["data_quality"] == "approximated"


async def test_runtime_refuses_synthetic_fallback_input_file(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs.json"
    inputs.write_text(json.dumps({"data_quality": "synthetic", "source": "unit test"}))
    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning), pytest.raises(ValueError, match="real source"):
            Runtime.from_env(
                http, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_AQ_INPUTS": str(inputs)}
            )


async def test_demo_requires_explicit_concentration_bounds(tmp_path: Path) -> None:
    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning), pytest.raises(KeyError, match="HIRUP_DEMO_MIN"):
            Runtime.from_env(http, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_DEMO": "true"})


def test_production_tile_requires_supplied_hourly_artifact(tmp_path: Path) -> None:
    service = AQService(ProductionAQ(), pilot_bounds(), tiles_dir=tmp_path)
    with pytest.raises(AQUnavailableError, match="No sourced tile"):
        service.tile(0, 0, 0, TS)
    path = tmp_path / "2026101406/0/0/0.png"
    path.parent.mkdir(parents=True)
    pixels = np.zeros((256, 256, 4), dtype=np.uint8)
    path.write_bytes(png_rgba(pixels))
    data, quality = service.tile(0, 0, 0, TS)
    assert data.startswith(b"\x89PNG")
    assert quality == "approximated"


async def test_forecast_age_comes_from_generation_time_not_future_valid_hour(
    tmp_path: Path,
) -> None:
    from tests.test_aq_provider import raster_set

    manifest = raster_set(tmp_path)
    document = json.loads(manifest.read_text())
    document.update(
        data_quality="approximated",
        kind="forecast",
        lead_hours=16,
        generated_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    )
    manifest.write_text(json.dumps(document))
    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(
                http,
                {
                    "HIRUP_DATA_DIR": str(tmp_path),
                    "HIRUP_AQ_MANIFESTS": json.dumps([str(manifest)]),
                },
            )
        try:
            point = unproject(699050, 9313950)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
            ) as api:
                result = await api.get(
                    "/v1/aq/point",
                    params={"lat": point.lat, "lon": point.lon, "ts": document["valid_hour"]},
                )
            assert result.status_code == 200
            assert 3500 <= int(result.headers["X-Data-Age-Seconds"]) <= 3700
        finally:
            assert configured.cog is not None
            configured.cog.close()


async def test_hourly_refresh_adopts_late_inputs_and_keeps_prior_on_bad_data(
    tmp_path: Path,
) -> None:
    from services.api.refresh import refresh, signature

    inputs = tmp_path / "inputs.json"
    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(http, {"HIRUP_DATA_DIR": str(tmp_path)})
        before = signature((inputs,))
        inputs.write_text(
            json.dumps(
                {
                    "data_quality": "approximated",
                    "source": "unit test",
                    "cams": {TS.isoformat(): {"p10": 10, "p50": 20, "p90": 30}},
                }
            )
        )
        assert signature((inputs,)) != before
        refresh(configured, TS, (), inputs, None)
        assert configured.aq.point(Point(106.8, -6.2), TS).p50[0] == 20
        inputs.write_text(json.dumps({"data_quality": "synthetic", "source": "unit test"}))
        with pytest.raises(ValueError, match="provenance"):
            refresh(configured, TS, (), inputs, None)
        assert configured.aq.point(Point(106.8, -6.2), TS).p50[0] == 20
