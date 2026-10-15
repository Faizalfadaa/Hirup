"""Advice-only forecast policy and sourced historical hour-of-week fallback."""

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.exposure.aq_provider import (
    AQProvider,
    AQUnavailableError,
    CogAQProvider,
    ManifestBounds,
    OutOfServiceAreaError,
    Pm25Samples,
)
from services.exposure.geometry import Point, hour_key

JAKARTA = ZoneInfo("Asia/Jakarta")
HourOfWeek = Annotated[str, Field(pattern=r"^[0-6]:([01][0-9]|2[0-3])$")]
Concentration = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class HistoricalQuantiles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    p10: Concentration
    p50: Concentration
    p90: Concentration

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if not self.p10 <= self.p50 <= self.p90:
            raise ValueError("Historical quantiles must be ordered")
        return self


class HistoricalAQInput(BaseModel):
    """Internal file adapter, not a new or modified cross-lane contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str = Field(min_length=1)
    data_quality: Literal["approximated"]
    units: Literal["ug/m3"]
    period_start: date
    period_end: date
    bbox_wgs84: ManifestBounds
    hours: dict[HourOfWeek, HistoricalQuantiles]

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if not self.source.strip() or self.period_end < self.period_start:
            raise ValueError("Historical inputs require a source and ordered observation period")
        if not self.hours:
            raise ValueError("Historical inputs require observed hour-of-week statistics")
        self.bbox_wgs84.domain()
        return self


class HistoricalAQProvider:
    """Regional mean quantiles from observations, never inferred from a current raster."""

    def __init__(self, artifact: HistoricalAQInput) -> None:
        self.artifact = artifact
        self.bounds = artifact.bbox_wgs84.domain()

    @classmethod
    def load(cls, path: Path) -> "HistoricalAQProvider":
        return cls(HistoricalAQInput.model_validate_json(path.read_text(encoding="utf-8")))

    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
        if any(not self.bounds.contains(point) for point in points):
            raise AQUnavailableError("Historical artifact does not cover the requested geometry")
        local = ts.astimezone(JAKARTA)
        # The input must describe observations completed before the day being estimated.
        if self.artifact.period_end >= local.date():
            raise AQUnavailableError("Historical period overlaps the requested day")
        value = self.artifact.hours.get(f"{local.weekday()}:{local.hour:02d}")
        if value is None:
            raise AQUnavailableError("No observed statistics for this hour of the week")
        return Pm25Samples(
            np.full(len(points), value.p10, dtype=np.float64),
            np.full(len(points), value.p50, dtype=np.float64),
            np.full(len(points), value.p90, dtype=np.float64),
            hour_key(ts),
            "approximated",
            "historical:" + self.artifact.source,
        )


class AdviceAQProvider:
    def __init__(
        self,
        primary: AQProvider,
        cog: CogAQProvider | None,
        historical: HistoricalAQProvider | None,
        *,
        demo: bool = False,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.primary, self.cog, self.historical = primary, cog, historical
        self.demo, self.now = demo, now

    def sample(self, points: Sequence[Point], ts: datetime) -> Pm25Samples:
        now = self.now()
        try:
            if self.demo:
                return self.primary.sample(points, ts)
            if hour_key(ts) > hour_key(now):
                if self.cog is None:
                    raise AQUnavailableError("No corrected forecast configured")
                manifest = self.cog.manifest(ts)
                if manifest.kind != "forecast" or manifest.generated_at > now:
                    raise AQUnavailableError("No published corrected forecast for this hour")
                if (manifest.metrics or {}).get("forecast_model_corrected") == 0:
                    raise AQUnavailableError("Uncorrected IDW/CAMS is not an advice forecast")
                samples = self.cog.sample(points, ts)
                current = self.cog.manifest(ts)
                if (
                    current.kind != "forecast"
                    or current.generated_at > now
                    or samples.generated_at != current.generated_at
                    or samples.model_version != current.model_version
                ):
                    raise AQUnavailableError("Forecast publication changed during sampling")
            else:
                samples = self.primary.sample(points, ts)
            if samples.data_quality == "synthetic":
                raise AQUnavailableError("Synthetic advice is forbidden in production")
            return samples
        except (AQUnavailableError, OutOfServiceAreaError):
            if (
                self.historical is None
                or self.historical.artifact.period_end >= now.astimezone(JAKARTA).date()
            ):
                raise AQUnavailableError("No forecast or sourced historical coverage") from None
            return self.historical.sample(points, ts)
