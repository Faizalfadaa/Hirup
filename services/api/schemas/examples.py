"""OpenAPI examples. Illustrative only, so every example is labelled `synthetic`.

The plan example reproduces SPEC 13.2 and follows the chapter 12 formulas with the
values in contracts/exposure_params.yaml (dose = C * F * VR * h, cig_eq = sum(C * F * h) / 528).
SPEC 13.2 had two slips that are corrected here: duration_s is the sum of its legs (2310,
not 2280) and transfers is 0 for a single transit leg. Under the rentan profile the cleanest
option also minimises J, so its labels are merged (SPEC 12.4). test_examples.py recomputes
every number.
"""

from typing import Any

JsonDict = dict[str, Any]

_ORIGIN = {"lat": -6.2891, "lon": 106.7745}
_DESTINATION = {"lat": -6.2088, "lon": 106.8227}
_START = {"name": "Titik awal", **_ORIGIN}
_END = {"name": "Titik tujuan", **_DESTINATION}
_LEBAK_BULUS = {"name": "MRT Lebak Bulus", "lat": -6.2893, "lon": 106.7743}
_DUKUH_ATAS = {"name": "MRT Dukuh Atas", "lat": -6.2008, "lon": 106.8227}
_MRT = {
    "id": "MRT:NS",
    "short_name": "MRT",
    "long_name": "MRT Utara-Selatan",
    "agency": "MRT Jakarta",
}

PLAN_REQUEST: JsonDict = {
    "origin": _ORIGIN,
    "destination": _DESTINATION,
    "depart_at": "2026-10-16T07:00:00+07:00",
    "mode": "transit",
    "profile": {"sensitivity": "rentan", "max_walk_m": 1000},
    "include_comparison": True,
}


def _wait_leg(start: str, end: str) -> JsonDict:
    return {
        "mode": "WAIT",
        "start_time": start,
        "end_time": end,
        "duration_s": 150,
        "distance_m": None,
        "from": _LEBAK_BULUS,
        "to": _LEBAK_BULUS,
        "polyline": None,
        "segments_pm25": None,
        "mean_pm25": 55,
        "mean_pm25_p10": 40,
        "mean_pm25_p90": 75,
        "dose_ug": 0.9,
        "dose_ug_p10": 0.7,
        "dose_ug_p90": 1.2,
        "ct_ugh_m3": 1.5,
        "route": None,
        "wait_place": "station",
        "headway_s": 300,
    }


def _subway_leg(start: str, end: str) -> JsonDict:
    return {
        "mode": "SUBWAY",
        "start_time": start,
        "end_time": end,
        "duration_s": 1500,
        "distance_m": 11500,
        "from": _LEBAK_BULUS,
        "to": _DUKUH_ATAS,
        "polyline": "fxz~Jwp~sjE~fEopb@oc}AoiJwk`@_yF_}b@gud@_sNwcA",
        "segments_pm25": [52, 49, 50, 51, 48],
        "mean_pm25": 50,
        "mean_pm25_p10": 37,
        "mean_pm25_p90": 68,
        "dose_ug": 5.7,
        "dose_ug_p10": 4.2,
        "dose_ug_p90": 7.8,
        "ct_ugh_m3": 11.5,
        "route": _MRT,
        "wait_place": None,
        "headway_s": None,
    }


def _walk_leg(
    start: str,
    end: str,
    duration_s: int,
    from_: JsonDict,
    to: JsonDict,
    polyline: str,
    segments: list[float],
    pm25: tuple[float, float, float],
    dose: tuple[float, float, float],
    ct: float,
) -> JsonDict:
    return {
        "mode": "WALK",
        "start_time": start,
        "end_time": end,
        "duration_s": duration_s,
        "distance_m": round(duration_s * 1.2),
        "from": from_,
        "to": to,
        "polyline": polyline,
        "segments_pm25": segments,
        "mean_pm25": pm25[0],
        "mean_pm25_p10": pm25[1],
        "mean_pm25_p90": pm25[2],
        "dose_ug": dose[0],
        "dose_ug_p10": dose[1],
        "dose_ug_p90": dose[2],
        "ct_ugh_m3": ct,
        "route": None,
        "wait_place": None,
        "headway_s": None,
    }


_OP1_LEGS = [
    _walk_leg(
        "2026-10-16T07:00:00+07:00",
        "2026-10-16T07:07:00+07:00",
        420,
        _START,
        _LEBAK_BULUS,
        "vkz~Jg}~sjEwuBgiB~p@vcAfpA~p@",
        [58, 63, 61],
        (61, 45, 83),
        (9.8, 7.2, 13.4),
        8.2,
    ),
    _wait_leg("2026-10-16T07:07:00+07:00", "2026-10-16T07:09:30+07:00"),
    _subway_leg("2026-10-16T07:09:30+07:00", "2026-10-16T07:34:30+07:00"),
    _walk_leg(
        "2026-10-16T07:34:30+07:00",
        "2026-10-16T07:38:30+07:00",
        240,
        _DUKUH_ATAS,
        _END,
        "~|myJwa}vjE~fEg^~jHf^",
        [57, 59],
        (58, 43, 79),
        (5.3, 4.0, 7.3),
        4.4,
    ),
]

