import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from services.api.refresh import hourly
from services.api.runtime import Runtime
from services.exposure.geometry import Point
from services.exposure.params import UnverifiedParamsWarning


async def test_refresh_worker_detects_publication_inside_hour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "late.json"
    clock = datetime.now(UTC)
    calls = 0

    async def tick(delay: float) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.to_thread(
                inputs.write_text,
                json.dumps(
                    {
                        "data_quality": "approximated",
                        "source": "unit test",
                        "cams": {clock.isoformat(): {"p10": 10, "p50": 20, "p90": 30}},
                    }
                ),
            )
        else:
            raise asyncio.CancelledError

    async with httpx.AsyncClient() as http:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(http, {"HIRUP_DATA_DIR": str(tmp_path)})
        monkeypatch.setattr(asyncio, "sleep", tick)
        with pytest.raises(asyncio.CancelledError):
            await hourly(configured, (), inputs, None)
        assert configured.aq.point(Point(106.8, -6.2), clock).p50[0] == 20
