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
