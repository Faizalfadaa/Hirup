"""Reload sourced hourly inputs off the event loop without rebuilding the street graph."""

import asyncio
import json
import logging
from concurrent.futures import Executor
from contextlib import suppress
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from services.api.runtime import Runtime
from services.exposure.advice_aq import HistoricalAQProvider
from services.exposure.aq_provider import FallbackAQProvider, IdwAQProvider, StationSample
from services.exposure.engine import Quantiles
from services.exposure.geometry import Point, hour_key
from services.exposure.kelurahan import KelurahanService
from services.exposure.publication import Publication


def refresh(
    runtime: Runtime,
    ts: datetime,
    manifests: tuple[Path, ...],
    fallback_path: Path | None,
    reference_path: Path | None,
    history_path: Path | None = None,
    *,
    publication_path: Path | None = None,
) -> None:
    try:
        if publication_path is not None:
            _refresh_publication(runtime, ts, publication_path)
        else:
            _refresh(runtime, ts, manifests, fallback_path, reference_path, history_path)
    except (TypeError, AttributeError) as exc:
        raise ValueError("Malformed hourly AQ input structure") from exc
    finally:
        # Also clear after partial/failed publication: no cached result outlives input changes.
        runtime.invalidate_plans()


def _refresh_publication(runtime: Runtime, ts: datetime, path: Path) -> None:
    """Validate all non-raster inputs before the owner-thread COG swap."""
    publication = Publication.load(runtime.data_root, path)
    if publication.generated_at > datetime.now(UTC) or runtime.cog is None:
        raise ValueError("Publication is unavailable or the COG reader is not configured")
    raw = json.loads(publication.fallback.read_text())
    if raw["data_quality"] not in {"real", "approximated"} or not raw.get("source"):
        raise ValueError("Publication fallback requires production provenance")
    fallback = IdwAQProvider(
        [
            StationSample(
                Point(**s["point"]),
                datetime.fromisoformat(s["valid_hour"]),
                Quantiles(**s["pm25"]),
                raw["data_quality"],
            )
            for s in raw.get("stations", [])
        ],
        runtime.aq.bounds,
        cams={
            datetime.fromisoformat(key): Quantiles(**value)
            for key, value in raw.get("cams", {}).items()
        },
    )
    references = {}
    for key, entry in json.loads(publication.medians.read_text()).items():
        if not entry.get("source"):
            raise ValueError("Publication medians require a source")
        references[hour_key(datetime.fromisoformat(key))] = float(entry["value"])
    historical = HistoricalAQProvider.load(publication.history) if publication.history else None
    regional = KelurahanService(publication.kelurahan, allow_synthetic=runtime.cog.allow_synthetic)
    if publication.kelurahan is not None:
        regional.reload()
    runtime.cog.reload(publication.manifests)
    provider = runtime.aq.provider
    if isinstance(provider, FallbackAQProvider):
        provider.fallback = fallback
    runtime.references, runtime.kelurahan = references, regional
    runtime.aq.tiles_available = publication.tiles_available
    for service in (runtime.advice_aq, runtime.forecast, runtime.daily_summary):
        if service is not None:
            service.historical = historical
    runtime.prepare_hour(ts)


def _refresh(
    runtime: Runtime,
    ts: datetime,
    manifests: tuple[Path, ...],
    fallback_path: Path | None,
    reference_path: Path | None,
    history_path: Path | None = None,
) -> None:
    if runtime.kelurahan is not None and runtime.kelurahan.path is not None:
        try:
            runtime.kelurahan.reload()
        except (ValueError, OSError):
            logging.getLogger(__name__).warning(
                "Regional aggregate refresh unavailable; retaining prior valid input"
            )
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
            if runtime.daily_summary is not None:
                runtime.daily_summary.historical = historical
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
    *,
    owner: Executor | None = None,
    publication_path: Path | None = None,
) -> None:
    paths = manifests + tuple(
        path for path in (fallback_path, reference_path, history_path) if path is not None
    )
    if publication_path is not None:
        paths = (publication_path,)
    if runtime.kelurahan is not None and runtime.kelurahan.path is not None:
        paths += (runtime.kelurahan.path,)
    previous = (hour_key(datetime.now(UTC)), await asyncio.to_thread(signature, paths))
    while True:
        # Poll publication metadata, not pixels. P2 can publish after the hour.
        await asyncio.sleep(60)
        now = datetime.now(UTC)
        current = (hour_key(now), await asyncio.to_thread(signature, paths))
        if current == previous:
            continue
        pending = asyncio.get_running_loop().run_in_executor(
            owner,
            partial(
                refresh,
                runtime,
                now,
                manifests,
                fallback_path,
                reference_path,
                history_path,
                publication_path=publication_path,
            ),
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
