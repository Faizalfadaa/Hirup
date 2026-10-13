"""Cache miss/hit and small concurrent bursts on public OD, synthetic AQ explicitly."""

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
import numpy as np

from services.api.main import create_app
from services.api.runtime import ROOT, Runtime
from services.api.schemas.routes import PlanResponse


async def run(args: argparse.Namespace) -> dict[str, Any]:
    golden = json.loads((ROOT / "contracts/golden_od.json").read_text())
    around = datetime.fromisoformat(f"{args.date.isoformat()}T07:30:00+07:00")
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient(trust_env=False) as upstream:
        configured = await asyncio.to_thread(
            Runtime.from_env,
            upstream,
            {
                "HIRUP_DEMO": "true",
                "HIRUP_DEMO_MIN_PM25": str(args.demo_min_pm25),
                "HIRUP_DEMO_MAX_PM25": str(args.demo_max_pm25),
                "HIRUP_DEMO_REFERENCE_PM25": str(args.reference_pm25),
                "HIRUP_TRUNK_PENALTY": str(args.trunk_penalty),
            },
        )
        await asyncio.to_thread(configured.prepare_hour, around)
        app = create_app(configured)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://hirup"
        ) as api:

            async def call(pair: dict[str, str], phase: str) -> dict[str, Any]:
                places = golden["places"]
                payload = {
                    "origin": {k: places[pair["origin"]][k] for k in ("lat", "lon")},
                    "destination": {k: places[pair["destination"]][k] for k in ("lat", "lon")},
                    "depart_at": around.isoformat(),
                    "include_comparison": True,
                }
                started = perf_counter()
                reply = await api.post("/v1/routes/plan", json=payload)
                record = {
                    "phase": phase,
                    "pair_id": pair["id"],
                    "status": reply.status_code,
                    "latency_ms": (perf_counter() - started) * 1000,
                }
                if reply.status_code == 200:
                    body = PlanResponse.model_validate(reply.json())
                    if body.data_quality.value != "synthetic" or "sel 100 m" not in body.disclaimer:
                        raise ValueError(
                            "Cache demo must declare synthetic AQ and approximate locations"
                        )
                    if not body.options:
                        raise ValueError("A successful route requires an option")
                    for option in body.options:
                        if not np.isclose(option.dose_ug, sum(leg.dose_ug for leg in option.legs)):
                            raise ValueError("Cached total dose must match per-leg dose")
                records.append(record)
                return record

            await call(golden["pairs"][0], "warmup")
            records.clear()
            for pair in golden["pairs"]:
                configured.invalidate_plans()
                cold = await call(pair, "miss")
                print(json.dumps(cold), flush=True)
                if cold["status"] == 200:
                    for _ in range(10):
                        await call(pair, "hit")
            configured.invalidate_plans()
            before = configured.plan_cache.stats()
            await asyncio.gather(*(call(golden["pairs"][0], "same_key_burst") for _ in range(8)))
            after = configured.plan_cache.stats()
            shared = {key: after[key] - before[key] for key in ("hits", "misses", "joins")}
            if shared["misses"] != 1:
                raise ValueError("Identical concurrent requests must share one upstream plan")
            configured.invalidate_plans()
            await asyncio.gather(
                *(call(pair, "distinct_key_burst") for pair in golden["pairs"][:4])
            )
            stats = configured.plan_cache.stats()
    phases = {}
    for phase in ("miss", "hit", "same_key_burst", "distinct_key_burst"):
        group = [record for record in records if record["phase"] == phase]
        latencies = [record["latency_ms"] for record in group]
        phases[phase] = {
            "requests": len(group),
            "successes": sum(record["status"] == 200 for record in group),
            "p50_ms": float(np.median(latencies)) if latencies else None,
            "p95_ms": float(np.percentile(latencies, 95)) if latencies else None,
            "max_ms": max(latencies) if latencies else None,
        }
    report = {
        "purpose": "local cache latency: real routing, synthetic AQ; not impact metrics",
        "success": all(record["status"] == 200 for record in records),
        "phases": phases,
        "same_key_work": shared,
        "cache_stats": stats,
        "records": records,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--demo-min-pm25", type=float, required=True)
    parser.add_argument("--demo-max-pm25", type=float, required=True)
    parser.add_argument("--reference-pm25", type=float, required=True)
    parser.add_argument("--trunk-penalty", type=float, required=True)
    parser.add_argument("--output", type=Path)
    report = asyncio.run(run(parser.parse_args()))
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    if not report["success"]:
        raise SystemExit("Some cache cases failed; inspect per-phase statuses")


if __name__ == "__main__":
    main()
