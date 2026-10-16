"""Build a lightweight sourced AQ fallback from ingested Parquet data."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def iso_hour(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0).isoformat()


def main() -> None:
    observations = DATA / "aq_observations" / "date=*" / "part.parquet"
    stations_path = DATA / "stations.parquet"
    cams_path = DATA / "cams_hourly.parquet"
    if not stations_path.is_file() or not list(
        (DATA / "aq_observations").glob("date=*/part.parquet")
    ):
        raise SystemExit("Data AQ belum ada. Jalankan ingest dan QC terlebih dahulu.")

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    with duckdb.connect() as con:
        station_rows = con.execute(
            """
            WITH latest AS (
                SELECT station_id, ts, value_cal,
                       row_number() OVER (PARTITION BY station_id ORDER BY ts DESC) AS rank
                FROM read_parquet(?)
                WHERE qc_flag = 'ok' AND value_cal IS NOT NULL
            )
            SELECT s.lon, s.lat, l.value_cal
            FROM latest l
            JOIN read_parquet(?) s USING (station_id)
            WHERE l.rank = 1 AND s.merged_into IS NULL
            """,
            [observations.as_posix(), stations_path.as_posix()],
        ).fetchall()
        cams_rows = (
            con.execute(
                """
                SELECT ts, median(pm25_cams)
                FROM read_parquet(?)
                WHERE pm25_cams IS NOT NULL
                GROUP BY ts ORDER BY ts
                """,
                [cams_path.as_posix()],
            ).fetchall()
            if cams_path.is_file()
            else []
        )

    stations = []
    for lon, lat, value in station_rows:
        pm25 = max(0.0, float(value))
        stations.append(
            {
                "point": {"lon": float(lon), "lat": float(lat)},
                "valid_hour": iso_hour(now),
                "pm25": {"p10": pm25, "p50": pm25, "p90": pm25},
            }
        )
    cams = {}
    for timestamp, value in cams_rows:
        pm25 = max(0.0, float(value))
        cams[iso_hour(timestamp)] = {"p10": pm25, "p50": pm25, "p90": pm25}

    target = DATA / "aq_inputs.json"
    target.write_text(
        json.dumps(
            {
                "data_quality": "approximated",
                "source": "QC-passed OpenAQ/WAQI observations and Open-Meteo CAMS",
                "generated_at": datetime.now(UTC).isoformat(),
                "stations": stations,
                "cams": cams,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {target}: {len(stations)} stations, {len(cams)} CAMS hours")


if __name__ == "__main__":
    main()
