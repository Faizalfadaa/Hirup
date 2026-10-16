"""`hirup-ml <command>`; run `hirup-ml --help` for the list."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime

from hirup_ml import baseline, insights, predict, registry, train
from hirup_ml.config import manifests_dir
from hirup_pipelines.settings import data_dir


def api_env() -> dict[str, str]:
    """Environment the API (P1) needs to read P2's outputs."""
    slots = [(manifests_dir() / name).as_posix() for name in predict.slot_names()]
    return {
        "HIRUP_DATA_DIR": data_dir().as_posix(),
        "HIRUP_AQ_PUBLICATION": (data_dir() / "aq_publication.json").as_posix(),
        "HIRUP_AQ_MANIFESTS": json.dumps(slots, separators=(",", ":")),
        "HIRUP_AQ_INPUTS": (data_dir() / "aq_inputs.json").as_posix(),
        "HIRUP_CITY_MEDIANS": (data_dir() / "city_medians.json").as_posix(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="hirup-ml", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("baseline", help="IDW (LOSO) and CAMS baselines -> data/reports/baseline.json")
    sub.add_parser("hourly", help="ingest/QC followed by one complete raster publication")
    fit = sub.add_parser("train", help="tune, validate (LOSO), save and maybe promote a model")
    fit.add_argument("--trials", type=int, help="Optuna trials (0 = config defaults, no tuning)")
    run = sub.add_parser("predict", help="hourly inference: rasters, manifests, tiles, insights")
    run.add_argument("--at", type=datetime.fromisoformat, help="ISO time with offset (default now)")
    city = sub.add_parser("insights", help="print the Insight Kota payload for a date range")
    city.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    city.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    city.add_argument("--hours", type=int, nargs="*", help="local hours of day to include")
    sub.add_parser("status", help="show the model registry")
    sub.add_parser("env", help="print the environment variables the API needs")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    if args.command == "hourly":
        from hirup_pipelines import tasks

        tasks.hourly()
        print(json.dumps(predict.run(), indent=2))
    elif args.command == "baseline":
        print(json.dumps(baseline.run(), indent=2))
    elif args.command == "train":
        entry = train.run(args.trials)
        print(
            json.dumps(
                {k: entry[k] for k in ("model_version", "metrics", "is_active", "promotion")},
                indent=2,
            )
        )
    elif args.command == "predict":
        if args.at is not None and args.at.tzinfo is None:
            parser.error("--at needs a UTC offset, for example 2026-10-16T07:00:00+07:00")
        print(json.dumps(predict.run(args.at), indent=2))
    elif args.command == "insights":
        print(
            json.dumps(
                insights.summarise(args.start, args.end, args.hours), indent=2, ensure_ascii=False
            )
        )
    elif args.command == "status":
        for entry in registry.entries():
            flag = "ACTIVE" if entry["is_active"] else "      "
            print(flag, entry["model_version"], entry["metrics"], entry.get("promotion", ""))
        if not registry.entries():
            print("no models registered; inference serves the IDW + CAMS fallback")
    elif args.command == "env":
        for name, value in api_env().items():
            print(f"{name}='{value}'")


if __name__ == "__main__":
    main()
