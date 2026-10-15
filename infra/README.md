# Hirup routing infrastructure

Current handoff: [backend architecture/privacy](BACKEND.md),
[parameter verification queue](PARAMETER_REVIEW.md),
[Azure deployment preparation](deploy/AZURE.md) and
[production runbook](deploy/RUNBOOK.md).

Linux graph-build containers now use the invoking host UID/GID, including
tools, OSM conversion, OSRM and OTP. This prevents root-owned staged directories
from blocking host-side markers and GitHub cache handling. Windows Docker Desktop
keeps its own permission mapping. Pre-existing root-owned Linux inputs must be
reviewed by their administrator; these scripts do not recursively change owners
or permissions. A fresh hosted cache-miss build and later cache hit remain
required acceptance evidence after publication.

CI engine preflight retries only transport failures (at most three attempts per
variant). Invalid/no-transit responses fail immediately. Its redacted
`initialization.json` records attempts and success/failure even on failure.
Preflight is excluded from latency; timed golden requests never retry.

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

### T6.4a: hourly point forecast

`GET /v1/aq/forecast?lat=...&lon=...&hours=24` returns the next 1–24 complete WIB
hours, starting after the current hour. The requested horizon is complete: there
are no silent gaps or partial success responses. Use the backend on port 8002
with the existing `backend-api` target; the Compose API on port 8000 is still a
placeholder.

The service first samples P10/P50/P90 from loaded P2 COG manifests configured by
the existing `HIRUP_AQ_MANIFESTS` setting. All hours must be `kind: forecast`,
already published, from the same model version and hourly generation cycle,
and consistent with their declared lead hours. Individual raster publications
may finish seconds apart within that cycle. Each sample must match its manifest
quality/model/generation metadata; a final metadata check rejects a publication
change during the window. No current-hour nowcast or raw CAMS value is repeated
as a future forecast. The response source is `model_corrected`, with the worst
input `data_quality` and `X-Data-Age-Seconds` from the oldest raster publication.

If corrected coverage is incomplete or invalid, the entire window falls back
to the already supported `HIRUP_AQ_HISTORY` artifact, using its regional
hour-of-week observation quantiles. This returns `source: historical_mean` and
`data_quality: approximated`, never a mixture of corrected and historical hours.
The observation period must end before today in WIB and cover every requested
hour/location. Because the artifact records dates rather than precise observation
timestamps, its age header is conservative: seconds since WIB midnight at the
start of the final observation day. It is not a newly generated forecast age.

Missing complete coverage returns RFC 9457 `503 data_unavailable`; points outside
the pilot return `404 out_of_service_area`. Horizons outside 1–24 return 400.
No extra request coordinates are cached or logged. Existing hourly/publication
refresh updates COGs and the shared historical input off the event loop; invalid
history retains the previous valid artifact. Files are not reopened per request.

Production refuses synthetic forecasts. The normal `HIRUP_DEMO` route provider
does not manufacture forecast inputs: without corrected/sourced history this
endpoint remains unavailable. Tests explicitly opt into synthetic 2x2 COG
fixtures to verify per-hour quantiles, 24-hour coverage, provenance/publication
changes, historical fallback, freshness headers and the HTTP contract. Those
fixtures are test-only and are never production, model or impact evidence.

```bash
uv run pytest -q tests/test_forecast.py tests/test_advice_aq.py services/api/tests tests/contract
curl --fail-with-body "http://127.0.0.1:8002/v1/aq/forecast?lat=-6.2088&lon=106.8227&hours=24"
```

No new configuration names, dependencies or contract fields are required. Real
P2 forecast artifacts are not present in this checkout, so production validation
remains pending. Daily summary is described below; kelurahan insights remains a
separate subsequent feature.

Final validation passes Ruff lint/format (104 files), strict mypy (56 source
files), lock consistency and 326 non-integration tests, including both live OSRM
profiles. The 30 forecast tests include actual COG IO plus HTTP/schema checks.
Existing rasterio/NumPy deprecations remain visible; contracts and schemas are
unchanged.

The first cold Docker golden replay passed 29/30 with one 06:30 OD02 503 at
approximately 3.25 s. A separate same-query OTP diagnostic observed a 3.22 s
ReadTimeout on walkReluctance 6 while other variants returned itineraries; later
diagnostic replays returned candidates. No routing timeout or variants were
changed. The final full cold replay passed 30/30, with plan p50 642.4 ms/p95
3,933.6 ms, AQ-point p95 3.33 ms and zero plan-cache hits (33 misses including
excluded warm-ups). These seeded-AQ/real-routing checks do not establish the
3-second Should target or production P2 availability.

