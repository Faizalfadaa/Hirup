# ml

**Owner:** P2 · LightGBM PM2.5 nowcast on the 100 m pilot grid (SPEC 11). Python package `hirup_ml` in `src/`, settings in `configs/model.yaml`, evaluation notebook in `notebooks/`. Writes hourly COG rasters (P10/P50/P90) described by `contracts/schemas/raster_manifest.schema.json`.

Model files (`ml/models/`) and data are gitignored. `ml/model_registry.json` holds metrics only and is committed.

## Run

Needs the tables from `pipelines/README.md` first.

```bash
uv run hirup-ml baseline            # B1 IDW (LOSO) and B0 CAMS -> data/reports/baseline.json
uv run hirup-ml train               # Optuna (30 trials) + LOSO + quantiles; promotes if it earns it
uv run hirup-ml train --trials 0    # same, config defaults, no tuning
uv run hirup-ml predict             # this hour: 25 raster sets, manifests, tiles, insights
uv run hirup-ml hourly              # reviewed ingest/QC -> complete P2 publication
uv run hirup-ml predict --at 2026-10-16T07:00:00+07:00
uv run hirup-ml insights --from 2026-10-09 --to 2026-10-16 --hours 6 7 8
uv run hirup-ml status              # model registry
eval "$(uv run hirup-ml env)"       # export the variables the API reads, then `make api`
```

## Test

```bash
uv run pytest -q ml/tests           # about 2 minutes; trains small models on seeded toy data
```

`ml/tests/test_ml_predict.py` loads the published manifests with P1's own `CogAQProvider`, so a contract break fails here first.

## Hand-off to the API (P1)

`hirup-ml env` prints the preferred `HIRUP_AQ_PUBLICATION` index path together
with data and legacy input paths. New backend/deploy code consumes the atomic
`data/aq_publication.json`, which points at one complete immutable run plus
retained observed nowcasts. It also supplies sourced history and complete daily
kelurahan aggregates. See [P1/P2 integration](../infra/deploy/INTEGRATION.md).

For compatibility, `HIRUP_AQ_MANIFESTS` remains a fixed list of 28 files in `data/manifests/`:

| File | Content |
|---|---|
| `nowcast.json` | Current hour T |
| `nowcast_minus_01..03.json` | The three previous nowcasts |
| `forecast_plus_01..24.json` | T+1 .. T+24 |

Legacy empty slots repeat the current nowcast with its actual valid hour; they
do not fabricate a missing forecast. Rasters now live in immutable
`data/rasters/run_<yyyymmddhh>_<run-id>/pm25_<yyyymmddhh>_<p10|p50|p90>.tif`.
Retries within the same hour never overwrite files open in the API. The index
is committed only after run-local fallback/median/history/aggregate files exist.

Also written each run:

- `data/tiles/<yyyymmddhh>/<z>/<x>/<y>.png` for the nowcast and the next hour, zoom 10 to 15, the path `GET /v1/aq/tiles` serves.
- `data/aq_inputs.json` (`HIRUP_AQ_INPUTS`): station readings and CAMS per hour, the API's own IDW fallback.
- `data/city_medians.json` (`HIRUP_CITY_MEDIANS`): median of the pilot raster per hour (C_ref, SPEC 12).
- Run-local `history.json`: observed regional hour-of-week quantiles, labelled
  approximated. Current dates and interpolated labels are excluded.
- Run-local `kelurahan_daily.json`: P1's daily/provenance adapter, with 24-hour
  coverage for every declared region. Incomplete days are omitted. The API now
  serves this adapter and leaves inequality fields null.
- `data/insights/kelurahan_latest.json`: the older offline proposal output from
  `summarise(start, end, hours)`. The backend does not serve its proposed index.

Production tile rendering is skipped while `tiles.ispu.verified_by` is null;
the indexed backend also refuses those tiles. Human verification is required.

## `data_quality`

| Value | When |
|---|---|
| `real` | An active LightGBM model produced the raster |
| `approximated` | No active model, or the drift alarm fired: IDW of station readings, CAMS where no station reports |

This lane never writes `synthetic`. With no labelled data at all the fallback band has zero width and the manifest says `interval_available: 0`.

## Model and validation (SPEC 11.3 to 11.5)

- **M1** LightGBM L2, published as P50. **M1-Q** quantile models at 0.1 and 0.9 for P10/P90, widened by a conformal offset learned in LOSO.
- **Baselines** B1 IDW (p = 2) and B0 CAMS, scored on the same rows. B2 kriging is not built.
- **LOSO**: one fold per station; the IDW features are rebuilt without the held-out station. Also a 2 km spatial block CV and a 20% temporal hold-out. A source hold-out runs when `validation.holdout_station_ids` lists stations.
- **Monotone constraints**: P50 cannot fall as `road_trunk_*` rises or rise as `ndvi_mean_*` rises. LightGBM does not allow constraints on quantile models, so P10/P90 are clamped around P50 instead.
- **Promotion**: a model becomes active only if its LOSO RMSE is below IDW (gate G2) and not more than 5% worse than the active model.
- **Feature contributions**: LightGBM's built-in TreeSHAP (`pred_contrib`), saved as `shap_summary.json`. The `shap` package is not a dependency.
- Each trained model saves `validation.json` (error by road class, hour, ISPU category, rush hour) and `oof.parquet` next to its binaries; `notebooks/evaluation.ipynb` plots them.

## Inference (SPEC 11.6)

- The nowcast for hour T uses station readings carried forward at most 3 hours.
- Forecast hours use forecast weather and CAMS; the station IDW field is scaled by the CAMS trend (clipped to 0.5 to 2x). This is a stand-in until the Phase B forecast model. Forecast intervals are not widened with lead time.
- Post-processing: clip to [0, 500], Gaussian smoothing (sigma = 1 cell), then P10 <= P50 <= P90.
- Drift: rolling 24 h RMSE of published nowcasts against later station readings. Above 1.5x the LOSO RMSE the run falls back and is labelled `approximated`.
- Retention: nowcasts 7 days, forecasts of the last 3 runs, tiles 6 hours, daily mean P50 archived in `data/rasters/daily/`.

## Insight Kota index (FR-31)

For kelurahan with at least half their area in the pilot grid: percentile rank of mean PM2.5 (E), one minus the rank of green cover from WorldCover tree + low vegetation (G), rank of WorldPop density (P); index = (E x G x P)^(1/3). Rank 1 is the highest priority. Boundaries are OSM `admin_level=7`; `kelurahan_id` is `osm_r<relation id>`.

## Do not

- Do not report metrics from toy or dummy data. Numbers for the deck come from `model_registry.json` only.
- Do not edit `model_registry.json` by hand.
- Do not change the manifest schema or file naming without P1.

## Needs a human check

- ISPU PM2.5 breakpoints and colours in `configs/model.yaml` (`verified_by: null`); they drive tile colours and the error analysis by category.
- The inequality index formula is a P2 proposal; P4 should confirm it before it goes in the deck.