_OP2_LEGS = [
    _walk_leg(
        "2026-10-16T07:00:00+07:00",
        "2026-10-16T07:10:00+07:00",
        600,
        _START,
        _LEBAK_BULUS,
        "vkz~Jg}~sjEw`Eg{C~p@f{Cf{CnK",
        [27, 29, 28],
        (28, 21, 38),
        (6.4, 4.8, 8.7),
        5.4,
    ),
    _wait_leg("2026-10-16T07:10:00+07:00", "2026-10-16T07:12:30+07:00"),
    _subway_leg("2026-10-16T07:12:30+07:00", "2026-10-16T07:37:30+07:00"),
    _walk_leg(
        "2026-10-16T07:37:30+07:00",
        "2026-10-16T07:43:30+07:00",
        360,
        _DUKUH_ATAS,
        _END,
        "~|myJwa}vjEnhCooBfxGf^fpAfpA",
        [31, 33, 32],
        (32, 24, 44),
        (4.4, 3.3, 6.1),
        3.7,
    ),
]

_NO_FACTOR = "exposure_params.yaml: value missing, TODO(verify)"

PLAN_RESPONSE: JsonDict = {
    "request_id": "rq_9f2c4e1a",
    "data_quality": "synthetic",
    "data_freshness": {
        "aq_valid_hour": "2026-10-16T07:00:00+07:00",
        "model_version": "lgbm-2026w42",
        "confidence": "medium",
    },
    "sensitivity": "rentan",
    "options": [
        {
            "option_id": "op_1",
            "labels": ["fastest"],
            "depart_at": "2026-10-16T07:00:00+07:00",
            "arrive_at": "2026-10-16T07:38:30+07:00",
            "duration_s": 2310,
            "transfers": 0,
            "distance_m": 12292,
            "mean_pm25": 53.2,
            "dose_ug": 21.8,
            "dose_ug_p10": 16.1,
            "dose_ug_p90": 29.6,
            "ct_ugh_m3": 25.6,
            "cig_eq": 0.05,
            "daily_dose_share": None,
            "delta_vs_fastest_pct": 0.0,
            "delta_duration_vs_fastest_s": 0,
            "exceeds_profile_threshold": None,
            "co2_kg": None,
            "cost_idr": None,
            "data_quality": "synthetic",
            "legs": _OP1_LEGS,
        },
        {
            "option_id": "op_2",
            "labels": ["cleanest", "balanced"],
            "depart_at": "2026-10-16T07:00:00+07:00",
            "arrive_at": "2026-10-16T07:43:30+07:00",
            "duration_s": 2610,
            "transfers": 0,
            "distance_m": 12652,
            "mean_pm25": 42.8,
            "dose_ug": 17.5,
            "dose_ug_p10": 13.0,
            "dose_ug_p90": 23.8,
            "ct_ugh_m3": 22.0,
            "cig_eq": 0.04,
            "daily_dose_share": None,
            "delta_vs_fastest_pct": -19.7,
            "delta_duration_vs_fastest_s": 300,
            "exceeds_profile_threshold": None,
            "co2_kg": None,
            "cost_idr": None,
            "data_quality": "synthetic",
            "legs": _OP2_LEGS,
        },
    ],
    "comparison": {
        "motorcycle": {
            "duration_s": 3000,
            "distance_m": 13800,
            "mean_pm25": 60,
            "dose_ug": 39.0,
            "dose_ug_p10": 28.6,
            "dose_ug_p90": 52.7,
            "ct_ugh_m3": 65.0,
            "cig_eq": 0.12,
            "co2_kg": None,
            "cost_idr": None,
            "congestion_factor": None,
            "polyline": "vkz~Jg}~sjEwyw@wpQ_ry@_g^_lh@wik@",
            "data_quality": "synthetic",
            "assumptions": [
                {"key": "congestion_factor", "value": None, "unit": "1", "source": _NO_FACTOR},
                {"key": "emission_factor", "value": None, "unit": "kg/km", "source": _NO_FACTOR},
            ],
        },
        "car": {
            "duration_s": 3300,
            "distance_m": 14600,
            "mean_pm25": 60,
            "dose_ug": 12.4,
            "dose_ug_p10": 9.1,
            "dose_ug_p90": 16.7,
            "ct_ugh_m3": 24.8,
            "cig_eq": 0.05,
            "co2_kg": None,
            "cost_idr": None,
            "congestion_factor": None,
            "polyline": "vkz~Jg}~sjEgan@wg]_cmAoh\\os^gqa@",
            "data_quality": "synthetic",
            "assumptions": [
                {"key": "congestion_factor", "value": None, "unit": "1", "source": _NO_FACTOR},
                {"key": "emission_factor", "value": None, "unit": "kg/km", "source": _NO_FACTOR},
            ],
        },
    },
    "disclaimer": "Estimasi model, bukan pengukuran medis.",
}

