# P1/P2 integration on develop

The frozen API and raster manifest contracts are unchanged. Real model metrics
and production readiness still require actual P2 artefacts and human verification.

## Workspace and publication

```bash
uv sync --locked
make lint typecheck test
make -f infra/Makefile infra-check
```

`hirup-pipelines` and `hirup-ml` are workspace members; the lock also retains
Schemathesis. After P2 has staged real inputs and supplied credentials through
the process environment, `uv run hirup-ml hourly` performs ingest/QC and inference.
This command accesses external services; it is not a fixture/demo command.

`uv run hirup-ml env` prints configuration paths. The preferred API inputs are
`HIRUP_DATA_DIR` and `HIRUP_AQ_PUBLICATION=<data>/aq_publication.json`. Production
Compose defaults to `/data/aq_publication.json` inside its read-only data mount.

The index is an internal adapter. Version 1 contains `generated_at`, relative
`manifests`, `fallback`, `medians`, optional `history`/`kelurahan`, and
`tiles_available`. All paths must stay inside the data root. It is atomically
replaced only after every run-local file is written. API refresh polls this
pointer every minute, validates inputs and invalidates route caches. COG
open/reload/close stay on the owner thread. An absent first publication can
recover without restarting the configured routing runtime.

Rasters live in immutable `rasters/run_<WIB-hour>_<unique-run-id>/` directories.
Same-hour retries never overwrite open files. The index retains seven days of
observed nowcasts and the current forecast cycle. Legacy fixed slots remain
available, but new deployments use the index. The API nofile limit accommodates
the retained readers. Invalid refresh retains the prior valid inputs.

## Honest coverage and fallbacks

- Point/routing use hourly COGs with sourced station/CAMS fallback.
- Forecast/advice require model-corrected forecasts. The numeric manifest metric
  `forecast_model_corrected=0` identifies uncorrected IDW/CAMS future fields;
  these use observed history instead, or 503 if coverage is insufficient.
- `history.json` uses QC-passed regional station means grouped by WIB weekday/hour
  and empirical P10/P50/P90. Current dates are excluded. This spatially coarse
  fallback is labelled `approximated` and carries the observation period/source.
- Daily summary requires all 24 WIB hours, otherwise the whole day uses sourced
  historical statistics. Partial days are never presented as complete days.
- `kelurahan_daily.json` supplies P1's complete-day adapter, with a consistent
  boundary roster/version, model/publication provenance and all 24 hours for
  every region. Incomplete days are omitted; date ranges with gaps return 503.
  Forecast/current days have quality at least `approximated`.
- Inequality fields in the API remain null. P2's proposed index is not activated.
- Production tiles return 503 while ISPU `verified_by` is null. Test/demo
  greyscale tiles are explicitly synthetic; no scientific constants were invented.

## Separate API and hourly-worker images

```bash
make -f infra/Makefile deploy-image DEPLOY_API_IMAGE=hirup-api:<reviewed-commit>
make -f infra/Makefile deploy-pipeline-image DEPLOY_API_IMAGE=hirup-pipeline:<reviewed-commit>
make -f infra/Makefile deploy-test-image DEPLOY_API_IMAGE=hirup-api-test:local-review
```

The `api` target has workspace manifests for locked resolution but no ML runtime
or fixtures. The `pipeline` target installs P2 and native
`libgomp1=12.2.0-14+deb12u1`; its command is `hirup-ml hourly`. It sets
`HIRUP_PROJECT_ROOT=/app` so installed packages find source configs/contracts.
Mount shared data read-write for the worker and read-only for the API. The
`integration` target includes dev packages and fixtures; never deploy it as API.

For the existing systemd hook, install a reviewed Python 3.12 environment ahead
of time with `uv sync --locked --no-dev --package hirup-ml`. Its argv JSON is:

```json
["/opt/hirup/current/.venv/bin/hirup-ml", "hourly"]
```

Set `HIRUP_DATA_DIR=/var/lib/hirup/data` in the private pipeline environment.
The hook disables bytecode writes and uses temporary Matplotlib configuration.
Alternatively use the separate worker image through an approved scheduler.
This integration does not grant the service user Docker administrator privileges
or enable a live timer.

## Real handoff still required

P2 must supply versioned model binaries, `meta.json`, validation/OOF reports,
the registry entry and checksums, plus real pipeline inputs or a way to obtain
them. With a custom data root the worker expects `models/<model-version>/` and
`model_registry.json` there. Metrics committed to Git do not install a model.
The API needs the indexed raster publication, not model binaries. Do not commit
credentials or redistribute restricted observations.

ISPU, WAQI conversion/time alignment, inequality methodology and existing
exposure constants still need the responsible humans' verification. P2's
registered metrics are not independently reproduced by fixture tests.

## Cross-lane validation

```bash
uv run pytest -q -m "not integration"
uv run python -m tests.integration.p2_runner
```

The second command uses existing Docker OTP/OSRM ports and public golden OD.
It trains on seeded toy observations, publishes actual COG files labelled
`synthetic`, and feeds P1's real COG reader, active router, scoring and API.
Ignored reports are under `data/develop-validation/`; temporary models are
removed. Results are integration evidence, never model accuracy or impact metrics.

The test-only HTTP app `tests.integration.p2_backend:app` supports the
eight-operation contract runner with seeded date 2026-10-14. Production API
configuration cannot activate it. Unit tests cover hand-computed history and
regional means, gaps, same-hour retry, interrupted publication, path confinement,
synthetic rejection, late startup and failed refresh. Real artefact/VM/TLS and
production latency checks remain separate acceptance work.
