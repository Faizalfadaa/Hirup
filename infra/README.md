# Hirup routing infrastructure

This stack builds a pilot street graph for OTP and separate OSRM graphs for cars
and motorcycles. It is the T2 infrastructure lane; the API container is a readiness
placeholder until the backend is merged.

## Requirements

- Docker Desktop with Linux containers on Windows, or Docker Engine on Linux.
- Git Bash on Windows, GNU Make, curl, and Python 3.12 managed by uv for checks.
- The project's OTP heap is 8 GiB. Allow additional RAM for the JVM and Linux.
  A 10 GiB WSL2 limit is a starting point on a 16 GiB laptop, not a guarantee for
  arbitrary datasets. Graphs are built sequentially with runtime engines stopped.
- Budget at least 10 GiB of free disk for downloads, images, graphs, and build
  reports. Java OSM alone is approximately 856 MiB as of 13 October 2026; the
  buffered pilot is much smaller. This disk budget is an estimate.
- The first run requires Internet access. Later runs reuse the downloaded files
  and locally built graphs. Do not build the entire Java extract in OTP or OSRM.

WSL2 memory limits apply to its VM, not to an individual container. See
[Microsoft's WSL configuration documentation](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
and [Docker's WSL2 documentation](https://docs.docker.com/desktop/features/wsl/).
Teammates using the shared API or mobile fixtures do not need a local OTP engine.

## Run

Run these commands from the repository root. On Windows, use Git Bash; quote the
repository path when changing directories because it may contain spaces.
From PowerShell, the bare `bash` command can select WSL instead. Open Git Bash
explicitly; ensure the Windows uv executable's directory is on its `PATH`.

```bash
make -f infra/Makefile infra-help
make -f infra/Makefile infra-config
make -f infra/Makefile data-routing
make -f infra/Makefile graphs
make -f infra/Makefile up
make -f infra/Makefile smoke
```

`graphs` performs OSRM extract -> partition -> customize (MLD) for each profile,
then builds and saves OTP's graph. Runtime startup loads the existing graph; it
does not download inputs or rebuild it. `up` waits for healthy services.

Allow a few minutes for the first download and graph build on a laptop; this is an
estimate until the measurements below are recorded. Download speed and Docker
filesystem performance affect the duration.

```bash
make -f infra/Makefile infra-logs
bash infra/scripts/stack.sh ps
make -f infra/Makefile down
```

`down` stops this Compose project and retains the graph files. A failed build
leaves `data/otp/.build-incomplete`; `up` refuses to load a potentially stale graph.
Rerun `graphs` after fixing the reported error.

## Data and feeds

Pilot bounds, from SPEC 6.1: longitude 106.76 to 106.85, latitude -6.30 to -6.13.
`pyproj.Geod` expands these bounds by 2,000 metres on the WGS84 ellipsoid before
`osmium extract --strategy complete_ways`. Complete ways can have vertices outside
the extraction rectangle so roads crossing its boundary remain connected.

- [Java OSM extract](https://download.geofabrik.de/asia/indonesia/java.html), supplied
  by Geofabrik from OpenStreetMap contributors, under ODbL. Attribute both sources.
- [TransJakarta mdb-1909](https://mobilitydatabase.org/feeds/gtfs/mdb-1909), downloaded
  from Mobility Database's public `latest.zip` archive. The public catalog also
  identifies the publisher URL as `https://gtfs.transjakarta.co.id/files/file_gtfs.zip`.
  This download does not require a Mobility Database API account.
- P4's MRT/LRT feeds in `data_prep/gtfs_manual/` are discovered as ZIP files or
  directories containing `agency.txt`. Source files are never modified.

Basic validation checks required tables, agency timezone, pilot stop coverage,
coordinate ranges, shape references, and route/service/trip/stop references. It
prints counts and the calendar date range. This is not a full GTFS validator.
Check service dates when diagnosing a missing transit route; dates are never
extended or synthesized to make a smoke test pass.

Manual feeds are added as separate `manual-*.gtfs.zip` inputs to OTP. Staging writes
explicit, unique `feedId` values in `build-config.json` so overlapping IDs cannot
corrupt another operator's tables. When
manual MRT/LRT feeds are absent, a visible warning states that only TransJakarta is
loaded. Stops outside the pilot are counted and retained with their complete trip
schedules; only the OSM street graph is spatially clipped. Removing intermediate
stop times would silently change the upstream service.
Manual timetable summaries are marked `approximated` pending P4's provenance;
they are not silently presented as observed measurements.

Downloads go to `data/osm/` and `data/gtfs/`; prepared OTP files go to `data/otp/`;
OSRM MLD files go to `data/osrm/car/` and `data/osrm/motorcycle/`. None belong in
Git. The T0 owner should include `data/` in the root ignore rules when bootstrapping
the repository. Do not use `git add .` while those rules are absent.

Cached downloads are reused. To refresh, move the relevant cached file aside and
run `data-routing` and `graphs` again. Interrupted downloads remain `.part` files
and curl resumes them on retry. Validate and record licenses with the source owner
before redistributing GTFS: the mdb-1909 catalog's license field was blank when
checked. Competition attribution is not evidence of a redistribution license.

## Images and motorcycle assumptions

Runtime image tags are fixed in `infra/images.env`, a non-secret configuration
file. It is explicitly passed to Compose; no `.env` is read.

| Component | Pin |
| --- | --- |
| OTP | `opentripplanner/opentripplanner:2.8.0` |
| OSRM | `ghcr.io/project-osrm/osrm-backend:v5.27.1` |
| Python placeholder/tools base | `python:3.12.13-slim-bookworm` |
| Osmium inside tools image | Debian `osmium-tool=1.15.0-1` |
| Geodesic buffer | `pyproj==3.7.1` |

`hirup-routing-tools:1` is built locally from `infra/tools/Dockerfile`. To rebuild
it explicitly after changing the Dockerfile:

```bash
docker build -t hirup-routing-tools:1 -f infra/tools/Dockerfile infra/tools
```

The car profile wraps the pinned upstream `car.lua` and selects left-hand driving.
The motorcycle profile derives from the same implementation but changes access
and turn-restriction hierarchy to motorcycle, prohibits motorway/motorway_link,
rejects toll ways (including directional and motorcycle toll tags), and blocks
toll-booth nodes. These exclusions are applied at extraction time; requests cannot
accidentally opt back into a toll route. Conservative rejection of either
directional toll tag can remove an otherwise untolled direction.

Motorcycle speeds use the upstream profile's urban default (50 km/h) as a ceiling
on inherited highway speeds and final extracted speeds, including explicit
`maxspeed` tags. This is an **approximation**, not a calibrated Jakarta motorcycle
model. `TODO(verify)`: obtain sourced Jakarta speed measurements before claiming
that these raw durations predict traffic. No hourly congestion multiplier or
exposure computation is supplied by this infrastructure task.

## Endpoints and smoke

Host bindings are loopback-only; containers communicate on the Compose network.

| Service | Host URL | Container URL |
| --- | --- | --- |
| OTP GTFS GraphQL | `http://127.0.0.1:18080/otp/gtfs/v1` | `http://otp:8080/otp/gtfs/v1` |
| OSRM car | `http://127.0.0.1:5000` | `http://osrm-car:5000` |
| OSRM motorcycle | `http://127.0.0.1:5001` | `http://osrm-moto:5000` |
| Placeholder readiness | `http://127.0.0.1:8000/health` | `http://api:8000/health` |

Port 8080 is occupied by another process on the verification laptop, so OTP uses
host port 18080 by default. Internal ports and service names remain unchanged.
Override host ports through `OTP_HOST_PORT`, `OSRM_CAR_HOST_PORT`,
`OSRM_MOTO_HOST_PORT`, and `API_HOST_PORT` when needed. Use the same variables on
every Compose invocation for a given stack.

The placeholder reports `status: placeholder` and rejects product requests with
503 Problem Details. It does not implement the frozen `/v1` API or store request
coordinates. Replace it with the real backend image after T0/T5; do not interpret
its healthy status as evidence that the product API works.

Smoke checks Lebak Bulus to Bundaran HI. It requests up to three OSRM alternatives
and prints raw durations. OTP must return an itinerary containing an actual transit
leg: a walk-only result is a failure. By default departure is tomorrow at 08:00
Asia/Jakarta. To choose an explicit date inside the feed calendar:

```bash
bash infra/scripts/smoke.sh --departure '2026-10-14T08:00:00+07:00'
```

No fixture or invented duration substitutes for a failing engine. All engine
failures are printed and smoke exits nonzero if any engine fails. Health checks
exercise GraphQL on OTP and nearest on each OSRM, rather than merely opening a
TCP port. Every runtime service has `restart: unless-stopped` and a health check.
OSRM runtime logging is limited to warnings/errors to suppress request URLs with
coordinates. The placeholder suppresses HTTP access logs.

## Checks

The infra uv project is independent of the root project owned by T0. Install its
pinned development dependencies and run:

```bash
uv sync --project infra --locked
make -f infra/Makefile infra-check
HIRUP_TEST_OSRM=1 uv run --project infra python -m pytest -q tests/infra/test_osrm_profiles.py
```

The default tests need no network, downloaded graph, or Docker. The opt-in OSRM
regression constructs a small, fixed OSM graph with legal detours and forbidden
shortcuts, builds both MLD profiles in containers, and verifies routing in both
directions plus speed caps. Temporary containers are stopped on exit.

T0/T1 contracts and the exposure engine are now integrated. The root project pins
`pyproj==3.7.1` so its CI can collect the infra package tests as well as backend
tests. The separate infra environment remains available for its own checks.
Contracts and the root Makefile are unchanged by this integration. Golden OD route
integration still requires T5 orchestration; the current planning endpoint is a stub.

## Local verification record

Verified on 13 October 2026 on Windows/Git Bash, Docker Desktop Linux/WSL2,
18 visible CPUs, and approximately 9.71 GiB Docker memory:

- Java PBF download: 898,040,981 bytes; buffered pilot: 30,746,967 bytes.
- TransJakarta archive: 2,497,332 bytes; 240 routes, 700 trips, 8,091 stops,
  including 2,635 inside the pilot. MRT/LRT manual feeds were absent.
- Final sequential build: car 17 seconds, motorcycle 19 seconds, OTP 61 seconds,
  104 seconds total including staging and image checks. Images and OSM were
  already cached for this measurement; the first OSM download took about 94 seconds.
- OTP graph: 44,944,471 bytes. Graph-builder warnings include 3,885 isolated
  stops and 3,882 stops not linked for transfers. Importing a citywide feed against
  clipped streets retains stops outside coverage; this build does not establish
  complete transit stop coverage. Inspect `data/otp/report/` when investigating.
- All four runtime containers were healthy. One post-smoke memory snapshot showed
  OTP about 844 MiB, car 43 MiB, motorcycle 50 MiB, and placeholder 18 MiB. This is
  not a peak-memory measurement and does not establish a lower build requirement.
- `make -f infra/Makefile smoke` succeeded for departure
  `2026-10-14T08:00:00+07:00`: car 801.8 seconds (3 alternatives), motorcycle
  1,053.4 seconds (2 alternatives), and OTP transit 6,585 seconds. The transit
  duration is a TransJakarta-only schedule result; MRT/LRT coverage and travel-time
  realism have not been validated. These are raw engine durations, not a model
  evaluation or the 50-OD impact report.
- `HIRUP_TEST_OSRM=1 make -f infra/Makefile infra-check`: Ruff lint/format passed,
  mypy passed for seven files, and all 42 tests passed, including Docker profile
  and HTTP placeholder/privacy checks. Compose configuration validation passed.
- After integrating T0/T1/T3, backend lint/format checks and strict types passed;
  all 142 backend, contract, and infra tests passed, including the Docker profile
  tests. The 42-test isolated infra suite also passed. Root `pyproj==3.7.1` and its
  lockfile entry were added with approval so CI can run the infra tests. Contracts
  are unchanged. Golden OD contract validation passes; end-to-end route requests
  remain unverified because the product planning endpoint awaits T5.

## Active routing and AQ (T4)

Install the pinned root environment with `uv sync --locked`. T4 adds OSMnx 2.0.6,
rustworkx 0.17.1, rasterio 1.4.3 and shapely 2.1.1; pyproj 3.7.1 is already pinned.
Build once using the existing clipped OSM, without another OSM download:

```bash
make -f infra/Makefile active-graph
make -f infra/Makefile active-benchmark \
  BENCHMARK_ARGS="--iterations 30 --trunk-penalty 2 --reference-pm25 40 --demo-min-pm25 10 --demo-max-pm25 80"
```

`active-graph` runs osmium in Docker to export complete highway ways, then OSMnx
converts the local XML to directed walk/bike edges. Access and mode restrictions,
one-way cycling (including reverse ways and contraflow tags), private nodes and
motorway exclusions are retained. The graph and its edge-to-100-m-cell index are
saved as versioned JSON/gzip under `data/graphs/`, which is ignored by Git. OSM
conditional/time-dependent access tags are not interpreted; confirm access locally.

The benchmark uses real street geometry and **synthetic AQ** with a fixed seed.
Its concentration bounds, reference and trunk preference are explicit illustrative
arguments. Do not use these values as calibrated production parameters or put its
concentrations/doses in model metrics, the 50-OD report, or the pitch.

For T5 integration, load the graph and provider once at startup, then call:

```python
from services.exposure.aq_provider import (
    CogAQProvider,
    FallbackAQProvider,
    IdwAQProvider,
)
from services.routing.active_graph import load_graph
from services.routing.active_params import load_active_params
from services.routing.active_router import ActiveRouter

# data_dir, manifest_paths, station_samples and cams_by_hour come from P2.
graph = load_graph(graph_path)
cog = CogAQProvider(data_dir, manifest_paths, bounds=graph.bounds)
fallback = IdwAQProvider(station_samples, graph.bounds, cams=cams_by_hour)
aq = FallbackAQProvider(cog, fallback)
router = ActiveRouter(
    graph, load_active_params(), aq, trunk_penalty_factor=trunk_preference
)
router.refresh_aq(departure, reference_pm25=city_median_for_hour)
routes = router.plan(origin, destination, departure, mode="WALK")
```

The snippet names externally supplied inputs, rather than fabricating P2 data.
`origin` and `destination` are `services.exposure.geometry.Point(lon, lat)`;
`departure` must include a timezone. Refresh the AQ edge cache before routing a
new hour (including forecast hours), and call `cog.reload(manifest_paths)` when P2
publishes a new set. A failed refresh preserves the previous snapshot; a new-hour
request still requires its own successful refresh. Close the COG provider at shutdown.
Refresh precomputes eight weighted graph views (two modes × four lambdas) to avoid
Python/numpy lookups inside each Dijkstra search. This increases memory use; run
refresh in a startup/background worker, outside request handling. Keep the previous
snapshot available until its replacement is ready. Only one hour is cached here;
orchestration must prepare the required hour or retain an original leg if unavailable.
Each result includes geometry, physical duration, length, sampled PM2.5 quantiles,
quality and merged lambda labels. Unmapped straight connectors are included in
distance and duration and mark an otherwise real result `approximated`.

`CogAQProvider` follows the frozen raster manifest: projected EPSG:32748, aligned
100 m quantile grids and relative paths within `data/`. It samples a pixel window,
rejects nodata or unordered quantiles, and uses the requested hour's nowcast or
forecast. Its `raster_median` covers only that raster extent; it must not be used
as a whole-city reference without evidence of city coverage. Production fallback
uses current supplied stations or CAMS and stays `approximated`; it never invents
background concentrations or automatically switches to synthetic data.

TODO(verify): the contract's active speeds/design parameters have `verified_by:
null`. It provides no numeric trunk penalty. Confirm the explicit trunk preference
and the hourly city median with the owners before production integration. No new
scientific constant or contract field is introduced here.

Orchestration must map `OutOfServiceAreaError` to the contract's 404
`out_of_service_area` Problem Details; handle `AQUnavailableError` and
`NoActiveRouteError` without making the whole multimodal plan fail. These modules
perform no API wiring and keep no origin/destination or result cache.

On this Windows machine, inherited `PROJ_LIB`/`PROJ_DATA` from PostgreSQL selected
an incompatible database for rasterio. Clear them **in the current test shell**
so rasterio uses its bundled database; no system setting needs changing:

```powershell
Remove-Item Env:PROJ_LIB -ErrorAction SilentlyContinue
Remove-Item Env:PROJ_DATA -ErrorAction SilentlyContinue
uv run pytest -q
```

Measured on 13 October 2026 on the same Windows machine: 208,790 nodes,
454,932 directed edges and 17,355 grid cells. A warm Senayan–Setiabudi plan
(all four lambdas, deduplication and final 25 m sampling included) over 30 iterations
had walking p50 197.4 ms / p95 225.6 ms / max 236.5 ms at 3,226.7 m, with three
variants; cycling p50 101.8 ms / p95 119.7 ms / max 125.3 ms at 3,894.7 m, with one
variant. Both satisfy the 300 ms latency target. Startup graph loading and the
9.48-second hourly AQ refresh are excluded from request latency. These local
synthetic-AQ timings do not establish VM latency or COG production performance.
An earlier uncached-weight Make run exceeded the target (walking p95 441 ms);
the final cache implementation and refresh regression test address that overhead.

## Backend request-to-dose integration (T5)

The product backend runs separately from the T2 readiness placeholder while deploy
wiring is prepared. On Windows, use Git Bash from the repository root:

```bash
make -f infra/Makefile up
export HIRUP_DEMO=true
export HIRUP_DEMO_MIN_PM25=10 HIRUP_DEMO_MAX_PM25=80
export HIRUP_DEMO_REFERENCE_PM25=40 HIRUP_TRUNK_PENALTY=2
make -f infra/Makefile backend-api
```

The backend listens on `127.0.0.1:8002` (override `BACKEND_HOST_PORT`). It suppresses
HTTP access logs because query strings can contain locations. Its outbound clients
also suppress request-URL logging. Export process variables explicitly; the backend
does not read `.env`. In a second terminal, verify `/v1/health`, `/v1/aq/point`, and
POST `/v1/routes/plan` using coordinates/time from `contracts/golden_od.json`.
Startup loads the street graph once and prepares current-hour weights before serving.
If a requested hour has no weight snapshot, active routing can use its lambda-zero
geometry and then score it with that hour's AQ. Missing AQ still returns 503.

Demo concentration bounds/reference and the trunk preference above are illustrative
configuration, not calibrated parameters. Demo responses carry `synthetic`, low
confidence and an explicit disclaimer. Demo tiles use a continuous grey scale;
they do not invent ISPU thresholds. Turn demo off for production. With no actual
AQ inputs, production returns `503 data_unavailable`; an outside-pilot origin,
destination, point or tile returns `404 out_of_service_area`.

Production inputs are configured as follows (names are in `.env.example`):

- `HIRUP_DATA_DIR`: data directory, default repository `data/`.
- `HIRUP_ACTIVE_GRAPH`: optional override of `data/graphs/active.json.gz`.
- `HIRUP_TRUNK_PENALTY`: explicit verified cycling preference; active routing is
  disabled until supplied. No numeric production default is invented.
- `HIRUP_AQ_MANIFESTS`: JSON array of P2 manifest paths, including relevant forecast
  hours. Each manifest follows the frozen raster contract and points within the data directory.
- `HIRUP_AQ_INPUTS`: optional sourced adapter JSON with `source`, `data_quality`
  (`real` or `approximated`), `stations` and/or `cams`. Station entries contain
  `point: {lon, lat}`, `valid_hour`, and `pm25: {p10, p50, p90}`. `cams` maps aware
  ISO timestamps to quantiles. This is local adapter configuration, not a new P2 contract.
- `HIRUP_CITY_MEDIANS`: optional sourced JSON mapping aware ISO hours to
  `{value, source}`. Without a reference, exposure scoring still works but active
  optimization retains baseline geometry.
- `OTP_URL`, `OSRM_CAR_URL`, `OSRM_MOTO_URL`: routing engine URLs. Local defaults
  are `http://127.0.0.1:18080/otp/gtfs/v1`, `http://127.0.0.1:5000`, and
  `http://127.0.0.1:5001`.

The startup worker checks publication metadata once a minute and reloads on a new
hour or changed inputs. It catches artefacts published after the hour boundary;
unchanged rasters are not reopened per request. Reload errors retain prior data and
never enable synthetic production fallback. Forecast data age uses its generation
timestamp, rather than treating a future valid hour as newly generated data.

Supply pre-rendered, verified ISPU-coloured PNGs under
`data/tiles/YYYYMMDDHH/z/x/y.png` for production. Missing tiles return 503. Point
categories and warning thresholds remain null while the frozen ISPU breakpoint
value is null. Emissions, fares, fuel costs and daily dose share likewise remain
null when their contract inputs are unverified. Road comparisons expose raw OSRM
estimates with a null congestion factor and an explicit assumption until a sourced
hourly profile is supplied. `TOMTOM_API_KEY` is reserved by bootstrap; this T5
configuration uses the contract profile and does not send coordinates to TomTom.

OTP calls the three walk-reluctance variants concurrently. With complete feeds it
uses all, rail-first and bus-only sets; the actual TransJakarta-only feed collapses
equivalent mode sets and skips missing rail. The departure search window is 30
minutes, `numItineraries=5`. This bounds a search strategy rather than changing
exposure parameters. Candidates still obey the requested walking limit and contain
actual transit legs. Headways come from GTFS frequencies or active timetable
intervals, including calendar exceptions, stop offsets and service times after
midnight. Unknown headways cause that candidate to be dropped, never fabricated.

Expected WAIT legs use headway/2. Result timelines represent expected travel with
those waits, rather than a promise to board a specific realtime departure. Trip
exposure and ranking remain pure, use contract values, preserve quantile ordering,
and merge identical labels. CO2/cost assumptions are separate from route ranking.
There is no persistent origin/destination or result cache in T5; the 10-minute
cache, departure advice and other Should endpoints remain T6 work.

Run the real-routing integration/latency check (no new OSM download):

```bash
make -f infra/Makefile golden-od \
  GOLDEN_ARGS="--date 2026-10-14 --demo-min-pm25 10 --demo-max-pm25 80 --reference-pm25 40 --trunk-penalty 2 --output data/benchmarks/t5-latency.json"
HIRUP_TEST_GOLDEN=1 uv run pytest -q -m integration tests/integration/test_golden_od.py
```

The runner uses in-process HTTP requests through ASGITransport to the FastAPI app;
its clients make network calls to the Docker OTP/OSRM stack. It checks 10 OD ×
three slots with the default 1,000 m
walking limit, response schema, option count and per-leg dose totals, then measures
AQ point latency. Graph loading/hourly refresh and one public-pair JVM warm-up per
slot are excluded from timed requests; API serialization and exposure calculation
are included. This does not measure a deployed VM, TLS or production COG latency.
The marked test is opt-in; default CI performs no download or live routing calls.

Verified locally on 13 October 2026 for departures on 14 October: **30/30 golden
requests passed**, at least one option each. The final Make run measured plan p50
1,130.5 ms/p95 4,759.6 ms and point p95 9.03 ms; maximum plan latency was 5,555.2 ms.
An earlier warm run measured plan p50 621.5 ms/p95 4,290.8 ms and point p95 2.13 ms.
These local runs meet the p95 Must targets; the p95 3-second Should target awaits T6.
Routing data is real, AQ explicitly synthetic: these measurements
must not feed model metrics, the 50-OD impact report or dose claims in the pitch.
Early uncapped OTP searches timed out; the final bounded search passed all pairs.
The retained readiness placeholder now consumes/discards bounded POST bodies before
responding, avoiding reproduced Windows socket resets without storing coordinates.
Native TCP HTTP was also checked: health and point returned 200; a warmed plan
returned 200 with one option and ten dose-bearing legs. A cold native plan first
returned 503 while routing searches exceeded their timeout. Engine warm-up and
production latency must be checked on the deployed host; no fixture substitutes
an engine failure. The temporary local backend used for this check was stopped.

## Departure advice (T6, first feature)

`GET /v1/routes/departure-advice` plans 13 departures, spaced 15 minutes from the
requested `around` time (inclusive ±90 minutes). The center preserves the requested
minute/second. Each slot compares the balanced option for the requested sensitivity,
with P10/P50/P90 dose, duration, and signed changes against the center slot.
Negative dose change means lower dose. The best slot minimizes P50 dose, then
duration, then distance from the requested time. Road comparisons are omitted.
Two slot plans at a time share a semaphore across advice requests. No OD, route
result or advice response was cached in the T6.1 baseline measured below. T6.2
adds caching of plans for approximate grid representatives, as described next.

Production uses sourced current/past-hour AQ; future hours require a published
`kind: forecast` raster manifest from P2. Raw future CAMS or a repeated current
nowcast is not presented as corrected forecast advice. The fallback is observed
regional hour-of-week statistics labelled `approximated`, never an invented trend.
Synthetic advice is confined to the explicit seeded demo mode described above.

Set `HIRUP_AQ_HISTORY` to an internal JSON adapter file under ignored `data/`.
This adapter does not change the frozen API or P2 raster contract. Required fields:

| Field | Required value/content |
| --- | --- |
| `source` | Nonempty title/URL identifying the actual observation source |
| `data_quality` | `approximated` |
| `units` | `ug/m3` |
| `period_start`, `period_end` | ISO dates bounding the observed period, in order |
| `bbox_wgs84` | `min_lat`, `max_lat`, `min_lon`, `max_lon` of the regional statistics |
| `hours` | Map from `weekday:HH` to `{p10, p50, p90}`; Monday=0, Sunday=6 |

Quantiles must be finite, nonnegative and ordered, calculated from the declared
observations by the data lane; this service only reads them. Regional statistics
are spatially uniform within their stated bbox and approximate local exposure.
No extrapolation occurs for missing weekdays/hours or outside the artifact bbox.
The observation period must end before both today and the requested day. Lookup
uses Asia/Jakarta, including midnight/week boundaries. Files load at startup and
on changed publication metadata in the hourly worker. A missing/malformed history
file retains prior valid history and does not block regular AQ refresh. The plan
and point services keep their existing policy; the stricter forecast/history
policy applies to advice only.

All 13 slot plans must succeed. Missing routing/AQ coverage produces 503 Problem
Details instead of partial advice or synthetic production data. Outside-area OD
returns 404. If the center dose is zero and another slot is positive, the required
percentage is undefined and the endpoint returns 503; all-zero windows have zero
deltas. Production historical/forecast inputs and deployed-host latency remain
unverified. Advice performs 13 plans and has its own latency; it is not the
single-plan p95 target.
Active routing keeps the T5 hourly weight cache: unprepared hours use baseline
geometry scored with that hour's advice AQ. Future-hour active weight preparation
is not performed inside the advice request.

With `make backend-api` running and sourced inputs configured:

```bash
curl --get http://127.0.0.1:8002/v1/routes/departure-advice \
  --data-urlencode 'origin_lat=-6.2891' --data-urlencode 'origin_lon=106.7745' \
  --data-urlencode 'destination_lat=-6.2088' --data-urlencode 'destination_lon=106.8227' \
  --data-urlencode 'around=2026-10-14T07:30:00+07:00' \
  --data-urlencode 'mode=transit' --data-urlencode 'sensitivity=rentan'
```

To validate the window and measure local advice latency (no downloads):

```bash
uv run python tests/integration/advice_runner.py --date 2026-10-14 \
  --demo-min-pm25 10 --demo-max-pm25 80 --reference-pm25 40 --trunk-penalty 2 \
  --output data/benchmarks/t6-advice-latency.json
HIRUP_TEST_ADVICE=1 uv run pytest -q -m integration tests/integration/test_departure_advice.py
```

As in the golden runner, these values are explicit test/demo inputs, not verified
scientific assumptions. The runner uses one public golden OD at 07:30 and 17:30,
three modes and two sensitivities (12 advice requests, each with 13 slot plans).
It checks schema, synthetic label and center deltas. Graph load/hourly preparation
and one transit warm-up per time are excluded; slot routing, scoring and HTTP
serialization are included. The small sample is a local diagnostic, not production
latency evidence, a model score or an impact claim. Ordinary tests need no Docker
or external AQ artifact. Cache, plan optimization and other T6 endpoints are
separate features.

Local verification on 13 October 2026 for departures on 14 October: all 12 advice
requests passed with 13 slots each. Advice p50 was 6,535.8 ms and p95 8,779.4 ms
(maximum 9,147.9 ms). This is separate from the single-plan target; no cache or
variant pruning was introduced in this feature. Production COG/historical timing
remains unverified.

The accompanying 30-case golden regression replay passed: plan p50 848.9 ms,
p95 4,217.3 ms and point p95 4.66 ms. The p95 3-second Should target remains open;
this replay does not demonstrate an optimization change.

## Plan cache (T6, second feature)

The runtime now wraps plan generation in an in-process LRU cache: 600-second
monotonic TTL, at most 128 completed entries and 16 distinct in-flight jobs per
cache. Identical simultaneous requests share one computation. A caller disconnect
does not cancel a computation needed by another caller. Failed requests are not
cached; excess distinct in-flight work returns 503. Plan and advice use separate
caches because their AQ fallback policies differ. Cached advice now plans one slot
at a time: each slot already fans out OTP variants. This avoids the six simultaneous
OTP searches produced by overlapping bus-only slots. The T6.1 baseline above used
two slots concurrently.

To meet the location minimization rule, requests are planned from deterministic
centers of 100 m EPSG:32748 cells, clamped to the pilot bbox. Exact incoming
coordinates are used only to identify the cells, never passed to a retained job
or saved with the result. The same cells produce the same representative query
regardless of the precise pin location. Cached objects contain domain results,
not HTTP responses, request IDs or users. Serialization creates a new request ID
for each reply.

This changes route endpoints to approximate locations, with quality at least
`approximated` (synthetic remains synthetic) and an Indonesian location note on
plan responses. A representative can be on a different side of a physical barrier;
users must check access from their actual location. Very short trips within one
cell can collapse to the same endpoint. The input coordinates are not restored
into cached polylines. This behavior was explicitly approved for the pilot.

The key includes origin/destination cells, local-equivalent 15-minute slot,
the exact timezone-normalized departure/arrival time, profile, mode, max walking
distance, excluded modes, transfer preference, arrival/departure direction and
comparison preference. Requests at different exact times do not share a transit
result even within the same slot: simply shifting a cached timetable can miss a
service. Consequently default-now requests with distinct timestamps often miss;
the cache benefits repeated searches with the same selected departure time.

AQ publication refresh, including history/reference changes or partial failures,
invalidates both caches. Preparing new active weights also invalidates results.
Versioned in-flight work cannot refill the cache after invalidation; it retries
against the new generation once, then returns 503 if inputs keep changing. Cached
data is immutable. Workers/processes have separate caches; cross-process sharing
is not provided. TTL expiry is enforced on lookup, with expired entries removed
on insertion; memory remains bounded even during idle periods.

The schema, graph loading and sourced AQ policies are unchanged. PostgreSQL/PostGIS
and additional Rust/Go services remain options to evaluate after profiling shows
a concrete need. Neither was added for this cache feature.

Measure cache misses, repeated hits, eight identical simultaneous requests and
four distinct requests on public golden OD:

```bash
uv run python tests/integration/cache_runner.py --date 2026-10-14 \
  --demo-min-pm25 10 --demo-max-pm25 80 --reference-pm25 40 --trunk-penalty 2 \
  --output data/benchmarks/t6-cache-latency.json
HIRUP_TEST_CACHE=1 uv run pytest -q -m integration tests/integration/test_plan_cache.py
```

The report distinguishes miss/hit/burst latency and verifies response schemas,
quality labels and dose sums. It uses real Docker engines and explicit seeded AQ
for integration/latency only. Graph loading and hourly preparation are excluded.
These small bursts are a diagnostic, not a production capacity or throughput
claim. Production COG performance and deployed-host load remain unverified.

The dedicated local run succeeded for all 122 recorded requests:

| Phase | Requests | p50 | p95 |
| --- | --- | --- | --- |
| Empty cache, unique public OD | 10 | 978.6 ms | 3,317.4 ms |
| Repeated cache hits | 100 | 9.33 ms | 13.70 ms |
| Identical concurrent misses | 8 | 1,037.3 ms | 1,043.1 ms |
| Distinct concurrent misses | 4 | 5,885.8 ms | 6,124.9 ms |

The identical burst performed one upstream plan with seven joined callers.
The distinct burst exceeds the 5-second Must target on this host; the cache does
not solve the CPU/upstream cost of unrelated new searches. Admission/rate limits,
further profiling and deployed-host validation remain necessary before claiming
production capacity. The 10-case miss p95 also remains above the 3-second Should
target. Do not combine the hit and miss samples into a headline latency figure.

Profiling found repeated active-leg graph searches among transit candidates. The
planner now reuses identical endpoint/mode/hour searches within a single request,
including unavailable searches, while checking each leg's original detour bounds.
The memo is discarded before responding; it stores no coordinates across requests.
No candidate mode, walk-reluctance variant, or itinerary count was removed.

The API runtime also bounds initial transit departure searches to 15 minutes,
rather than the previous 30-minute window. This is an operational search tradeoff:
departures beyond that window may no longer be candidates. It does not change the
13-slot ±90-minute advice window, and is not a GTFS or exposure constant. Revalidate
coverage when new GTFS feeds or service patterns arrive. Direct OTP client defaults
remain separate from this runtime setting.

On this host, the first cache regression replay passed 29/30 cases with one OTP
timeout; an exact-coordinate diagnostic also timed out for the same case. A longer
diagnostic timeout exposed roughly 6.84 s of OTP generation and 1.75 s of downstream
processing in one primary-only experiment. A 15-minute search restored 30/30
options but initially measured plan p95 6,206.4 ms, above the Must target. After
request-local active-search reuse, Make golden-od again passed 30/30 and the Must
latency gates: plan p50 1,067.9 ms/p95 3,758.4 ms and AQ point p95 4.28 ms.
The golden runner's one-pair warm-up now primes that pair's cache, so this replay
mixes three hits with 27 misses; the dedicated runner separates them. The p95
3-second Should target for new searches remains open. These observations do not
prove deployed-host capacity or model accuracy.

Post-cache advice regression initially passed 10/12 windows: both evening transit
windows returned 503 under combined slot/routing/graph load. An isolated scan
found generated routes with GTFS headways in all 13 evening slots. After limiting
cached advice to one slot at a time, the full direct runner passed 12/12 windows,
13 slots each, across both profiles and transit/walk/bike. Cold advice p50 was
10,179.4 ms/p95 13,937.2 ms (maximum 14,471.6 ms). This is slower than the T6.1
baseline and remains a user-experience/performance concern; reliability of this
local replay does not establish production availability. Repeated identical advice
can use its plan cache, but this run measures fresh windows, not cache hits.

### T6.3: cold-plan profiling and optimization

Run an explicitly cold plan-cache replay, with optional per-stage wall times:

```bash
make -f infra/Makefile golden-od GOLDEN_ARGS="--date 2026-10-14 --demo-min-pm25 10 --demo-max-pm25 80 --reference-pm25 40 --trunk-penalty 2 --cold-cache --profile-stages --output data/benchmarks/plan-profile.json"
```

`--cold-cache` clears both plan caches before each recorded request. Each of the
three slots still has one excluded JVM warm-up; all 30 measured plans are cache
misses, and the counters show 33 misses and zero hits. Graph startup and hourly
preparation are excluded. `--profile-stages` temporarily instruments the local
runtime and restores its methods afterwards, including on failure. Without this
flag the profiling wrappers are absent. The report contains public OD IDs,
status, latency, response fingerprints and stage times, rather than user location
logs. Nested and concurrent stage times overlap and must not be summed.

The original cold replay passed 30/30 with p50 988.3 ms/p95 4,304.1 ms. The slowest
public OD had approximately 2.2–3.3 s in OTP, 0.8–1.0 s in active optimization,
and 0.7–1.0 s in scoring. Much of the scoring time was the seeded synthetic AQ
provider; this timing does not represent production COG reads.

The implementation keeps the OTP mode/reluctance variants, five itineraries,
15-minute runtime search window, 25 m sampling, scientific parameters, and ranking
rules. It uses vectorized geodesic inverse/forward operations; request-owned
geometry and exact-time AQ sample memos; request-owned graph paths keyed by nodes,
mode, lambda and immutable AQ snapshot; and overlapping original scoring/active
optimization. Connector geometry and each leg's detour limits are recomputed.
Snapshot changes clear graph search reuse even within the same hour. No such
memo survives a request on the planner or active router.

For geometry-only fallback in hours whose AQ graph is not prepared, the router
can also reuse an already loaded lambda-zero graph's native float weights. Those
weights are exactly the static travel-time/trunk-preference costs and contain no
hourly pollution weighting. AQ is still sampled at each leg's requested time in
the scorer. If no snapshot has ever been prepared, the original base network is
used. Tests verify identical fallback paths/durations before and after different
hourly publications for both active modes, without extra AQ reads.

Road comparisons are scored while OTP is searching. Alternatives are evaluated
in stable duration order until the first with AQ coverage, preserving fastest
covered selection and ties while avoiding scoring slower covered alternatives.
The main and road workers own separate scoring contexts; original and optimized
main candidates share a context only after the original scorer has finished.

Intermediate 30-case cold replays all passed: p95 3,649.9 ms after geometry/scoring
reuse, 3,315.6 ms after overlapping road work and graph search reuse, and 3,068.4 ms
after overlapping main scoring/optimization. These are separate local runs and
include normal OTP/host timing variation; they are not production capacity claims.
The 3-second target was still missed in these runs.

Numerical tests compare scalar and vectorized geodesics to within 1 micrometre,
including duplicates, short segments, noninteger spacing and a dateline crossing.
A local diagnostic replay also fixes the generated candidates for the heaviest
public OD, three slots and both profiles: all six responses match the previous
main implementation in geometry, labels and data provenance, with numeric
tolerance max(1e-8, abs(value) * 1e-12). One separate live OTP run produced a
different option count; identical-candidate replay prevents that upstream
variation from hiding a scoring regression.

The final source replay passes 30/30 cold plans and 122/122 cache/burst requests.
The comparable local measurements are:

| Measurement | Before | Final |
| --- | --- | --- |
| Cold plan, 30 cases, p50 | 988.3 ms | 816.9 ms |
| Cold plan, 30 cases, p95 | 4,304.1 ms | 4,315.9 ms |
| Dedicated cold plan, 10 cases, p95 | 3,317.4 ms | 3,234.5 ms |
| 100 cache hits, p95 | 13.70 ms | 21.69 ms |
| Eight identical concurrent misses, p95 | 1,043.1 ms | 1,284.4 ms |
| Four distinct concurrent misses, p95 | 6,124.9 ms | 3,795.8 ms |

The final AQ-point p95 is 7.04 ms. The identical burst still performs one upstream
plan with seven joined callers. The distinct burst meets the 5-second Must target
in this small sample, while the final cold 30-case p95 is effectively unchanged.
The earlier 3,068.4 ms replay does not establish a consistent 3-second Should
result. Cached and identical-burst timings also varied and were higher in the
final run; they are reported rather than omitted. New-search tail latency remains
open and should be reassessed with production AQ and the deployed routing host.

Advice regression passed 12/12 windows with 13 slots each, across both profiles
and transit/walk/bike. Its first post-optimization run measured p95 18,959.5 ms.
After lambda-zero fallback reuse, the final replay measured p50 10,248.2 ms/p95
12,876.6 ms, versus the T6.2 p95 13,937.2 ms. Timing variation remains visible;
this is a local regression check, not an advice SLA or availability guarantee.
The lambda-zero change affects geometry fallback; the cold transit golden/cache
cohorts above do not invoke that fallback.

Final source checks pass: Ruff lint and format (102 files), strict mypy (55 source
files), and 296 non-integration tests including both live OSRM profiles, with
three marked Docker integrations deselected and exercised by the direct runners
above. Existing rasterio/NumPy deprecation warnings remain. Contract/schema and
dependency lock files are unchanged.

PostgreSQL/PostGIS and new Rust/Go services remain deferred. Existing native
geodesic/graph libraries are used, with no new dependencies or data downloads.
Production P2 rasters, a deployed VM, and sustained load still require validation.
