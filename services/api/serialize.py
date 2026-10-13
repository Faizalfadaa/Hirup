"""Map domain calculations to frozen response models; rounding occurs only here."""

import hashlib
from datetime import timedelta
from typing import cast
from zoneinfo import ZoneInfo

from services.api.schemas.common import DataQuality, Sensitivity
from services.api.schemas.routes import (
    Assumption,
    Comparison,
    ComparisonOption,
    Confidence,
    DataFreshness,
    Leg,
    LegMode,
    Place,
    PlanResponse,
    RouteLabel,
    RouteOption,
    TransitRoute,
    WaitPlace,
)
from services.exposure.engine import Mode, assumptions, co2_kg, transit_fare_idr, vehicle_cost_idr
from services.exposure.params import ExposureParams
from services.routing.models import PlanResult, ScoredCandidate, Selected
from services.routing.polyline import encode


def costs(item: ScoredCandidate, params: ExposureParams) -> tuple[float | None, int | None]:
    carbon, cost = [], []
    paid_routes = set()
    for leg in item.candidate.legs:
        if leg.mode in {Mode.WALK, Mode.BICYCLE, Mode.WAIT}:
            continue
        carbon.append(co2_kg(leg.mode, leg.distance_m, params))
        if leg.mode in {Mode.CAR, Mode.MOTORCYCLE}:
            cost.append(vehicle_cost_idr(leg.mode, leg.distance_m, params))
        elif leg.route is not None and leg.route.id not in paid_routes:
            cost.append(transit_fare_idr(leg.mode, params))
            paid_routes.add(leg.route.id)
    return (
        None if any(v is None for v in carbon) else sum(cast(float, v) for v in carbon),
        None if any(v is None for v in cost) else round(sum(cast(float, v) for v in cost)),
    )


def option(selected: Selected, params: ExposureParams) -> RouteOption:
    item, labels = selected.scored, selected.labels
    legs, clock = [], item.candidate.depart_at
    for raw, exposure, segments in zip(
        item.candidate.legs, item.exposure.legs, item.segments_pm25, strict=True
    ):
        # Derive boundaries from cumulative physical durations, avoiding per-leg rounding drift.
        end = clock + timedelta(seconds=raw.duration_s)
        a, b = raw.points[0], raw.points[-1]
        route = raw.route
        legs.append(
            Leg(
                mode=LegMode(raw.mode.value),
                start_time=clock,
                end_time=end,
                duration_s=round(raw.duration_s),
                distance_m=raw.distance_m,
                from_=Place(name=raw.from_name, lat=a.lat, lon=a.lon),
                to=Place(name=raw.to_name, lat=b.lat, lon=b.lon),
                polyline=encode(raw.points) if raw.mode != Mode.WAIT else None,
                segments_pm25=list(segments) if segments else None,
                mean_pm25=exposure.pm25.p50,
                mean_pm25_p10=exposure.pm25.p10,
                mean_pm25_p90=exposure.pm25.p90,
                dose_ug=exposure.dose_ug.p50,
                dose_ug_p10=exposure.dose_ug.p10,
                dose_ug_p90=exposure.dose_ug.p90,
                ct_ugh_m3=exposure.ct_ugh_m3,
                route=TransitRoute(
                    id=route.id,
                    short_name=route.short_name,
                    long_name=route.long_name,
                    agency=route.agency,
                )
                if route is not None
                else None,
                wait_place=WaitPlace(raw.wait_place.value) if raw.wait_place is not None else None,
                headway_s=round(raw.headway_s) if raw.headway_s is not None else None,
            )
        )
        clock = end
    fingerprint = "|".join(
        f"{raw.mode}:{encode(raw.points)}:{raw.route.id if raw.route else ''}"
        for raw in item.candidate.legs
    )
    identifier = "op_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:12]
    carbon, cost = costs(item, params)
    return RouteOption(
        option_id=identifier,
        labels=[RouteLabel(label) for label in labels],
        depart_at=item.candidate.depart_at,
        arrive_at=clock,
        duration_s=round(item.exposure.duration_s),
        transfers=item.candidate.transfers,
        distance_m=item.candidate.distance_m,
        mean_pm25=item.exposure.mean_pm25,
        dose_ug=item.exposure.dose_ug.p50,
        dose_ug_p10=item.exposure.dose_ug.p10,
        dose_ug_p90=item.exposure.dose_ug.p90,
        ct_ugh_m3=item.exposure.ct_ugh_m3,
        cig_eq=item.exposure.cig_eq,
        daily_dose_share=item.exposure.daily_dose_share,
        delta_vs_fastest_pct=selected.dose_delta_pct,
        delta_duration_vs_fastest_s=selected.duration_delta_s,
        exceeds_profile_threshold=None,
        co2_kg=carbon,
        cost_idr=cost,
        data_quality=DataQuality(item.data_quality),
        legs=legs,
    )


def comparison(item: ScoredCandidate | None, params: ExposureParams) -> ComparisonOption | None:
    if item is None:
        return None
    carbon, cost = costs(item, params)
    leg = item.candidate.legs[0]
    entries = [
        Assumption(key=a.key, value=a.value, unit=a.unit, source=a.source)
        for a in assumptions(leg.mode, params)
    ]
    entries.append(
        Assumption(
            key="congestion_factor",
            value=item.candidate.congestion_factor,
            unit="1",
            source="TODO(verify): raw OSRM estimate; no sourced congestion profile configured"
            if item.candidate.congestion_factor is None
            else params.sources["congestion_hourly"],
        )
    )
    return ComparisonOption(
        duration_s=round(item.candidate.duration_s),
        distance_m=item.candidate.distance_m,
        mean_pm25=item.exposure.mean_pm25,
        dose_ug=item.exposure.dose_ug.p50,
        dose_ug_p10=item.exposure.dose_ug.p10,
        dose_ug_p90=item.exposure.dose_ug.p90,
        ct_ugh_m3=item.exposure.ct_ugh_m3,
        cig_eq=item.exposure.cig_eq,
        co2_kg=carbon,
        cost_idr=cost,
        congestion_factor=item.candidate.congestion_factor,
        polyline=encode(leg.points),
        data_quality=DataQuality(item.data_quality),
        assumptions=entries,
    )


def response(
    result: PlanResult,
    params: ExposureParams,
    request_id: str,
    sensitivity: Sensitivity,
    include_comparison: bool,
) -> PlanResponse:
    return PlanResponse(
        request_id=request_id,
        data_quality=DataQuality(result.data_quality),
        data_freshness=DataFreshness(
            aq_valid_hour=result.valid_hour.astimezone(ZoneInfo("Asia/Jakarta")),
            model_version=result.model_version,
            confidence=Confidence.LOW if result.data_quality != "real" else Confidence.MEDIUM,
        ),
        sensitivity=sensitivity,
        options=[option(item, params) for item in result.options],
        comparison=Comparison(
            motorcycle=comparison(result.motorcycle, params), car=comparison(result.car, params)
        )
        if include_comparison
        else None,
        disclaimer=("Data simulasi untuk demo. " if result.data_quality == "synthetic" else "")
        + "Estimasi model, bukan pengukuran medis. Waktu tunggu memakai headway/2; "
        "waktu perjalanan merupakan perkiraan, bukan jaminan jadwal kedatangan.",
    )