PostgreSQL/PostGIS and new Rust/Go services remain deferred. Existing native
geodesic/graph libraries are used, with no new dependencies or data downloads.
Production P2 rasters, a deployed VM, and sustained load still require validation.

### T6.4b: complete daily point summary

`GET /v1/aq/daily-summary?lat=...&lon=...&date=2026-10-14` returns the mean of
the 24 hourly P50 values from midnight through 23:00 on the requested WIB date.
Omitting `date` selects today in WIB, including when the UTC date differs.
`cig_eq_day` uses the existing Exposure Engine and the cigarette constant loaded
from `contracts/exposure_params.yaml`. For example, a daily mean of 50 ug/m3
gives `50 * 24 / 528`, about 2.27 cigarettes per day with the current contract.
The API does not infer daily means from a current-hour concentration or average
P10/P90 into P50. `ispu_category` stays null until verified breakpoints exist.

All 24 COG hours must be published, with matching valid hours and sample
quality/model/generation metadata. Nowcasts have zero lead and an hourly
generation cycle matching their valid hour. Future hours require corrected
forecasts with consistent lead hours and one model/generation cycle. Archived
past forecasts may come from distinct completed cycles. A final manifest check
rejects publication changes during sampling. A day containing any forecast has
at least `approximated` quality; explicit test fixtures preserve `synthetic`.
The age header follows the oldest raster publication in the day.

If any hour is missing or invalid, the entire day uses the existing sourced
`HIRUP_AQ_HISTORY` hour-of-week statistics with `approximated` quality. History
must cover all 24 hours and the location, and its observation period must end
before both today and the requested day. Its age uses the same conservative
last-observation-day midnight policy as forecast. There is no partial-day or
mixed-source success response. Without complete COG or historical coverage the
endpoint returns RFC 9457 `503 data_unavailable`; points outside the pilot return
`404 out_of_service_area`. Invalid dates return 400.

Startup and hourly publication refresh share the validated historical artifact
across advice, forecast and daily summary. Invalid historical updates retain the
previous valid artifact. Raster handles are reused, sampling runs off the event
loop, and the endpoint does not cache or log requested coordinates. Production
refuses synthetic COGs; demo mode does not substitute a daily forecast. No new
configuration names, dependencies, contracts, database or data downloads are
required. P2 production artifacts remain unavailable for real-data validation.

```bash
uv run pytest -q tests/test_daily_summary.py tests/test_forecast.py tests/test_advice_aq.py services/api/tests tests/contract
curl --fail-with-body "http://127.0.0.1:8002/v1/aq/daily-summary?lat=-6.2088&lon=106.8227&date=2026-10-14"
```

The daily feature adds 40 tests for hand-computed means/conversion, full-day
coverage, WIB dates, provenance, publication changes, fallback, refresh, actual
synthetic COG IO, HTTP errors and numeric overflow. Final validation passes Ruff
lint/format (107 files), strict mypy (58 source files) and 366 non-integration
tests including both live OSRM profiles. OpenAPI/schema synchronization remains
green and the dependency lock is unchanged. The three opt-in integrations are
deselected in that suite; golden and advice are also exercised by direct runners.
Existing upstream rasterio/NumPy deprecation warnings remain.

The cold-cache Docker golden replay passes 30/30, with plan p50 542.7 ms/p95
2,567.8 ms and AQ-point p95 2.34 ms (zero cache hits, 33 misses including warm-ups).
Advice regression passes 12/12 windows, each with 13 slots, with p50 6,304.1 ms
and p95 9,288.8 ms. These are local real-router/seeded-synthetic-AQ regressions,
not production or impact measurements. Although this golden sample is below
3 seconds, previous runs exceeded it: consistent cold Should performance and
production P2/deployed validation remain open.

### T7.1: bounded live HTTP contract checks