DEPARTURE_ADVICE: JsonDict = {
    "requested_depart_at": "2026-10-16T07:00:00+07:00",
    "sensitivity": "rentan",
    "mode": "transit",
    "slots": [
        {
            "depart_at": "2026-10-16T06:45:00+07:00",
            "duration_s": 2280,
            "dose_ug": 20.9,
            "dose_ug_p10": 15.4,
            "dose_ug_p90": 28.4,
            "delta_dose_pct": -4.1,
            "delta_duration_s": -30,
        },
        {
            "depart_at": "2026-10-16T07:00:00+07:00",
            "duration_s": 2310,
            "dose_ug": 21.8,
            "dose_ug_p10": 16.1,
            "dose_ug_p90": 29.6,
            "delta_dose_pct": 0.0,
            "delta_duration_s": 0,
        },
        {
            "depart_at": "2026-10-16T07:15:00+07:00",
            "duration_s": 2400,
            "dose_ug": 23.0,
            "dose_ug_p10": 17.0,
            "dose_ug_p90": 31.2,
            "delta_dose_pct": 5.5,
            "delta_duration_s": 90,
        },
    ],
    "best_slot": "2026-10-16T06:45:00+07:00",
    "data_quality": "synthetic",
}

AQ_POINT: JsonDict = {
    "lat": -6.2088,
    "lon": 106.8227,
    "cell_id": "c_0712_0386",
    "valid_hour": "2026-10-16T07:00:00+07:00",
    "pm25": {"p10": 41.0, "p50": 56.0, "p90": 76.0},
    "ispu_category": None,
    "data_quality": "synthetic",
}

AQ_FORECAST: JsonDict = {
    "lat": -6.2088,
    "lon": 106.8227,
    "source": "model_corrected",
    "hours": [
        {
            "valid_hour": "2026-10-16T08:00:00+07:00",
            "pm25": {"p10": 44.0, "p50": 59.0, "p90": 80.0},
        },
        {
            "valid_hour": "2026-10-16T09:00:00+07:00",
            "pm25": {"p10": 40.0, "p50": 54.0, "p90": 74.0},
        },
    ],
    "data_quality": "synthetic",
}

DAILY_SUMMARY: JsonDict = {
    "lat": -6.2088,
    "lon": 106.8227,
    "date": "2026-10-16",
    "mean_pm25": 50.0,
    "cig_eq_day": 2.27,
    "ispu_category": None,
    "data_quality": "synthetic",
}

GREENSPACES: JsonDict = {
    "items": [
        {
            "name": "Taman Langsat",
            "lat": -6.2405,
            "lon": 106.8018,
            "distance_m": 850,
            "pm25_now": 38.0,
            "best_hour_today": "2026-10-16T06:00:00+07:00",
        }
    ],
    "data_quality": "synthetic",
}

KELURAHAN_INSIGHTS: JsonDict = {
    "from": "2026-10-09",
    "to": "2026-10-16",
    "boundaries_version": "kelurahan-2026-10",
    "items": [
        {
            "kelurahan_id": "kel_0001",
            "name": "Gelora",
            "kecamatan": "Tanah Abang",
            "mean_pm25": 52.4,
            "inequality_index": 0.61,
            "priority_rank": 1,
        },
        {
            "kelurahan_id": "kel_0002",
            "name": "Lebak Bulus",
            "kecamatan": "Cilandak",
            "mean_pm25": 47.9,
            "inequality_index": 0.44,
            "priority_rank": 2,
        },
    ],
    "data_quality": "synthetic",
}

HEALTH: JsonDict = {
    "status": "ok",
    "version": "0.1.0",
    "model_version": None,
    "data_age_seconds": None,
    "data_quality": "real",
}

PROBLEMS: dict[int, JsonDict] = {
    400: {
        "type": "validation_error",
        "title": "Permintaan tidak valid",
        "status": 400,
        "detail": "origin.lat: Input should be greater than or equal to -90",
        "request_id": "rq_9f2c4e1a",
    },
    404: {
        "type": "out_of_service_area",
        "title": "Di luar area layanan",
        "status": 404,
        "detail": "Asal atau tujuan berada di luar area pilot Hirup.",
        "request_id": "rq_9f2c4e1a",
    },
    429: {
        "type": "rate_limited",
        "title": "Terlalu banyak permintaan",
        "status": 429,
        "detail": "Coba lagi dalam beberapa saat.",
        "request_id": "rq_9f2c4e1a",
    },
    503: {
        "type": "data_unavailable",
        "title": "Data kualitas udara belum tersedia",
        "status": 503,
        "detail": "Raster PM2.5 terbaru belum tersedia.",
        "request_id": "rq_9f2c4e1a",
    },
}
