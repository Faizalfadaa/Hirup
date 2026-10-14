"""Startup wiring from process environment, never by reading a secret .env file."""

import json
import logging
import os
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

from services.exposure.advice_aq import AdviceAQProvider, HistoricalAQProvider
from services.exposure.aq_provider import (
    AQProvider,
    AQUnavailableError,
    CogAQProvider,
    FallbackAQProvider,
    IdwAQProvider,
    StationSample,
    SyntheticAQProvider,
)
from services.exposure.aq_service import AQService
from services.exposure.daily_summary import DailySummaryService
from services.exposure.engine import Mode, Quantiles
from services.exposure.forecast import ForecastService
from services.exposure.geometry import BoundingBox, Point, hour_key
from services.exposure.kelurahan import KelurahanService
from services.exposure.params import ExposureParams, load_params
from services.routing.active_graph import load_graph
from services.routing.active_params import DEFAULT_PATH, load_active_params
from services.routing.active_router import ActiveRouter
from services.routing.departure_advice import DepartureAdvice
from services.routing.gtfs import GtfsHeadways
from services.routing.models import Candidate, PlanResult, Query
from services.routing.osrm_client import OsrmClient
from services.routing.otp_client import OtpClient
from services.routing.plan import ActiveCandidates, Planner
from services.routing.plan_cache import PlanCache
from services.routing.rerank import load_ranking_params

ROOT = Path(__file__).resolve().parents[2]


def pilot_bounds() -> BoundingBox:
    return BoundingBox(**json.loads((ROOT / "contracts/golden_od.json").read_text())["bbox"])


class EmptyRouter:
    async def candidates(self, query: Query) -> tuple[Candidate, ...]:
        return ()


