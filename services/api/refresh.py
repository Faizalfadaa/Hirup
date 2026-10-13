"""Reload sourced hourly inputs off the event loop without rebuilding the street graph."""

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from services.api.runtime import Runtime
from services.exposure.advice_aq import HistoricalAQProvider
from services.exposure.aq_provider import FallbackAQProvider, IdwAQProvider, StationSample
from services.exposure.engine import Quantiles
from services.exposure.geometry import Point, hour_key


def refresh(
    runtime: Runtime,
    ts: datetime,
    manifests: tuple[Path, ...],
    fallback_path: Path | None,
    reference_path: Path | None,
    history_path: Path | None = None,
) -> None:
    try:
        _refresh(runtime, ts, manifests, fallback_path, reference_path, history_path)
    finally:
        # Also clear after partial/failed publication: no cached result outlives input changes.
        runtime.invalidate_plans()


def _refresh(
    runtime: Runtime,
    ts: datetime,
    manifests: tuple[Path, ...],
    fallback_path: Path | None,
    reference_path: Path | None,
    history_path: Path | None = None,
) -> None:
    provider = runtime.aq.provider
    if fallback_path is not None:
        raw = json.loads(fallback_path.read_text())
        if raw["data_quality"] not in {"real", "approximated"} or not raw.get("source"):
            raise ValueError("Fallback refresh requires production provenance")
        stations = [
            StationSample(
                Point(**s["point"]),
                datetime.fromisoformat(s["valid_hour"]),
                Quantiles(**s["pm25"]),
                raw["data_quality"],
            )
            for s in raw.get("stations", [])
        ]
        cams = {
            datetime.fromisoformat(key): Quantiles(**value)
            for key, value in raw.get("cams", {}).items()
        }
        fallback = IdwAQProvider(stations, runtime.aq.bounds, cams=cams)
        if isinstance(provider, FallbackAQProvider):
            provider.fallback = fallback
    if reference_path is not None:
        raw = json.loads(reference_path.read_text())
        references = {}
        for key, entry in raw.items():
            if not entry.get("source"):
                raise ValueError("City medians require a source")
            references[hour_key(datetime.fromisoformat(key))] = float(entry["value"])
        runtime.references = references
    if runtime.cog is not None:
        runtime.cog.reload(manifests)
    if history_path is not None:
        try:
            historical = HistoricalAQProvider.load(history_path)
            if runtime.advice_aq is not None:
                runtime.advice_aq.historical = historical
            if runtime.forecast is not None:
                runtime.forecast.historical = historical
        except (ValueError, OSError):
            logging.getLogger(__name__).warning(
                "Historical advice refresh unavailable; retaining prior observations"
            )
    runtime.prepare_hour(ts)


def signature(paths: tuple[Path, ...]) -> tuple[tuple[int, int], ...]:
    stamps = []
    for path in paths:
        try:
            stat = path.stat()
            stamps.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            stamps.append((-1, -1))
    return tuple(stamps)


async def hourly(
    runtime: Runtime,
    manifests: tuple[Path, ...],
    fallback_path: Path | None,
    reference_path: Path | None,
    history_path: Path | None = None,
) -> None:
    paths = manifests + tuple(
        path for path in (fallback_path, reference_path, history_path) if path is not None
    )
    previous = (hour_key(datetime.now(UTC)), await asyncio.to_thread(signature, paths))
    while True:
        # Poll publication metadata, not pixels. P2 can publish after the hour.
        await asyncio.sleep(60)
        now = datetime.now(UTC)
        current = (hour_key(now), await asyncio.to_thread(signature, paths))
        if current == previous:
            continue
        pending = asyncio.create_task(
            asyncio.to_thread(
                refresh, runtime, now, manifests, fallback_path, reference_path, history_path
            )
        )
        try:
            await asyncio.shield(pending)
            previous = current
        except asyncio.CancelledError:
            # Finish current raster I/O before shutdown closes its handles.
            with suppress(ValueError, OSError, KeyError):
                await pending
            raise
        except (ValueError, OSError, KeyError):
            logging.getLogger(__name__).warning(
                "Hourly AQ refresh unavailable; retaining prior data"
            )
