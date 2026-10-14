"""Sourced daily regional aggregates; no user-location or inequality inference."""

import math
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from services.exposure.advice_aq import JAKARTA
from services.exposure.aq_provider import AQUnavailableError, DataQuality

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Hour = Annotated[int, Field(strict=True, ge=0, le=23)]
Concentration = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class _InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Region(_InputModel):
    kelurahan_id: NonBlank
    name: NonBlank
    kecamatan: NonBlank


class DailyRegion(_InputModel):
    kelurahan_id: NonBlank
    mean_pm25: Concentration
    hours_covered: tuple[Hour, ...]

    @model_validator(mode="after")
    def check_hours(self) -> Self:
        if len(self.hours_covered) != 24 or set(self.hours_covered) != set(range(24)):
            raise ValueError("Every regional daily mean must cover each WIB hour exactly once")
        return self


class DailyAggregate(_InputModel):
    date: date
    boundaries_version: NonBlank
    generated_at: AwareDatetime
    source_kind: Literal["model", "cams"]
    model_version: NonBlank | None = None
    contains_forecast: bool = Field(strict=True)
    data_quality: DataQuality
    items: tuple[DailyRegion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_provenance(self) -> Self:
        if self.source_kind == "model" and self.model_version is None:
            raise ValueError("Model aggregates require a model version")
        ids = [item.kelurahan_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("Daily aggregates cannot repeat a kelurahan")
        if not self.contains_forecast:
            try:
                end = datetime.combine(self.date, time.min, JAKARTA) + timedelta(days=1)
            except OverflowError:
                raise ValueError("Observed day is outside supported timestamp coverage") from None
            if self.generated_at < end:
                raise ValueError(
                    "An incomplete observed day must be labelled as containing forecast"
                )
        return self


class KelurahanArtifact(_InputModel):
    """Internal P1 adapter format; frozen cross-lane contracts remain unchanged."""

    source: NonBlank
    aggregation_method: NonBlank
    units: Literal["ug/m3"]
    boundaries_version: NonBlank
    regions: tuple[Region, ...] = Field(min_length=1)
    days: tuple[DailyAggregate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_coverage(self) -> Self:
        region_ids = {region.kelurahan_id for region in self.regions}
        if len(region_ids) != len(self.regions):
            raise ValueError("Boundary roster cannot repeat a kelurahan")
        dates = [day.date for day in self.days]
        if len(set(dates)) != len(dates):
            raise ValueError("Artifact cannot repeat a WIB day")
        for day in self.days:
            if day.boundaries_version != self.boundaries_version:
                raise ValueError("Daily aggregates must use the declared boundary version")
            if {item.kelurahan_id for item in day.items} != region_ids:
                raise ValueError("Every day must cover the complete declared kelurahan roster")
        return self


@dataclass(frozen=True, slots=True)
class KelurahanMean:
    kelurahan_id: str
    name: str
    kecamatan: str
    mean_pm25: float


@dataclass(frozen=True, slots=True)
class KelurahanResult:
    from_date: date
    to_date: date
    boundaries_version: str
    items: tuple[KelurahanMean, ...]
    data_quality: DataQuality


def mean_daily_values(values: Sequence[float]) -> float:
    """Each complete WIB day has equal duration and the same regional footprint."""
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise AQUnavailableError("Regional mean requires finite non-negative daily values")
    try:
        return math.fsum(value / len(values) for value in values)
    except OverflowError:
        raise AQUnavailableError("Regional mean exceeds supported numeric precision") from None


def aggregate_kelurahan(
    artifact: KelurahanArtifact,
    from_date: date,
    to_date: date,
    now: datetime,
    *,
    allow_synthetic: bool = False,
) -> KelurahanResult:
    """Pure aggregation: reject gaps, never interpolate dates or incomplete regions."""
    if from_date > to_date:
        raise ValueError("Insight date range must be ordered")
    days = tuple(day for day in artifact.days if from_date <= day.date <= to_date)
    # Unique dates are validated at ingestion. This also avoids enumerating huge date ranges.
    if len(days) != (to_date - from_date).days + 1:
        raise AQUnavailableError("No complete daily aggregates for the requested range")
    if any(day.generated_at > now for day in days):
        raise AQUnavailableError("Regional aggregates are not published yet")
    qualities = {day.data_quality for day in days}
    if "synthetic" in qualities and not allow_synthetic:
        raise AQUnavailableError("Synthetic insights are forbidden in production")
    quality: DataQuality = (
        "synthetic"
        if "synthetic" in qualities
        else "approximated"
        if "approximated" in qualities
        or any(day.contains_forecast or day.source_kind == "cams" for day in days)
        else "real"
    )
    by_day = tuple({item.kelurahan_id: item.mean_pm25 for item in day.items} for day in days)
    items = tuple(
        KelurahanMean(
            region.kelurahan_id,
            region.name,
            region.kecamatan,
            mean_daily_values(tuple(day[region.kelurahan_id] for day in by_day)),
        )
        for region in sorted(artifact.regions, key=lambda region: region.kelurahan_id)
    )
    return KelurahanResult(from_date, to_date, artifact.boundaries_version, items, quality)


class KelurahanService:
    def __init__(
        self,
        path: Path | None = None,
        *,
        allow_synthetic: bool = False,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path, self.allow_synthetic, self.now = path, allow_synthetic, now
        self._artifact: KelurahanArtifact | None = None
        self._lock = threading.Lock()

    def reload(self) -> None:
        if self.path is None:
            raise AQUnavailableError("No regional aggregate input configured")
        artifact = KelurahanArtifact.model_validate_json(self.path.read_text(encoding="utf-8"))
        now = self.now()
        if any(day.generated_at > now for day in artifact.days):
            raise AQUnavailableError("Regional aggregate publication is in the future")
        if not self.allow_synthetic and any(
            day.data_quality == "synthetic" for day in artifact.days
        ):
            raise AQUnavailableError("Synthetic insights are forbidden in production")
        with self._lock:
            self._artifact = artifact

    def summarize(self, from_date: date, to_date: date) -> KelurahanResult:
        if from_date > to_date:
            raise ValueError("Insight date range must be ordered")
        with self._lock:
            artifact = self._artifact
        if artifact is None:
            raise AQUnavailableError("No complete sourced regional aggregates configured")
        # One immutable snapshot per request; concurrent refresh never mixes old/new days.
        return aggregate_kelurahan(
            artifact, from_date, to_date, self.now(), allow_synthetic=self.allow_synthetic
        )
