"""Cold golden OD on real Docker engines and explicitly synthetic P2 model/COG outputs."""

import asyncio
import json
from datetime import date
from pathlib import Path

from tests.integration.golden_runner import run
from tests.integration.p2_backend import fixture


async def main() -> None:
    day = date(2026, 10, 14)
    output = Path("data/develop-validation/p2-golden.json")
    async with fixture(day) as factory:
        report = await run(
            day=day,
            minimum=10,
            maximum=80,
            reference=40,
            trunk=2,
            output=output,
            cold_cache=True,
            profile_stages=True,
            runtime_factory=factory,
        )
    report["aq_provider"] = "seeded toy LightGBM -> P2 COG publication -> P1 reader; synthetic only"
    await asyncio.to_thread(output.write_text, json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}))
    if (
        not report["golden_success"]
        or report["plan_p95_ms"] > 5000
        or report["aq_point_p95_ms"] > 500
    ):
        raise SystemExit("P2 fixture golden OD failed or exceeded Must latency")


if __name__ == "__main__":
    asyncio.run(main())
