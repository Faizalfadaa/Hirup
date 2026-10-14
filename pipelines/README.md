# pipelines

**Owner:** P2 · Ingest (OpenAQ, WAQI, Open-Meteo weather and CAMS, OSM, WorldCover, WorldPop, GTFS), QC, calibration and features (SPEC 10, 11.2). Python package `hirup_pipelines`, a uv workspace member. Everything it writes goes to `data/` (gitignored); every step is logged in `data/ingest_runs.parquet`.

## Run

API keys come from the process environment only (never from a file the code reads, never in a prompt). In Git Bash:

```bash
set -a; source .env; set +a          # WAQI_TOKEN, OPENAQ_API_KEY

uv run hirup-pipelines static        # once: static features + kelurahan for the pilot grid (no key needed)
uv run hirup-pipelines stations      # discover stations in the pilot area +/- 10 km
uv run hirup-pipelines openaq --days 90
uv run hirup-pipelines weather --days 90   # archive back-fill, then live + 2-day forecast
uv run hirup-pipelines qc            # QC, merge WAQI mirrors, calibrate -> aq_observations
uv run hirup-pipelines g0            # gate G0 -> data/reports/g0.json
uv run hirup-pipelines station-static
uv run hirup-pipelines loop          # WAQI every 10 min + hourly job, forever (or use cron)
```

Cron alternative to `loop` on the VM:

```cron
*/10 * * * * cd /srv/hirup && uv run hirup-pipelines waqi
5 * * * *    cd /srv/hirup && uv run hirup-pipelines hourly && uv run hirup-ml predict
```

The first `static` run downloads the Geofabrik Java extract (about 860 MB, to `data/osm/`, the same file `infra/scripts/fetch_osm.sh` uses) and parses roads and buildings into a local index in `data/raw/osm/index/`. Allow about 30 minutes once; `uv run hirup-pipelines osm-index` rebuilds it. Kelurahan boundaries, and stations outside the index, still come from public Overpass servers, which are often busy. Their responses are cached in `data/raw/osm/`, so a failed run resumes: run it again.

## Test

```bash
uv run pytest -q pipelines/tests
uv run ruff check pipelines && uv run ruff format --check pipelines
uv run mypy --config-file pipelines/mypy.ini pipelines/src ml/src
```

Tests use `httpx.MockTransport` and a temporary `HIRUP_DATA_DIR`; they never call a real API.

## What it writes (SPEC 10.3)

| Path under `data/` | Contents |
|---|---|
| `raw/stations.parquet`, `raw/observations/date=*/` | As fetched, before QC |
| `stations.parquet` | `station_id, name, type {reference, lcs}, source, provider, lat, lon, active` + `x, y, merged_into, weight, calibrated` |
| `aq_observations/date=*/part.parquet` | `station_id, ts (UTC, start of hour), value_raw, value_cal, qc_flag, source` |
| `weather_hourly.parquet`, `cams_hourly.parquet` | Per lattice point (`cell_group_id`): `wind_u, wind_v, temp, rh, precip, blh` / `pm25_cams` |
| `grid_cells.parquet` (+ `features/features_static_v<date>.parquet`) | GeoParquet, one row per 100 m cell: `cell_id, geometry, kelurahan_id`, static features |
| `features/station_static.parquet` | The same features at each station |
| `boundaries/kelurahan-osm-<date>.geojson`, `boundaries/latest.json` | Kelurahan polygons for the app (`boundaries_version`) |
| `reports/g0.json`, `calibration.json`, `duplicates.json` | Gate G0, calibration coefficients, merged station pairs |
| `ingest_runs.parquet` | `run_id, source, start, end, status, rows, error` |

`cell_id` is `{easting // 100}:{northing // 100}` in EPSG:32748, the same id `GET /v1/aq/point` returns. The pilot grid is the UTM envelope of the bbox in `contracts/golden_od.json`: 102 x 190 = 19,380 cells (SPEC 6.1 estimated about 13,600).

## Rules implemented (SPEC 10.2)

- `qc_flag`: `ok`, `range` (< 0 or > 1,000), `flatline` (>= 6 identical hours), `spike` (> 5 robust sigma from the 24 h rolling median and no neighbour within 3 km moving the same way), `interpolated` (gap <= 2 h, linear).
- Only `ok` rows are labels. `interpolated` rows feed features only. Flagged rows keep `value_raw`; `value_cal` is empty.
- A WAQI station <= 50 m from an OpenAQ station with correlation >= 0.9 is merged into it (OpenAQ wins, WAQI fills gaps).
- Low-cost sensors <= 1 km from a reference station are calibrated per provider with `PM_ref = a*PM_lcs + b*RH + c*PM_lcs*RH + d` once 72 paired hours exist.
- A failed pandera schema check stops the step and is logged with `status = failed`.

Constants live in `configs/pipeline.yaml` with their source.

## Do not

- Do not commit anything under `data/`. WAQI data may not be redistributed.
- Do not put API keys in code, config, logs or AI prompts. HTTP errors are logged with the host only.
- Do not use dummy data here. Fixtures in `pipelines/tests` are for unit tests only (SPEC 10.4).
- Do not change files in `contracts/`; ask P1.

## Open questions (need a human, SPEC 17.3 rule 4)

1. **WAQI AQI table.** WAQI reports a PM2.5 AQI sub-index, converted to ug/m3 with the US EPA 2012 breakpoints in `configs/pipeline.yaml`. Confirm WAQI has not moved to the 2024 revision.
2. **WAQI hour stamp.** It is unclear whether a WAQI reading stamped 08:00 is the hour starting or ending at 08:00. `data/reports/duplicates.json` reports the correlation with the co-located OpenAQ station at -1/0/+1 h; set `waqi.hour_offset_h` if lag 0 is not the best.
3. **Holiday and Ramadan dates** in `configs/pipeline.yaml` were entered from memory and are marked `verified_by: null`.
4. **Reference vs low-cost.** OpenAQ `isMonitor` decides the station type; WAQI stations default to `lcs`.

Not built: TomTom traffic (optional in SPEC 10.1), ISPU daily CSV sanity check, Google Open Buildings (OSM buildings are used).
