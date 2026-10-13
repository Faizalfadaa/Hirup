"""Shared types for the v1 contract.

Units live in field names (`_s` seconds, `_m` metres, `_ug` micrograms, `_ugh_m3` ug*h/m3).
Times are ISO 8601 with an explicit offset; the API emits Asia/Jakarta (+07:00).
Coordinates are WGS84. Polylines use Google encoded polyline with precision 6.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DataQuality(StrEnum):
    """real: measured or model output from real data. approximated: fallback derived from
    real data (IDW, CAMS, historical mean). synthetic: seeded dummy data, demo only."""

    REAL = "real"
    APPROXIMATED = "approximated"
    SYNTHETIC = "synthetic"


class IspuCategory(StrEnum):
    BAIK = "baik"
    SEDANG = "sedang"
    TIDAK_SEHAT = "tidak_sehat"
    SANGAT_TIDAK_SEHAT = "sangat_tidak_sehat"
    BERBAHAYA = "berbahaya"


class Sensitivity(StrEnum):
    """Profile from SPEC 12.4. Changes alpha, cleanest tolerance and warning threshold."""

    UMUM = "umum"
    RENTAN = "rentan"


Latitude = Annotated[float, Field(ge=-90, le=90, examples=[-6.2088])]
Longitude = Annotated[float, Field(ge=-180, le=180, examples=[106.8227])]
Pm25 = Annotated[float, Field(ge=0, description="PM2.5 concentration in ug/m3")]
Polyline6 = Annotated[str, Field(description="Encoded polyline, precision 6")]


class ContractModel(BaseModel):
    """Base for response models. Clients must ignore unknown fields so additive changes
    stay backward compatible."""

    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)


class RequestModel(ContractModel):
    """Base for request bodies: unknown fields are rejected with 400."""

    model_config = ConfigDict(extra="forbid")


class LatLon(ContractModel):
    lat: Latitude
    lon: Longitude


class Pm25Quantiles(ContractModel):
    p10: Pm25
    p50: Pm25
    p90: Pm25
