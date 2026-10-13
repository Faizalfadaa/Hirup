# tests

**Owner:** P1 · Cross-service tests. Unit tests stay next to the code in `services/*/tests/`.

- `integration/`: API with OTP and OSRM; `contracts/golden_od.json` must always return at least one option. Marked `integration`, needs `make up`.
- `contract/`: schemathesis against the running API.

```bash
uv run pytest -q -m integration tests/integration
```