@dataclass
class Runtime:
    aq: AQService
    planner: Planner | None = None
    params: ExposureParams | None = None
    active: ActiveRouter | None = None
    cog: CogAQProvider | None = None
    model_version: str | None = None
    references: dict[datetime, float] = field(default_factory=dict)
    demo_reference: float | None = None
    advice: DepartureAdvice | None = None
    advice_aq: AdviceAQProvider | None = None
    plan_cache: PlanCache | None = None
    advice_cache: PlanCache | None = None
    forecast: ForecastService | None = None
    daily_summary: DailySummaryService | None = None
    kelurahan: KelurahanService | None = None

    def configure_kelurahan(self, path: Path | None = None) -> None:
        self.kelurahan = KelurahanService(path)
        if path is not None:
            try:
                self.kelurahan.reload()
            except (ValueError, OSError):
                logging.getLogger(__name__).warning(
                    "Regional aggregate input unavailable; insights require complete coverage"
                )

    def configure_daily_summary(self, historical: HistoricalAQProvider | None = None) -> None:
        if self.params is not None:
            self.daily_summary = DailySummaryService(
                self.aq.bounds, self.params, self.cog, historical
            )

    def configure_forecast(self, historical: HistoricalAQProvider | None = None) -> None:
        self.forecast = ForecastService(self.aq.bounds, self.cog, historical)

    def configure_plan_cache(self) -> None:
        if self.planner is not None:
            self.plan_cache = PlanCache(self.planner, self.aq.bounds)

    def invalidate_plans(self) -> None:
        for cache in (self.plan_cache, self.advice_cache):
            if cache is not None:
                cache.invalidate()

    async def plan(self, query: Query) -> PlanResult:
        if self.planner is None:
            raise AQUnavailableError("No planner configured")
        if self.plan_cache is not None:
            return await self.plan_cache.plan(query)
        return await self.planner.plan(query)

    def configure_advice(
        self, *, demo: bool = False, historical: HistoricalAQProvider | None = None
    ) -> None:
        if self.planner is None:
            return
        self.advice_aq = AdviceAQProvider(self.aq.provider, self.cog, historical, demo=demo)
        planner = copy(self.planner)
        planner.aq = self.advice_aq
        if self.plan_cache is not None:
            self.advice_cache = PlanCache(planner, self.aq.bounds)
            # Slot generation already fans out OTP variants; avoid overlapping slot CPU bursts.
            self.advice = DepartureAdvice(self.advice_cache, concurrency=1)
        else:
            self.advice = DepartureAdvice(planner)

    @classmethod
    def unavailable(cls) -> "Runtime":
        bounds = pilot_bounds()
        return cls(AQService(IdwAQProvider([], bounds), bounds))

    def prepare_hour(self, ts: datetime) -> None:
        reference = (
            self.demo_reference
            if self.demo_reference is not None
            else self.references.get(hour_key(ts))
        )
        if self.active is not None and reference is not None:
            self.active.refresh_aq(ts, reference)
            self.invalidate_plans()

    def data_age(self, ts: datetime, source: str) -> int:
        generated_at = (
            self.cog.manifest(ts).generated_at
            if self.cog is not None and source == "cog"
            else hour_key(ts)
        )
        return max(0, round((datetime.now(UTC) - generated_at).total_seconds()))

    @classmethod
    def from_env(cls, http: httpx.AsyncClient, env: Mapping[str, str] | None = None) -> "Runtime":
        settings = os.environ if env is None else env
        # httpx logs full URLs at INFO; those can contain origins or credentials.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        data = Path(settings.get("HIRUP_DATA_DIR") or ROOT / "data")
        bounds = pilot_bounds()
        demo = settings.get("HIRUP_DEMO", "").lower() in {"true", "1"}
        params, active_params = load_params(), load_active_params()
        cog = None
        demo_range = None
        model_version = None
        provider: AQProvider
        if demo:
            low, high = (
                float(settings[name]) for name in ("HIRUP_DEMO_MIN_PM25", "HIRUP_DEMO_MAX_PM25")
            )
            provider = SyntheticAQProvider(
                low, high, seed=int(settings.get("HIRUP_DEMO_SEED") or 20261013)
            )
            demo_range = (low, high)
        else:
            paths = [Path(name) for name in json.loads(settings.get("HIRUP_AQ_MANIFESTS") or "[]")]
            cog = CogAQProvider(data, [], bounds=bounds)
            try:
                cog.reload(paths)
            except AQUnavailableError:
                logging.getLogger(__name__).warning(
                    "Hourly raster unavailable; using sourced fallback"
                )
            stations, cams = [], {}
            if settings.get("HIRUP_AQ_INPUTS") and Path(settings["HIRUP_AQ_INPUTS"]).is_file():
                inputs = json.loads(Path(settings["HIRUP_AQ_INPUTS"]).read_text())
                if inputs["data_quality"] not in {"real", "approximated"} or not inputs.get(
                    "source"
                ):
                    raise ValueError("Fallback inputs require a real source and production quality")
                for station in inputs.get("stations", []):
                    stations.append(
                        StationSample(
                            Point(**station["point"]),
                            datetime.fromisoformat(station["valid_hour"]),
                            Quantiles(**station["pm25"]),
                            inputs["data_quality"],
                        )
                    )
                cams = {
                    datetime.fromisoformat(ts): Quantiles(**value)
                    for ts, value in inputs.get("cams", {}).items()
                }
            provider = FallbackAQProvider(cog, IdwAQProvider(stations, bounds, cams=cams))
        aq = AQService(provider, bounds, tiles_dir=data / "tiles", demo_range=demo_range)
        active = None
        graph_path = Path(settings.get("HIRUP_ACTIVE_GRAPH") or data / "graphs/active.json.gz")
        if graph_path.is_file() and settings.get("HIRUP_TRUNK_PENALTY"):
            active = ActiveRouter(
                load_graph(graph_path),
                active_params,
                provider,
                trunk_penalty_factor=float(settings["HIRUP_TRUNK_PENALTY"]),
            )
        feeds = {
            path.name.removesuffix(".gtfs.zip"): path for path in (data / "otp").glob("*.gtfs.zip")
        }
        gtfs = GtfsHeadways(feeds)
        contract = yaml.safe_load(DEFAULT_PATH.read_text())
        hourly = contract["congestion_hourly"]["value"]
        congestion = (
            {int(h): float(value) for h, value in hourly.items()} if hourly is not None else None
        )
        planner = Planner(
            bounds=bounds,
            aq=provider,
            params=params,
            ranking={profile: load_ranking_params(profile) for profile in ("umum", "rentan")},
            sample_spacing_m=active_params.sample_spacing_m,
            transit=OtpClient(
                http,
                settings.get("OTP_URL") or "http://127.0.0.1:18080/otp/gtfs/v1",
                available_modes=gtfs.transport_modes or None,
            ),
            active=ActiveCandidates(active) if active is not None else EmptyRouter(),
            car=OsrmClient(
                http,
                settings.get("OSRM_CAR_URL") or "http://127.0.0.1:5000",
                Mode.CAR,
                congestion_hourly=congestion,
            ),
            motorcycle=OsrmClient(
                http,
                settings.get("OSRM_MOTO_URL") or "http://127.0.0.1:5001",
                Mode.MOTORCYCLE,
                congestion_hourly=congestion,
            ),
            gtfs=gtfs,
            active_router=active,
            model_version=model_version,
        )
        # Bound the pilot departure search to one 15-minute slot; keep all mode/reluctance variants.
        if isinstance(planner.transit, OtpClient):
            planner.transit.search_window_s = 900
        runtime = cls(aq, planner, params, active, cog, model_version)
        runtime.configure_plan_cache()
        historical = None
        history_path = settings.get("HIRUP_AQ_HISTORY")
        if not demo and history_path and Path(history_path).is_file():
            try:
                historical = HistoricalAQProvider.load(Path(history_path))
            except (ValueError, OSError):
                logging.getLogger(__name__).warning(
                    "Historical advice input unavailable; requiring forecast coverage"
                )
        runtime.configure_advice(demo=demo, historical=historical)
        runtime.configure_forecast(historical=historical)
        runtime.configure_daily_summary(historical=historical)
        kelurahan_path = settings.get("HIRUP_KELURAHAN_SUMMARIES")
        runtime.configure_kelurahan(Path(kelurahan_path) if kelurahan_path else None)
        if demo:
            runtime.demo_reference = float(settings["HIRUP_DEMO_REFERENCE_PM25"])
        elif settings.get("HIRUP_CITY_MEDIANS"):
            references = json.loads(Path(settings["HIRUP_CITY_MEDIANS"]).read_text())
            for ts, entry in references.items():
                if not entry.get("source"):
                    raise ValueError("City reference medians require a source")
                runtime.references[hour_key(datetime.fromisoformat(ts))] = float(entry["value"])
        return runtime
