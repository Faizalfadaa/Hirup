import os
from datetime import date

import pytest

from tests.integration.golden_runner import run


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("HIRUP_TEST_GOLDEN") != "1",
    reason="Set HIRUP_TEST_GOLDEN=1 with the Docker routing stack running",
)
async def test_all_golden_od_requests_return_options() -> None:
    # Explicit test/demo inputs, never scientific model or impact evaluation data.
    report = await run(day=date(2026, 10, 14), minimum=10, maximum=80, reference=40, trunk=2)
    assert report["golden_success"] is True
    assert len(report["records"]) == 30
    assert report["plan_p95_ms"] <= 5000
    assert report["aq_point_p95_ms"] <= 500
