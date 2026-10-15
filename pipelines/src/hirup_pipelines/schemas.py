"""Pandera schemas for the SPEC 10.3 tables. A failed check stops the pipeline step."""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

UTC = pd.DatetimeTZDtype("us", "UTC")
QC_FLAGS = ["ok", "range", "flatline", "spike", "interpolated"]
SOURCES = ["openaq", "waqi"]

STATIONS = pa.DataFrameSchema(
    {
        "station_id": pa.Column(str, unique=True),
        "name": pa.Column(str, nullable=True),
        "type": pa.Column(str, pa.Check.isin(["reference", "lcs"])),
        "source": pa.Column(str, pa.Check.isin(SOURCES)),
        "provider": pa.Column(str, nullable=True),
        "lat": pa.Column(float, pa.Check.in_range(-90, 90)),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180)),
        "active": pa.Column(bool),
    },
    strict=False,
    coerce=True,
)

RAW_OBSERVATIONS = pa.DataFrameSchema(
    {
        "station_id": pa.Column(str),
        "ts": pa.Column(UTC),
        "value_raw": pa.Column(float, nullable=True),
        "source": pa.Column(str, pa.Check.isin(SOURCES)),
    },
    strict=False,
    coerce=True,
    unique=["station_id", "ts"],
)

AQ_OBSERVATIONS = pa.DataFrameSchema(
    {
        "station_id": pa.Column(str),
        "ts": pa.Column(UTC),
        "value_raw": pa.Column(float, nullable=True),
        # Rows that pass QC are physically plausible; flagged rows keep their raw value.
        "value_cal": pa.Column(float, nullable=True),
        "qc_flag": pa.Column(str, pa.Check.isin(QC_FLAGS)),
        "source": pa.Column(str, pa.Check.isin(SOURCES)),
    },
    checks=[
        pa.Check(
            lambda df: bool(
                df.loc[df["qc_flag"].isin(["ok", "interpolated"]), "value_cal"]
                .between(0, 1000)
                .all()
            ),
            error="value_cal of usable rows must lie in [0, 1000] ug/m3",
        ),
        pa.Check(
            lambda df: bool((df["ts"].dt.minute.eq(0) & df["ts"].dt.second.eq(0)).all()),
            error="ts must be the start of an hour",
        ),
    ],
    strict=False,
    coerce=True,
    unique=["station_id", "ts"],
)

WEATHER_HOURLY = pa.DataFrameSchema(
    {
        "cell_group_id": pa.Column(int, pa.Check.ge(0)),
        "ts": pa.Column(UTC),
        "lat": pa.Column(float),
        "lon": pa.Column(float),
        "wind_u": pa.Column(float, pa.Check.in_range(-60, 60), nullable=True),
        "wind_v": pa.Column(float, pa.Check.in_range(-60, 60), nullable=True),
        "temp": pa.Column(float, pa.Check.in_range(-10, 55), nullable=True),
        "rh": pa.Column(float, pa.Check.in_range(0, 100), nullable=True),
        "precip": pa.Column(float, pa.Check.ge(0), nullable=True),
        "blh": pa.Column(float, pa.Check.ge(0), nullable=True),
    },
    strict=False,
    coerce=True,
    unique=["cell_group_id", "ts"],
)

CAMS_HOURLY = pa.DataFrameSchema(
    {
        "cell_group_id": pa.Column(int, pa.Check.ge(0)),
        "ts": pa.Column(UTC),
        "lat": pa.Column(float),
        "lon": pa.Column(float),
        "pm25_cams": pa.Column(float, pa.Check.in_range(0, 2000), nullable=True),
    },
    strict=False,
    coerce=True,
    unique=["cell_group_id", "ts"],
)

INGEST_RUNS = pa.DataFrameSchema(
    {
        "run_id": pa.Column(str, unique=True),
        "source": pa.Column(str),
        "start": pa.Column(UTC),
        "end": pa.Column(UTC),
        "status": pa.Column(str, pa.Check.isin(["ok", "failed"])),
        "rows": pa.Column(int, pa.Check.ge(0)),
        "error": pa.Column("string", nullable=True),
    },
    strict=False,
    coerce=True,
)

STATIC_FEATURES = pa.DataFrameSchema(
    {
        "cell_id": pa.Column(str, unique=True),
        "x": pa.Column(float),
        "y": pa.Column(float),
        r"^road_\w+_\d+m$": pa.Column(float, pa.Check.ge(0), regex=True),
        r"^(bldg|wc)_frac_\w+$": pa.Column(float, pa.Check.in_range(0, 1.0001), regex=True),
        r"^ndvi_\w+$": pa.Column(float, pa.Check.in_range(-1, 1), nullable=True, regex=True),
        "pop_density": pa.Column(float, pa.Check.ge(0)),
    },
    strict=False,
    coerce=True,
)


def validate(frame: pd.DataFrame, schema: pa.DataFrameSchema) -> pd.DataFrame:
    return schema.validate(frame, lazy=True)
