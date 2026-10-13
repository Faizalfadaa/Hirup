"""Complete hourly forecast windows with explicit publication and fallback policy."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal

from services.exposure.advice_aq import JAKARTA, HistoricalAQProvider
from services.exposure.aq_provider import (
    AQUnavailableError,
    CogAQProvider,
    DataQuality,
    OutOfServiceAreaError,
    Pm25Samples,
)
from services.exposure.engine import Quantiles
from services.exposure.geometry import BoundingBox, Point, hour_key


@dataclass(frozen=True, slots=True)
class ForecastHour:
    valid_hour: datetime
    pm25: Quantiles


@dataclass(frozen=True, slots=True)
class ForecastResult:
    hours: tuple[ForecastHour, ...]
    source: Literal["model_corrected", "historical_mean"]
    data_quality: DataQuality
    age_s: int


class ForecastService:
    def __init__(
        self,
        bounds: BoundingBox,
        cog: CogAQProvider | None,
        historical: HistoricalAQProvider | None = None,
        *,
        allow_synthetic: bool = False,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.bounds, self.cog, self.historical = bounds, cog, historical
        self.allow_synthetic, self.now = allow_synthetic, now

    def forecast(self, point: Point, hours: int) -> ForecastResult:
        if not self.bounds.contains(point):
            raise OutOfServiceAreaError("Forecast point is outside the pilot service area")
        if type(hours) is not int or not 1 <= hours <= 24:
            raise ValueError("Forecast horizon must be an integer from 1 to 24 hours")
        now = self.now()
        window = tuple(hour_key(now) + timedelta(hours=i) for i in range(1, hours + 1))
        try:
            return self._corrected(point, window, now)
        except (AQUnavailableError, OutOfServiceAreaError):
            # The API has one source field: never mix partial forecast/history windows.
            return self._historical(point, window, now)

    @staticmethod
    def _hour(samples: Pm25Samples, valid_hour: datetime) -> ForecastHour:
        if len(samples.p50) != 1 or samples.valid_hour != valid_hour:
            raise AQUnavailableError("Forecast sample count/hour differs from the requested point")
        return ForecastHour(valid_hour, samples.mean())

    def _corrected(
        self, point: Point, window: tuple[datetime, ...], now: datetime
    ) -> ForecastResult:
        cog = self.cog
        if cog is None:
            raise AQUnavailableError("No corrected forecast configured")
        result, manifests, qualities = [], [], []
        publication = None
        for valid_hour in window:
            manifest = cog.manifest(valid_hour)
            if (
                manifest.kind != "forecast"
                or manifest.generated_at > now
                or manifest.valid_hour != valid_hour
                or hour_key(manifest.generated_at) + timedelta(hours=manifest.lead_hours)
                != valid_hour
            ):
                raise AQUnavailableError("No published corrected forecast for the requested hour")
            # Raster files may finish seconds apart within one hourly inference cycle.
            identity = (manifest.model_version, hour_key(manifest.generated_at))
            if publication is not None and identity != publication:
                raise AQUnavailableError("Forecast hours belong to different publications")
            publication = identity
            samples = cog.sample((point,), valid_hour)
            if (
                samples.source != "cog"
                or samples.generated_at != manifest.generated_at
                or samples.model_version != manifest.model_version
                or samples.data_quality != manifest.data_quality
                or (samples.data_quality == "synthetic" and not self.allow_synthetic)
            ):
                raise AQUnavailableError("Forecast samples differ from published provenance")
            result.append(self._hour(samples, valid_hour))
            manifests.append(manifest)
            qualities.append(samples.data_quality)
        # A publication may change between hourly reads; discard the whole mixed result.
        if any(cog.manifest(ts) != m for ts, m in zip(window, manifests, strict=True)):
            raise AQUnavailableError("Forecast publication changed during sampling")
        quality: DataQuality = (
            "synthetic"
            if "synthetic" in qualities
            else "approximated"
            if "approximated" in qualities
            else "real"
        )
        return ForecastResult(
            tuple(result),
            "model_corrected",
            quality,
            max(0, round((now - min(m.generated_at for m in manifests)).total_seconds())),
        )

    def _historical(
        self, point: Point, window: tuple[datetime, ...], now: datetime
    ) -> ForecastResult:
        historical = self.historical
        if historical is None or historical.artifact.period_end >= now.astimezone(JAKARTA).date():
            raise AQUnavailableError(
                "No complete corrected forecast or sourced historical coverage"
            )
        # Date-only observations give a conservative age from the start of the last day.
        observed = datetime.combine(historical.artifact.period_end, time.min, JAKARTA)
        hours = tuple(self._hour(historical.sample((point,), ts), ts) for ts in window)
        return ForecastResult(
            hours,
            "historical_mean",
            "approximated",
            max(0, round((now - observed).total_seconds())),
        )