The `contract-http` target runs [Schemathesis 4.31.0](https://pypi.org/project/schemathesis/4.31.0/)
against a running localhost FastAPI server and the frozen `contracts/openapi.yaml`.
The runner compares `/openapi.json` with the frozen document before sending cases.
It covers all four Must operations plus implemented Should operations for advice,
forecast and daily summary. Kelurahan insights is explicitly excluded until its
separate local commit is published/merged; greenspaces remains Could. The report
lists these exclusions instead of claiming whole-API coverage.

Checks cover undocumented status codes, response media types, response header
values, response schemas, server errors and acceptance of generated invalid input.
503 is permitted only where that operation documents it, with the correct Problem
Details media type/body. Other 5xx responses remain failures. Valid input outside
the pilot can legitimately produce the documented 404, and unavailable AQ/routing
can produce a conforming 503. Conformance alone does not prove route availability;
the independent golden OD regression remains required.

Each operation gets a guided case, unchanged schema examples, and seeded positive
and negative fuzzing. The default is at most 20 generated examples per mode and
300 seconds for the whole run, with a 30-second request timeout. Health has no
request inputs, so negative generation is not applicable and its positive
strategy has one unique case. Hypothesis shrinking/database reuse is disabled;
the configured seed and date are recorded for repeatable generation. Upstream
router timing/availability can still vary. The supervising process enforces the
wall-clock budget and fails incomplete runs rather than reporting a partial pass.

Only plain localhost HTTP targets are accepted. Proxy/environment authentication
is disabled for the client, redirects are not followed, and the test server
disables access logs. Reports contain operation templates, phase completion,
status counts and failure class names. They contain no request/response bodies,
precise coordinates, full URLs, curl reproductions or exception messages. Worker
stdout/stderr is captured and discarded; raw VCR/HAR/crash reports and persistent
Hypothesis example storage are not enabled. Reports belong under ignored `data/`.

For full successful-response coverage, use the explicit test-only server below.
It uses actual FastAPI handlers and real Docker OTP/OSRM, a seeded synthetic route
AQ provider, and tiny synthetic COG fixtures for forecast/daily summary. Those
fixtures cover one test point and a fixed 14 October 2026 day; other in-pilot
points can still return 503. All fixture data is labelled synthetic. The normal
production startup has no switch to enable these forecast/daily fixtures.
This is contract/demo evidence, never model, impact or production-AQ validation.
Raster fixtures are opened/closed on a dedicated owner thread and their temporary
files are cleaned on shutdown, while request sampling remains off the event loop.

With the existing routing graphs and healthy Docker stack, run in Git Bash:

```bash
uv sync --locked
unset PROJ_LIB PROJ_DATA  # avoid a conflicting PostgreSQL PROJ installation
uv run uvicorn tests.contract.demo_backend:app --host 127.0.0.1 --port 8002 --no-access-log
```

In a second terminal:

```bash
make -f infra/Makefile contract-http CONTRACT_ARGS="--base-url http://127.0.0.1:8002 --date 2026-10-14 --fixture-aq --seed 20261014 --max-examples 20 --budget-s 300 --output data/contracts/http-conformance.json"
```

`--fixture-aq` additionally requires all seven guided cases to return 200, and
forecast/daily successful responses to retain their synthetic label. Against a
normal local backend, omit that flag: declared 503 is checked for conformance,
not treated as successful availability. Stop the temporary test server with
Ctrl+C before measuring the separate cold-cache golden regression:

```bash
make -f infra/Makefile golden-od GOLDEN_ARGS="--date 2026-10-14 --demo-min-pm25 10 --demo-max-pm25 80 --reference-pm25 40 --trunk-penalty 2 --cold-cache --profile-stages --output data/benchmarks/t7-golden.json"
uv run pytest -q tests/contract/test_runner.py
```

The dev-only dependency adds 11 locked transitive packages, without changing any
existing dependency versions. No production dependency, contract, service handler,
workflow or deployment file is modified in this part. Docker CI and deployment
are subsequent T7 checkpoints. Real P2 data, sustained/deployed performance and
the pending insights integration remain outside this local contract validation.

Final local validation passes Ruff lint/format (110 files), strict mypy (58
source files), lock consistency and 394 non-integration tests, including both
live OSRM profiles. The 28 added checker tests detect corrupt status/media/header/
schema responses, retain proper 503 validation, reject remote targets, fail schema
mismatch/timeouts, redact output, and verify raster-resource shutdown. Three
opt-in integrations are deselected; the direct golden runner exercises Docker.
Existing rasterio/NumPy deprecation warnings and unverified exposure-parameter
warnings remain visible.

The initial HTTP run passed 247 cases but primarily exercised error paths. The
final stronger run passed 254 requests across all seven operations with zero
violations, including guided 200 responses for plan, advice, point, PNG tile,
forecast, daily summary and health. The forecast/daily fixtures explicitly retain
synthetic quality. A first fixture shutdown exposed a cross-thread GDAL environment
error; the dedicated owner-thread lifecycle plus regression test fixes it, and
the final real-server startup/shutdown completed cleanly.

After stopping that test server, cold-cache golden OD passes 30/30 with plan p50
492.5 ms/p95 2,289.0 ms and AQ-point p95 4.20 ms (zero hits, 33 misses including
warm-ups). These real-router/seeded-synthetic-AQ regressions are not production P2
validation or proof of sustained 3-second performance. This branch starts at main
887e57e; the separate, unpushed kelurahan commit/tests remain on the T6 branch.
# Manual Docker regression workflow (T7.2)

`.github/workflows/routing-golden.yml` runs only through `workflow_dispatch`.
After it is merged to the default branch, open **Actions → routing golden
(manual) → Run workflow**. Select the branch and a lowercase `dataset_version`,
for example `2026-10-14-v1`. No push or PR automatically downloads routing data
or starts this job. Running it consumes the repository's Actions allowance.
GitHub requires the dispatch workflow to exist on the default branch:
[manual workflow documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

This job uses `ubuntu-24.04`. The standard private-repository runner has
2 CPUs, 8 GB RAM and 14 GB SSD according to
[GitHub's runner specification](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
The approved CI-only OTP heap is **4g**, both when building and serving the
graph. `infra/ci/compose.yml` caps the runtime container at 5 GiB to leave
headroom for OSRM and the Python test runtime. Normal local/production Compose
and graph builds retain the **8g** default. A 4g build override is rejected
unless `HIRUP_CI_PROJECT` has a `hirup-ci-` prefix. Preflight requires at least
7 GiB host/Docker RAM and 9 GiB free workspace disk before downloads; a smaller
runner fails. Those are policy floors, not a guarantee that every future
dataset fits. OOM, unhealthy engines, or failing tests fail the job.

The graph cache key combines the explicit dataset version with hashes of the
locked Python dependencies, pinned images, graph builders, exposure/grid
helpers, pilot/parameter contracts, OTP configuration, OSRM profiles and
available manual GTFS inputs. Only an exact key is restored. Each graph file
must match its stored size/SHA-256, the artifact inventory must be complete,
and the manifest must match the version/configuration/images and source
provenance. Corrupt or incompatible caches fail instead of silently rebuilding
or accepting another version. Change `dataset_version` to request new inputs;
delete a corrupt cache in GitHub's cache UI or choose a new version.

On a miss, the existing targets download Java OSM and mdb-1909 GTFS, clip to the
pilot, build OSRM/OTP sequentially, then build the active graph. The manifest
records retrieval/build time, source URLs and actual download hashes. Upstream
`latest` URLs are mutable: the same version is stable while its immutable
GitHub cache exists, but rebuilding after eviction can fetch different bytes.
Recorded hashes expose that change; this is not an archival snapshot service.
The raw Java download, temporary active OSM, OTP diagnostic maps, AQ/model
artefacts and secrets are excluded from the cache. Cold downloads are roughly
2–4 GB including images and OSM; a warm run restores only prepared graphs and
their staged feeds/configuration. No production P2 input is required here.

The job starts only OTP/car/motorcycle in its unique `hirup-ci-<run>-<attempt>`
project on loopback ports **18081/5100/5101**. Before HTTP testing, three
sequential OTP queries initialize the JVM/transfer caches; each has a 30-second
limit and must include a real transit leg. This initialization is excluded from
latency evidence and does not change production client timeouts. It then starts the actual FastAPI
handlers on **8003** with test-only seeded synthetic AQ, checks four Must and
three implemented Should endpoints over HTTP, stops that fixture server, and
runs all **10 public golden OD × 3 slots** with a fresh route cache per case.
The fixed fixture/regression date is **2026-10-14 WIB**. One JVM warm-up per
slot is excluded from latency measurements. Plan p95 must be **≤5000 ms** and
AQ point p95 **≤500 ms**; the ≤3000 ms Should target is reported but is not
this workflow's pass threshold. Missing options, schema violations, unexpected
5xx, incomplete fuzz phases and wall-clock overruns fail the job.

Reports in `data/ci/reports/` contain operation templates, status/failure counts,
public pair IDs, response hashes, stage timings and graph-source provenance.
They do not contain response geometry, exact OD coordinates, raw fuzz bodies,
access logs or credentials. Only these JSON reports are uploaded, retained for
7 days even after a test failure. These checks use real Docker routing and
**synthetic AQ**; they are regression/latency evidence, not model evaluation,
production AQ validation or the 50-OD impact report. Insights is still outside
the selected contract set pending its separate publication; greenspaces is Could.
The final `always()` cleanup stops only this CI Compose project and its labelled
graph-build child, without global Docker pruning or stopping `hirup-routing`.

To verify against existing local graphs without downloading or rebuilding them,
use Git Bash from the repository root (the ports above must be free):

```bash
export HIRUP_CI_PROJECT=hirup-ci-local-review
uv run python infra/ci/graphs.py preflight
make -f infra/Makefile ci-config
trap 'make -f infra/Makefile ci-down' EXIT
make -f infra/Makefile ci-up
make -f infra/Makefile ci-test
```

This validates serving at 4g and the checks/cleanup; it does not verify a fresh
4g graph build or the hosted runner's memory/performance. Local graphs built
at 8g must not be presented as a newly built CI cache. `ci-test` requires the
root locked Python test environment (`uv sync --locked`) and launches its own
fixture child without access logs. `ci-down` is also safe to rerun manually with
the same `HIRUP_CI_PROJECT`. Full GitHub cold-build and cache-hit validation must
be recorded after the workflow is published and manually dispatched.

## Production VM package (T7.3)

The portable Ubuntu 24.04/x86-64 deployment, pinned API/Caddy/Nginx images,
production Compose, P2 hourly hook, monitor, and release/rollback procedures are
documented in [the VM runbook](deploy/RUNBOOK.md). The target remains 4 vCPU,
16 GB RAM and OTP heap 8g; the 4g override is isolated local/CI testing only.
The production image needs pinned native libexpat1 for rasterio, uses the existing
uv lock without dev packages, and runs nonroot with a read-only filesystem.

Build locally with `make -f infra/Makefile deploy-image
DEPLOY_API_IMAGE=hirup-api:local-t7-3` and `deploy-test-image
DEPLOY_API_IMAGE=hirup-api-test:local-t7-3`. Use `deploy-local-test` only with a
unique `HIRUP_CI_PROJECT` and an already healthy `ci-up` routing project. It tests
production degraded/503 honesty without P2 inputs, trusted local Caddy TLS,
route 429/Retry-After despite spoofed IP headers, omitted query logs, seven HTTP
contract operations and 30 cold-cache golden cases. It removes its own proxy/API
project and certificate volumes; run `ci-down` in a shell trap/finally block to
clean the routing project. Preview tags and fixture targets are not production
releases. Reports/CA certificate remain under ignored `data/deploy-validation/`.

Real VM/DNS/ACME renewal, SSH/firewall exposure, reboot persistence, P2 timer
execution, real-AQ conformance and production latency still require verification
after choosing a server. No cloud resource is provisioned by these Make targets.

### T6.4c: sourced kelurahan aggregates

`GET /v1/insights/kelurahan?from=2026-10-12&to=2026-10-13` returns the mean
daily P50 for each declared kelurahan over an inclusive WIB date range. Each
day must have complete 24-hour coverage for every region in the boundary
roster. For two complete daily means of 10 and 30 ug/m3, the period mean is
20 ug/m3. This combines daily means of equal duration and a consistent regional
footprint. It does not aggregate route histories or any user-location data.

Set the new `HIRUP_KELURAHAN_SUMMARIES` name to a local UTF-8 JSON publication.
The adapter in `services/exposure/kelurahan.py` validates the internal shape below;
it does not modify the frozen HTTP or raster contracts. P2 must export or adapt
its sourced aggregates to this shape before real-data integration can run.

| JSON field | Required meaning |
| --- | --- |
| `source` | Nonblank provenance for the raster/CAMS inputs and administrative boundaries |
| `aggregation_method` | Nonblank methodology for the spatial hourly P50 aggregation and complete daily means; use the same footprint and weights on every day |
| `units` | Exactly `ug/m3` |
| `boundaries_version` | Version of the static GeoJSON used by the client |
| `regions` | Nonempty list of `kelurahan_id`, `name`, `kecamatan`; IDs are unique and join to that boundary version |
| `days` | Nonempty list of daily records, with unique WIB `date` values |
| `days[].boundaries_version` | Must match the publication's boundary version |
| `days[].generated_at` | ISO 8601 with a timezone; publication must already exist |
| `days[].source_kind` | `model` for model-raster aggregates, or `cams` for sourced CAMS fallback |
| `days[].model_version` | Nonblank for `model`; may be absent/null for `cams` |
| `days[].contains_forecast` | Required boolean; true if any contributing hour is a forecast |
| `days[].data_quality` | `real`, `approximated`, or explicitly test-only `synthetic` |
| `days[].items` | Exactly one item for every roster ID, with `kelurahan_id`, finite non-negative numeric `mean_pm25`, and `hours_covered` |
| `days[].items[].hours_covered` | The integers 0 through 23, each exactly once, in any order; these are WIB hours |

Region metadata belongs to `regions`, while daily concentrations belong to
`days[].items`. Extra fields are rejected. A complete observed daily aggregate
must be generated at or after the next WIB midnight. A current/future day whose
aggregate is published earlier requires `contains_forecast: true`; repeating a
current-hour concentration under a complete-day label is not a valid producer
implementation. Model aggregates require the actual producing model version.
Source and methodology declarations are required, but this adapter does not
independently recompute raster statistics or verify the GeoJSON roster; P2 and
the boundary owner must validate those upstream inputs.

All requested dates must be present, every daily region/hour complete, and all
boundary versions consistent. Missing coverage returns RFC 9457 `503
data_unavailable`, without partial success. Reversed ranges and malformed/missing
dates return `400 validation_error`. Dates outside loaded coverage, including
very wide ranges, return 503 without allocating a calendar for every date.
Returned items are ordered by ID for stability; this is not a priority ranking.

Quality follows the worst requested daily input. A result containing forecasts
or CAMS fallback has at least `approximated` quality. Production refuses any
synthetic day in a publication, even when route demo mode is enabled. The normal
demo provider does not create insights. Tests use a seeded, explicitly synthetic
regional fixture only; its values are not production/model/impact evidence.

Startup loads the configured file off the event loop. The existing metadata
worker also watches this path, including a file first published after startup,
and reloads it after publication changes or the hour changes. Validation happens
before replacement. Missing/malformed/unpublished/synthetic updates retain a
previous valid immutable snapshot; without one, the endpoint stays unavailable.
Each request uses one snapshot, so concurrent refresh cannot blend publications.
The JSON is not read per request, and an invalid regional input does not disable
the planner or the other AQ endpoints. Publish files with an atomic replacement
after writing and validating a complete document.

`inequality_index` and `priority_rank` remain null. **FR-31 is not complete:**
normalization, green-space/population inputs, and an agreed published methodology
are still required. No weights, scientific constants, or priority values are
invented. Real P2 aggregates and compatible static client boundaries are absent
from this checkout, so production FR-30 validation also remains pending.

```bash
uv run pytest -q tests/test_kelurahan.py tests/test_refresh_worker.py services/api/tests tests/contract
curl --fail-with-body "http://127.0.0.1:8002/v1/insights/kelurahan?from=2026-10-12&to=2026-10-13"
```

No dependency, database, raster download or contract change is needed. The only
new configuration name is `HIRUP_KELURAHAN_SUMMARIES` in `.env.example`; keep the
actual path in the uncommitted local environment.

Final validation passes Ruff lint/format (109 files), strict mypy (59 source
files), lock consistency and 427 non-integration tests including both live OSRM
profiles. The 61 new regional tests cover hand-calculated inclusive aggregation,
coverage/provenance/quality, malformed and missing inputs, WIB boundaries,
concurrent snapshot refresh, late publication detection and HTTP errors/schema.
Frozen OpenAPI/schema synchronization is unchanged. Three opt-in integrations
are deselected in the suite; the golden runner separately exercises Docker.
Existing rasterio/NumPy deprecation warnings remain.

The cold-cache Docker golden replay passes 30/30, with plan p50 550.7 ms/p95
2,965.4 ms and AQ-point p95 4.28 ms (zero hits, 33 misses including warm-ups).
It uses real routing engines and explicitly seeded synthetic AQ. This is a
regression sample, not production P2 evidence, and does not establish sustained
3-second Should performance. Real aggregate/boundary validation and FR-31
methodology remain pending.

### Develop: P1/P2 workspace integration

The combined branch uses an atomic `HIRUP_AQ_PUBLICATION` index, immutable COG
runs, sourced historical fallback and complete daily kelurahan aggregates.
See [integration, worker and real-data handoff](deploy/INTEGRATION.md) for the
current setup and limitations. API, P2 worker and fixture-only image targets
are separate. HTTP contract checks now include insights, for eight operations.
`uv run python -m tests.integration.p2_runner` checks all golden OD against
seeded P2 LightGBM/COG outputs and real Docker routing engines. It is explicitly
synthetic integration evidence, not a model-accuracy or impact result.
