import argparse
import os
from datetime import date

import pytest

from tests.integration.advice_runner import run


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("HIRUP_TEST_ADVICE") != "1",
    reason="Set HIRUP_TEST_ADVICE=1 with the Docker routing stack and active graph ready",
)
async def test_demo_advice_windows_with_live_engines() -> None:
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
    assert report["requests"] == 12
