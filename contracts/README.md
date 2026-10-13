# contracts

**Owner:** P1 · Interfaces between lanes, frozen at H0 (v1.0.0). Changes only through P1 with a team announcement and an entry in `docs/contracts-changelog.md`.

| File | Used by | Contents |
|---|---|---|
| `openapi.yaml` | P3 app, P1 API | API v1. Exported from `services/api/schemas` by `make contract`; do not edit by hand |
| `exposure_params.yaml` | P1 Exposure Engine | F, VR, 528 µg·h/m³, daily VR, ranking and routing parameters, each with source and `verified_by` |
| `golden_od.json` | P1 integration tests | 10 OD pairs × 3 time slots in the pilot bbox |
| `schemas/raster_manifest.schema.json` | P2 writes, P1 reads | Manifest for each hourly PM2.5 COG set |
| `schemas/demo_scenario.schema.json` | P3 fixtures | Offline demo scenario (always `synthetic`) |

```bash
make contract   # regenerate openapi.yaml after changing services/api/schemas
make mock       # Prism mock server from openapi.yaml on :4010
uv run pytest -q tests/contract services/api/tests/test_openapi_sync.py
```
