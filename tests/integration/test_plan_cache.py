import argparse
import os
from datetime import date

import pytest

from tests.integration.cache_runner import run


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("HIRUP_TEST_CACHE") != "1",
    reason="Set HIRUP_TEST_CACHE=1 with the Docker routing stack and active graph ready",
)
async def test_cache_misses_hits_and_small_bursts() -> None:
    report = await run(
        argparse.Namespace(
            date=date(2026, 10, 14),
            demo_min_pm25=10,
            demo_max_pm25=80,
            reference_pm25=40,
            trunk_penalty=2,
            output=None,
        )
    )
    assert report["success"] is True
    assert report["phases"]["miss"]["requests"] == 10
    assert report["phases"]["hit"]["requests"] == 100
    assert report["same_key_work"]["misses"] == 1
