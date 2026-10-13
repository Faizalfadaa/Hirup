"""Complete hourly forecast windows with explicit publication and fallback policy."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from services.exposure.advice_aq import HistoricalAQProvider
from services.exposure.aq_provider import (
    AQUnavailableError,
    CogAQProvider,
    DataQuality,
    OutOfServiceAreaError,
)
from services.exposure.aq_windows import cog_window, historical_window
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

    def _corrected(
        self, point: Point, window: tuple[datetime, ...], now: datetime
    ) -> ForecastResult:
        coverage = cog_window(
            self.cog,
            point,
            window,
            now,
            forecast_only=True,
            allow_synthetic=self.allow_synthetic,
        )
        return ForecastResult(
            tuple(ForecastHour(s.valid_hour, s.mean()) for s in coverage.samples),
            "model_corrected",
            coverage.data_quality,
            coverage.age_s,
        )

    def _historical(
        self, point: Point, window: tuple[datetime, ...], now: datetime
    ) -> ForecastResult:
        coverage = historical_window(self.historical, point, window, now)
        return ForecastResult(
            tuple(ForecastHour(s.valid_hour, s.mean()) for s in coverage.samples),
            "historical_mean",
            coverage.data_quality,
            coverage.age_s,
        )
