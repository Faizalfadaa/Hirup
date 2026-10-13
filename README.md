# Hirup

Android app (Flutter) and Python backend that plan multimodal trips in Jakarta (TransJakarta, MRT, LRT, walking, cycling, with motorcycle and car as comparisons) and rank them by inhaled PM2.5 dose, not only travel time. The technical specification is in `docs/SPEC.md`.

## Repository

| Path | Owner | Contents |
|---|---|---|
| `apps/mobile/` | P3 | Flutter app |
| `contracts/` | P1 | Frozen API contract, schemas, exposure parameters, golden OD |
| `services/` | P1 | FastAPI backend: `api`, `routing`, `exposure` |
| `infra/` | P1 | Docker Compose, OTP, OSRM |
| `tests/` | P1 | Integration and contract tests |
| `ml/`, `pipelines/` | P2 | PM2.5 model, ingest and features |
| `data_prep/gtfs_manual/` | P4 | MRT/LRT GTFS |
| `fixtures/` | P3 | Seeded demo data |
| `design/`, `docs/` | P4 | Figma exports, specification |
| `data/` | | Local data, gitignored |

## Quickstart

Needs `uv`, GNU `make`, Docker and Node (for the mock server). On Windows use Git Bash.

```bash
make setup                   # Python 3.12 environment via uv
make lint typecheck test
make api                     # http://localhost:8000/v1/health
make mock                    # mock API from contracts/openapi.yaml on :4010
```

Copy `.env.example` to `.env` for API keys; never commit `.env`.
