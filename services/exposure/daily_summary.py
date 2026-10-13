"""Daily ambient summaries from complete WIB days, with explicit fallback policy."""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from services.exposure.advice_aq import JAKARTA, HistoricalAQProvider
from services.exposure.aq_provider import (
    AQUnavailableError,
    CogAQProvider,
    DataQuality,
    OutOfServiceAreaError,
)
from services.exposure.aq_windows import cog_window, historical_window
from services.exposure.engine import daily_cig_eq
from services.exposure.geometry import BoundingBox, Point, hour_key
from services.exposure.params import ExposureParams


def daily_mean(values: Sequence[float]) -> float:
    """Equal hourly durations: average P50, never quantiles or partial coverage."""
    if len(values) != 24 or any(not math.isfinite(v) or v < 0 for v in values):
        raise AQUnavailableError("Daily mean requires 24 finite non-negative hourly values")
    try:
        return math.fsum(v / 24 for v in values)
    except OverflowError:
        raise AQUnavailableError("Daily mean exceeds supported numeric precision") from None


@dataclass(frozen=True, slots=True)
class DailySummaryResult:
    date: date
    mean_pm25: float
    cig_eq_day: float
    data_quality: DataQuality
    age_s: int


class DailySummaryService:
    def __init__(
        self,
        bounds: BoundingBox,
        params: ExposureParams,
        cog: CogAQProvider | None,
        historical: HistoricalAQProvider | None = None,
        *,
        allow_synthetic: bool = False,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.bounds, self.params, self.cog, self.historical = bounds, params, cog, historical
        self.allow_synthetic, self.now = allow_synthetic, now

    def summarize(self, point: Point, day: date | None = None) -> DailySummaryResult:
        if not self.bounds.contains(point):
            raise OutOfServiceAreaError("Daily summary point is outside the pilot service area")
        now = self.now()
        day = day if day is not None else now.astimezone(JAKARTA).date()
        start = datetime.combine(day, time.min, JAKARTA)
        try:
            window = tuple(hour_key(start + timedelta(hours=h)) for h in range(24))
        except OverflowError:
            raise AQUnavailableError("Requested day is outside supported hourly coverage") from None
        try:
            coverage = cog_window(
                self.cog, point, window, now, allow_synthetic=self.allow_synthetic
            )
        except (AQUnavailableError, OutOfServiceAreaError):
            # Never blend a partial observed/model day with historical statistics.
            coverage = historical_window(self.historical, point, window, now)
        mean = daily_mean(tuple(float(s.p50[0]) for s in coverage.samples))
        cigarettes = daily_cig_eq(mean, self.params)
        if not math.isfinite(cigarettes):
            raise AQUnavailableError("Daily cigarette equivalent is not finite")
        quality = coverage.data_quality
        if coverage.contains_forecast and quality == "real":
            quality = "approximated"
        return DailySummaryResult(day, mean, cigarettes, quality, coverage.age_s)
