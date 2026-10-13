"""Public golden OD advice latency with real engines and explicit synthetic demo AQ."""

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
from services.api.schemas.routes import DepartureAdviceResponse


async def run(args: argparse.Namespace) -> dict[str, Any]:
    golden = json.loads((ROOT / "contracts/golden_od.json").read_text())
    pair = golden["pairs"][0]
    origin, destination = (golden["places"][pair[key]] for key in ("origin", "destination"))
    records = []
    async with httpx.AsyncClient(trust_env=False) as upstream:
        runtime = await asyncio.to_thread(
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
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app(runtime)), base_url="http://hirup"
            ) as api:
                for slot in ("07:30", "17:30"):
                    around = datetime.fromisoformat(f"{args.date.isoformat()}T{slot}:00+07:00")
                    await asyncio.to_thread(runtime.prepare_hour, around)
                    # Warm the JVM on the same public pair before recording the 13-slot calls.
                    await api.post(
                        "/v1/routes/plan",
                        json={
                            "origin": {k: origin[k] for k in ("lat", "lon")},
                            "destination": {k: destination[k] for k in ("lat", "lon")},
                            "depart_at": around.isoformat(),
                            "include_comparison": False,
                        },
                    )
                    for mode in ("transit", "walk", "bike"):
                        for profile in ("umum", "rentan"):
                            start = perf_counter()
                            reply = await api.get(
                                "/v1/routes/departure-advice",
                                params={
                                    "origin_lat": origin["lat"],
                                    "origin_lon": origin["lon"],
                                    "destination_lat": destination["lat"],
                                    "destination_lon": destination["lon"],
                                    "around": around.isoformat(),
                                    "mode": mode,
                                    "sensitivity": profile,
                                },
                            )
                            record = {
                                "pair_id": pair["id"],
                                "slot": slot,
                                "mode": mode,
                                "profile": profile,
                                "status": reply.status_code,
                                "latency_ms": (perf_counter() - start) * 1000,
                            }
                            if reply.status_code == 200:
                                body = DepartureAdviceResponse.model_validate(reply.json())
                                if len(body.slots) != 13 or body.data_quality.value != "synthetic":
                                    raise ValueError(
                                        "Demo advice must have 13 labelled synthetic slots"
                                    )
                                baseline = body.slots[6]
                                if baseline.delta_dose_pct != 0 or baseline.delta_duration_s != 0:
                                    raise ValueError(
                                        "Requested departure baseline must have zero deltas"
                                    )
                                record["slots"] = len(body.slots)
                            records.append(record)
                            print(json.dumps(record), flush=True)
        finally:
            if runtime.cog is not None:
                runtime.cog.close()
    times = [r["latency_ms"] for r in records]
    report = {
        "purpose": "advice latency/demo only; real engines, synthetic AQ; no model/impact metrics",
        "success": all(r["status"] == 200 for r in records),
        "requests": len(records),
        "p50_ms": float(np.median(times)),
        "p95_ms": float(np.percentile(times, 95)),
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
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))
    if not report["success"]:
        raise SystemExit("Some advice requests failed; inspect status per public pair/mode/slot")


if __name__ == "__main__":
    main()
