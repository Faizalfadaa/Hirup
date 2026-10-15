# Data sources and licences

Required by Lampiran B (Definition of Done). One row per source the data and ML lanes read. Access was checked on 2026-10-13 unless noted. `data/` is gitignored; no source data is committed.

| Source | Used for | Access | Licence and attribution | Code |
|---|---|---|---|---|
| OpenAQ API v3 (`api.openaq.org/v3`) | Historical hourly PM2.5 labels | API key, 60 req/min and 2,000 req/hour | Data from many providers, each with its own licence; attribute OpenAQ and the original provider | `pipelines/.../ingest/openaq.py` |
| WAQI / aqicn (`api.waqi.info`) | Live PM2.5 labels, scraped every 10 minutes | Token | **May not be redistributed.** Internal use as labels only; attribute the World Air Quality Index Project and the originating EPA | `ingest/waqi.py` |
| Open-Meteo forecast and historical-forecast API | Wind, temperature, humidity, rain, boundary layer height | No key | Free for non-commercial use, CC BY 4.0; attribute Open-Meteo | `ingest/openmeteo.py` |
| Open-Meteo Air Quality API (CAMS global) | Regional PM2.5 background and forecast | No key | Non-commercial; CAMS data from Copernicus Atmosphere Monitoring Service / ECMWF, attribute both | `ingest/openmeteo.py` |
| OpenStreetMap: Geofabrik Java extract (`java-latest.osm.pbf`) | Roads, junctions, buildings | Direct download (about 860 MB), shared with `infra/` | ODbL 1.0; "(c) OpenStreetMap contributors", extract by Geofabrik | `ingest/osm.py` |
| OpenStreetMap via Overpass | Kelurahan and kecamatan boundaries; roads and buildings outside the local index | No key; public servers, often busy | ODbL 1.0; "(c) OpenStreetMap contributors" | `ingest/osm.py` |
| ESA WorldCover 2021 v200, 10 m | Land-cover fractions | Public S3 bucket `esa-worldcover` | CC BY 4.0; "(c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium" | `ingest/rasters.py` |
| ESA WorldCover Sentinel-2 NDVI composite 2021, 10 m | NDVI (annual median) | Public S3 bucket `esa-worldcover-s2` | CC BY 4.0, same attribution | `ingest/rasters.py` |
| WorldPop 2020 constrained, Indonesia, about 100 m | Population density | Direct download (about 103 MB) | CC BY 4.0; attribute WorldPop, University of Southampton | `ingest/rasters.py` |
| TransJakarta GTFS, Mobility Database `mdb-1909` | Distance to BRT, scheduled bus trips per cell | Public `latest.zip` | Official feed; attribution, non-commercial competition use (SPEC 6.3) | `ingest/gtfs.py` |

## Notes

- **WAQI values are an AQI sub-index.** They are converted to ug/m3 with the breakpoint table in `pipelines/configs/pipeline.yaml`. The table is marked `verified_by: null`.
- **NDVI** comes from the WorldCover annual composite (2021), not from a fresh Sentinel-2 scene. It is a static feature.
- **Kelurahan boundaries** are OSM `admin_level=7` relations, not the official BIG or DKI dataset named in SPEC 10.1. If P4 obtains the official polygons, replace `data/boundaries/` and bump `boundaries_version`.
- **Not used in Phase A:** Google Air Quality API (paid, storage terms), TomTom Traffic (optional), SPKU history (PPID request pending, Phase B), ISPU daily CSV.
- Derived datasets carry a date in their name, for example `features_static_v2026-10-13.parquet` (Lampiran A).
