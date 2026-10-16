"""Complete point windows with consistent publication and historical provenance."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from services.exposure.advice_aq import JAKARTA, HistoricalAQProvider
from services.exposure.aq_provider import (
    AQUnavailableError,
    CogAQProvider,
    DataQuality,
    Pm25Samples,
)
from services.exposure.geometry import Point, hour_key


@dataclass(frozen=True, slots=True)
class AQWindow:
    samples: tuple[Pm25Samples, ...]
    data_quality: DataQuality
    age_s: int
    contains_forecast: bool = False


def check_sample(samples: Pm25Samples, valid_hour: datetime) -> None:
    if len(samples.p50) != 1 or samples.valid_hour != valid_hour:
        raise AQUnavailableError("AQ sample count/hour differs from the requested point")


def cog_window(
    cog: CogAQProvider | None,
    point: Point,
    window: tuple[datetime, ...],
    now: datetime,
    *,
    forecast_only: bool = False,
    allow_synthetic: bool = False,
) -> AQWindow:
    if cog is None:
        raise AQUnavailableError("No hourly COG coverage configured")
    samples, manifests, qualities = [], [], []
    publication = None
    contains_forecast = False
    for valid_hour in window:
        manifest = cog.manifest(valid_hour)
        if manifest.generated_at > now or manifest.valid_hour != valid_hour:
            raise AQUnavailableError("No published raster for the requested hour")
        if (forecast_only or valid_hour > hour_key(now)) and manifest.kind != "forecast":
            raise AQUnavailableError("Future hours require corrected forecasts")
        if manifest.kind == "forecast":
            if (manifest.metrics or {}).get("forecast_model_corrected") == 0:
                raise AQUnavailableError("Uncorrected IDW/CAMS is not a model forecast")
            if (
                manifest.lead_hours < 1
                or hour_key(manifest.generated_at) + timedelta(hours=manifest.lead_hours)
                != valid_hour
            ):
                raise AQUnavailableError("Forecast lead differs from its publication hour")
            identity = (manifest.model_version, hour_key(manifest.generated_at))
            # Archived past forecasts may come from separate completed cycles.
            if forecast_only or valid_hour > hour_key(now):
                if publication is not None and identity != publication:
                    raise AQUnavailableError("Forecast hours belong to different publications")
                publication = identity
            contains_forecast = True
        elif manifest.lead_hours != 0 or hour_key(manifest.generated_at) != valid_hour:
            raise AQUnavailableError("Nowcast lead/publication differs from its valid hour")
        value = cog.sample((point,), valid_hour)
        check_sample(value, valid_hour)
        if (
            value.source != "cog"
            or value.generated_at != manifest.generated_at
            or value.model_version != manifest.model_version
            or value.data_quality != manifest.data_quality
            or (value.data_quality == "synthetic" and not allow_synthetic)
        ):
            raise AQUnavailableError("AQ samples differ from published provenance")
        samples.append(value)
        manifests.append(manifest)
        qualities.append(value.data_quality)
    # A refresh between reads must not produce a mixture of publications.
    if any(cog.manifest(ts) != m for ts, m in zip(window, manifests, strict=True)):
        raise AQUnavailableError("AQ publication changed during sampling")
    quality: DataQuality = (
        "synthetic"
        if "synthetic" in qualities
        else "approximated"
        if "approximated" in qualities
        else "real"
    )
    return AQWindow(
        tuple(samples),
        quality,
        max(0, round((now - min(m.generated_at for m in manifests)).total_seconds())),
        contains_forecast,
    )


def historical_window(
    historical: HistoricalAQProvider | None,
    point: Point,
    window: tuple[datetime, ...],
    now: datetime,
) -> AQWindow:
    if historical is None or historical.artifact.period_end >= now.astimezone(JAKARTA).date():
        raise AQUnavailableError("No complete hourly COG or sourced historical coverage")
    samples = []
    for ts in window:
        value = historical.sample((point,), ts)
        check_sample(value, ts)
        if (
            value.data_quality != "approximated"
            or value.source != "historical:" + historical.artifact.source
        ):
            raise AQUnavailableError("Historical samples differ from sourced provenance")
        samples.append(value)
    # Date-only observations give a conservative age from the start of the last day.
    observed = datetime.combine(historical.artifact.period_end, time.min, JAKARTA)
    return AQWindow(tuple(samples), "approximated", max(0, round((now - observed).total_seconds())))
