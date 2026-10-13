"""Request-to-dose checks on Docker engines; synthetic AQ is latency/demo only."""

import argparse
import asyncio
import hashlib
import json
from contextlib import ExitStack
from datetime import date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
import numpy as np

from services.api.main import create_app
from services.api.runtime import ROOT, Runtime
from services.api.schemas.routes import PlanResponse
from tests.integration.profiling import StageProfiler


async def run(
    *,
    day: date,
    minimum: float,
    maximum: float,
    reference: float,
    trunk: float,
    output: Path | None = None,
    cold_cache: bool = False,
    profile_stages: bool = False,
) -> dict[str, Any]:
    golden = json.loads((ROOT / "contracts/golden_od.json").read_text())
    env = {
        "HIRUP_DEMO": "true",
        "HIRUP_DEMO_MIN_PM25": str(minimum),
        "HIRUP_DEMO_MAX_PM25": str(maximum),
        "HIRUP_DEMO_REFERENCE_PM25": str(reference),
        "HIRUP_TRUNK_PENALTY": str(trunk),
    }
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient(trust_env=False) as upstream:
        runtime = await asyncio.to_thread(Runtime.from_env, upstream, env)
        profiler = StageProfiler()
        profiling = profiler.install(runtime) if profile_stages else ExitStack()
        with profiling:
            app = create_app(runtime)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://hirup", timeout=30
            ) as api:
                for slot in golden["time_slots"]:
                    departure = datetime.fromisoformat(f"{day.isoformat()}T{slot}:00+07:00")
                    await asyncio.to_thread(runtime.prepare_hour, departure)

                    def payload(
                        pair: dict[str, str], anchor: datetime = departure
                    ) -> dict[str, object]:
                        places = golden["places"]
                        return {
                            "origin": {k: places[pair["origin"]][k] for k in ("lat", "lon")},
                            "destination": {
                                k: places[pair["destination"]][k] for k in ("lat", "lon")
                            },
                            "depart_at": anchor.isoformat(),
                            "mode": "transit",
                            "include_comparison": True,
                        }

                    # Warm the JVM on one public golden pair before timing this slot.
                    await api.post("/v1/routes/plan", json=payload(golden["pairs"][0]))
                    for pair in golden["pairs"]:
                        if cold_cache:
                            runtime.invalidate_plans()
                        profiler.reset()
                        started = perf_counter()
                        response = await api.post("/v1/routes/plan", json=payload(pair))
                        latency = (perf_counter() - started) * 1000
                        record: dict[str, Any] = {
                            "id": pair["id"],
                            "slot": slot,
                            "status": response.status_code,
                            "latency_ms": latency,
                        }
                        if profile_stages:
                            record["stages_ms"] = profiler.snapshot()
                        if response.status_code == 200:
                            planned = PlanResponse.model_validate(response.json())
                            record["options"] = len(planned.options)
                            record["data_quality"] = planned.data_quality.value
                            stable = planned.model_dump(mode="json", exclude={"request_id"})
                            record["result_sha256"] = hashlib.sha256(
                                json.dumps(stable, sort_keys=True).encode()
                            ).hexdigest()
                            if planned.data_quality.value != "synthetic":
                                raise ValueError("Demo benchmark must declare synthetic AQ")
                            for option in planned.options:
                                if not np.isclose(
                                    option.dose_ug, sum(leg.dose_ug for leg in option.legs)
                                ):
                                    raise ValueError("Per-leg dose sum differs from route total")
                        else:
                            record["problem_type"] = response.json().get("type")
                        records.append(record)
                        print(json.dumps(record), flush=True)
                point_latencies = []
                for _ in range(30):
                    started = perf_counter()
                    response = await api.get("/v1/aq/point", params={"lat": -6.2, "lon": 106.8})
                    response.raise_for_status()
                    point_latencies.append((perf_counter() - started) * 1000)
            cache_stats = runtime.plan_cache.stats() if runtime.plan_cache is not None else None
        valid = all(item["status"] == 200 and item.get("options", 0) >= 1 for item in records)
    latencies = [item["latency_ms"] for item in records]
    report = {
        "purpose": "integration/latency; real routing and synthetic AQ; not impact/model metrics",
        "date": day.isoformat(),
        "cold_cache": cold_cache,
        "profile_stages": profile_stages,
        "cache_stats": cache_stats,
        "golden_success": valid,
        "plan_p50_ms": float(np.median(latencies)),
        "plan_p95_ms": float(np.percentile(latencies, 95)),
        "aq_point_p95_ms": float(np.percentile(point_latencies, 95)),
        "records": records,
    }
    if output is not None:
        await asyncio.to_thread(output.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(output.write_text, json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--demo-min-pm25", type=float, required=True)
    parser.add_argument("--demo-max-pm25", type=float, required=True)
    parser.add_argument("--reference-pm25", type=float, required=True)
    parser.add_argument("--trunk-penalty", type=float, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cold-cache", action="store_true")
    parser.add_argument("--profile-stages", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(
        run(
            day=args.date,
            minimum=args.demo_min_pm25,
            maximum=args.demo_max_pm25,
            reference=args.reference_pm25,
            trunk=args.trunk_penalty,
            output=args.output,
            cold_cache=args.cold_cache,
            profile_stages=args.profile_stages,
        )
    )
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    if not report["golden_success"]:
        raise SystemExit("Some golden OD requests failed; inspect the reported slot/pair IDs")
    if report["plan_p95_ms"] > 5000 or report["aq_point_p95_ms"] > 500:
        raise SystemExit("Local p95 latency exceeds the Must target")


if __name__ == "__main__":
    main()
