# Contracts changelog

Files in `contracts/` are frozen interfaces between lanes. Only P1 changes them, with an announcement to the team and an entry here. Additive, backward-compatible changes bump the minor version; renames, removals and type or unit changes bump the major version.

## 1.0.0 (2026-10-13, H0)

First frozen version.

**`openapi.yaml`** (exported from `services/api/schemas` with `make contract`; never edit by hand)
- Endpoints from SPEC Table 13, each tagged `x-priority`. Must: `POST /v1/routes/plan`, `GET /v1/aq/point`, `GET /v1/aq/tiles/{z}/{x}/{y}.png`, `GET /v1/health`. Should: `GET /v1/routes/departure-advice`, `GET /v1/aq/forecast`, `GET /v1/aq/daily-summary`, `GET /v1/insights/kelurahan`. Could: `GET /v1/greenspaces/nearby`.
- Every successful JSON response carries `data_quality` (`real | approximated | synthetic`). Route options and comparisons carry their own as well.
- Enums: leg `mode` `WALK | BICYCLE | WAIT | BUS | SUBWAY | RAIL | MOTORCYCLE | CAR`; `labels` `fastest | cleanest | balanced`; `sensitivity` `umum | rentan`; plan `mode` `transit | bike | walk | all`.
- Units are part of field names: `duration_s`, `distance_m`, `dose_ug` (+ `_p10`, `_p90`), `ct_ugh_m3`, `cig_eq`, `co2_kg`, `cost_idr`. Times are ISO 8601 with offset (+07:00). Polylines are encoded with precision 6.
- Errors are RFC 9457 `application/problem+json` with `type`, `title`, `status`, `detail`, `request_id`. Validation errors return **400** (not 422). Out-of-area requests return 404 with `type: out_of_service_area`. Every response has an `X-Request-ID` header.
- Clients must ignore unknown response fields. Request bodies reject unknown fields.
- Not-yet-implemented endpoints return 501 `not_implemented` until T5/T6.

**Differences from SPEC 13.2**
- `profile.sensitivity` uses `umum | rentan` (SPEC example said `vulnerable`).
- The example's `duration_s` is 2310 (the sum of its legs, SPEC said 2280) and `transfers` is 0 (one transit leg, SPEC said 1). Dose, CT 25.6 and `cig_eq` 0.05 are unchanged.
- Under `rentan` the cleanest option also has the lowest balanced score, so the example merges the labels (`["cleanest", "balanced"]`) as SPEC 12.4 requires.
- Response field `profile` is `sensitivity`; leg `from`/`to` are objects (`name`, `lat`, `lon`); `route` is an object (`id`, `short_name`, `long_name`, `agency`).

**Nullable until values are verified**
- `daily_dose_share`: needs `daily.f_indoor`, which SPEC 12.5 names but does not give.
- `ispu_category`, `exceeds_profile_threshold`: need ISPU PM2.5 breakpoints.
- `co2_kg`, `cost_idr`, `congestion_factor`: need emission factors, fuel cost, fares and the congestion profile.

**`exposure_params.yaml`**: every entry has `value`, `range`, `unit`, `source`, `verified_by` (all `null`), `note`. F values are the midpoints of the SPEC Table 12.1 ranges. Values that SPEC does not give are `null` with `TODO(verify)`.

**`golden_od.json`**: 10 OD pairs × slots 06:30, 07:30, 17:30 (weekday, WIB) inside the pilot bbox. `validated_by: null`; coordinates still need a map check.

**`schemas/raster_manifest.schema.json`** (P2 → P1): one manifest per hourly raster set: model version, valid hour, nowcast/forecast, EPSG:32748, 100 m, COG paths for P10/P50/P90, `data_quality`.

**`schemas/demo_scenario.schema.json`** (P3 fixtures): one offline demo scenario with `request` and `response` following PlanRequest/PlanResponse. Always `synthetic`, with `seed` and `generator`.

**Kelurahan boundaries** are not sent by the API. `kelurahan_id` joins to a static boundary GeoJSON that ships with the app (`boundaries_version`).
