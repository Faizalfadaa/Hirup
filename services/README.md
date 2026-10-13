# services

**Owner:** P1 · FastAPI modular monolith. Spec chapters 9, 12, 13.

| Package | Scope |
|---|---|
| `api/` | HTTP layer (`/v1`), Pydantic schemas, RFC 9457 errors. No math. |
| `routing/` | OTP and OSRM clients, walk/bike router, generate-and-rerank, Pareto labels. |
| `exposure/` | Exposure Engine: pure dose, cigarette-equivalent and daily-share functions. |

Dependency direction: `api -> routing -> exposure`. Unit tests live next to the code in `<package>/tests/`.

```bash
make lint typecheck test
make api    # uvicorn on :8000, GET /v1/health
```
