"""Latency benchmark on real OSM with explicitly synthetic AQ, not an impact report."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from services.exposure.aq_provider import SyntheticAQProvider
from services.exposure.geometry import Point
from services.routing.active_graph import load_graph
from services.routing.active_params import load_active_params
from services.routing.active_router import ActiveMode, ActiveRouter

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=ROOT / "data/graphs/active.json.gz")
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument(
        "--trunk-penalty",
        type=float,
        required=True,
        help="Explicit route preference, not a calibrated constant",
    )
    parser.add_argument(
        "--reference-pm25",
        type=float,
        required=True,
        help="Explicit synthetic reference for this performance test",
    )
    parser.add_argument("--demo-min-pm25", type=float, required=True)
    parser.add_argument("--demo-max-pm25", type=float, required=True)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    graph = load_graph(args.graph)
    provider = SyntheticAQProvider(args.demo_min_pm25, args.demo_max_pm25)
    router = ActiveRouter(
        graph, load_active_params(), provider, trunk_penalty_factor=args.trunk_penalty
    )
    ts = datetime.fromisoformat("2026-10-14T08:00:00+07:00")
    start = perf_counter()
    router.refresh_aq(ts, args.reference_pm25)
    refresh_ms = (perf_counter() - start) * 1000
    # Senayan to Setiabudi: report the measured street distance, not a rounded claim.
    places = json.loads((ROOT / "contracts/golden_od.json").read_text())["places"]
    origin = Point(places["senayan"]["lon"], places["senayan"]["lat"])
    destination = Point(places["setiabudi"]["lon"], places["setiabudi"]["lat"])
    modes: tuple[ActiveMode, ...] = ("WALK", "BICYCLE")
    report: list[dict[str, object]] = []
    target_exceeded = False
    for mode in modes:
        routes = router.plan(origin, destination, ts, mode)
        latencies = []
        for _ in range(args.iterations):
            started = perf_counter()
            routes = router.plan(origin, destination, ts, mode)
            latencies.append((perf_counter() - started) * 1000)
        target_exceeded |= float(np.percentile(latencies, 95)) >= 300
        report.append(
            {
                "mode": mode,
                "iterations": args.iterations,
                "p50_ms": float(np.median(latencies)),
                "p95_ms": float(np.percentile(latencies, 95)),
                "max_ms": max(latencies),
                "distance_m": routes[0].distance_m,
                "variants": len(routes),
                "data_quality": "synthetic",
            }
        )
    print(
        json.dumps(
            {
                "graph_nodes": len(graph.nodes),
                "graph_edges": len(graph.edges),
                "aq_refresh_ms": refresh_ms,
                "purpose": "latency only; not model or impact metrics",
                "origin": "senayan",
                "destination": "setiabudi",
                "routes": report,
            },
            indent=2,
        )
    )
    if target_exceeded:
        raise SystemExit("Active routing p95 exceeds 300 ms; see measured route lengths")


if __name__ == "__main__":
    main()
