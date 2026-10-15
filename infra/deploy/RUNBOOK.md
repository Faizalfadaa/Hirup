# Hirup VM deployment

The deploy package targets a dedicated **Ubuntu 24.04 x86-64 VM, 4 vCPU,
16 GB RAM**, with OTP heap **8g** and at least 10 GiB free disk after inputs
are staged. It works on Azure or another provider's Ubuntu VM. Choose a disk
with room for images, OSM/GTFS, routing graphs, P2 artefacts and their retention.
Use persistent disk, not ephemeral VM storage. This package does not provision
cloud resources or assume an Azure subscription has a particular VM quota.

An Android APK runs on the phone; this server hosts its API and routing/data
processes. Vercel/Cloudflare Pages can host a separate project website.
PostgreSQL/PostGIS remains a future stack decision, not a deploy prerequisite.

## Before deployment

1. Verify cloud quota, current price, remaining credit, and the required uptime
   period. Include disk, public IP and traffic in the budget. Azure Student credit
   is finite; consult [Azure Student](https://azure.microsoft.com/en-us/free/students/)
   and the [pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/).
2. Create the chosen VM manually. Keep the existing SSH key/port. In the cloud
   firewall/NSG, allow SSH from your administration address and public TCP 80/443.
   API 8000, OTP 8080 and OSRM 5000 stay unpublished.
3. Point the API domain's DNS A record to the VM. Add AAAA only if IPv6 is tested.
   Use DNS-only records initially; a CDN proxy requires an explicit trusted-proxy
   configuration before client-IP rate limits can remain correct.
   Caddy needs reachable 80/443 and persistent certificate storage for
   [automatic HTTPS](https://caddyserver.com/docs/automatic-https).
4. Install the reviewed Git checkout at `/opt/hirup/current`. Use a merged,
   reviewed commit. Preserve credentials outside the repository.
5. Obtain validated routing graphs, feeds and the sourced P2 publication inputs.
   The reviewed P2 entrypoint is `hirup-ml hourly`; stage its real inputs/model
   before enabling that timer. See [integration and handoff](INTEGRATION.md).

No production success can be claimed until real AQ inputs and public TLS/VM
checks pass. A 200 health response with `status: degraded` is not readiness.

## Bootstrap the chosen VM

Read `bootstrap.sh` and `firewall.sh` first. Run in the VM's existing SSH session,
substituting its current SSH port:

```bash
cd /opt/hirup/current
sudo bash infra/deploy/bootstrap.sh 22
```

Bootstrap installs Docker from its official apt repository, creates UID/GID
10001 for the API/P2 data owner, preserves existing UFW rules and allows the
active SSH port before enabling inbound denial. It refuses another application's
running containers and a mismatched active SSH port. It does not change sshd,
passwords or keys. Test a second SSH connection before closing the first one.

Docker published ports bypass ordinary UFW filtering; the dedicated
`HIRUP-INGRESS` chain in `DOCKER-USER` admits only TCP 80/443 and established or
internal bridge traffic. A systemd unit reapplies that chain with Docker startup.
Only Hirup's own chain/jump is managed; no global flush/prune is performed.
See [Docker firewall documentation](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
The package's IPv6 filtering is applied if Docker has an IPv6 DOCKER-USER chain;
verify both IPv4 and IPv6 exposure on the actual VM.

## Prepare inputs and private settings

Copy validated data to `/var/lib/hirup/data`, retaining the established layout:
`otp/`, `osrm/car/`, `osrm/motorcycle/`, `graphs/`, P2 rasters/manifests, fallback
inputs, history, city medians and `tiles/`. Keep P2 publications atomic and keep
the previous valid artefacts on a failed run. Do not put personal route histories
or exact user OD in server files. Pipeline-created files must be readable by
UID 10001; the API mounts this directory read-only.

Copy `infra/deploy/deploy.env.example` to `/etc/hirup/deploy.env` and fill it on
the server, not in Git. Restrict the filled file to root (mode 0600). Values:

- `HIRUP_DOMAIN`: bare API domain.
- `HIRUP_API_IMAGE`: commit-tagged or digest-pinned API image for initial setup.
- `HIRUP_DATA_HOST`: `/var/lib/hirup/data`.
- `HIRUP_AQ_PUBLICATION`: `/data/aq_publication.json`, the preferred atomic P2 index.
- `HIRUP_AQ_MANIFESTS`: JSON array of stable publication paths **inside** `/data`.
- `HIRUP_AQ_INPUTS`, `HIRUP_AQ_HISTORY`, `HIRUP_CITY_MEDIANS`: sourced JSON paths
  inside `/data`, when supplied by P2. Do not invent input values.
- `HIRUP_TRUNK_PENALTY`: the agreed routing strategy value, not a fabricated
  scientific constant. Exposure parameters still come from the frozen contract.

Production Compose explicitly sets `HIRUP_DEMO=false`; synthetic rasters or
fallback inputs are rejected. Missing real inputs yield documented 503 or a
degraded health response. COG startup/reload/shutdown share one owner thread.

## Build and validate an API release

From the exact reviewed source commit, with a clean worktree:

```bash
test -z "$(git status --porcelain)"
revision="$(git rev-parse HEAD)"
make -f infra/Makefile deploy-image DEPLOY_API_IMAGE="hirup-api:$revision"
sudo python3 infra/deploy/ops.py preflight
sudo python3 infra/deploy/ops.py config --image "hirup-api:$revision"
```

The production image uses the root `uv.lock`, pinned Python/uv images and no dev
packages. Its native `libexpat1=2.5.0-1+deb12u4` supplies rasterio's required
`libexpat.so.1`; Python dependencies are unchanged. A Dockerfile-specific ignore
file excludes data, models, .env, Git and
internal documents from the build context. The runtime is nonroot/read-only with
temporary storage and no access logs. Test fixtures are only copied into the
separate `integration` target. Never publish that target as a production image.
If built elsewhere, transport the image through an approved registry or
`docker save`/`docker load`; never paste registry credentials into this chat/Git.

## Start or deploy again

```bash
sudo python3 infra/deploy/ops.py release \
  --image "hirup-api:$revision" --url https://api.example.com
```

The helper uses only project `hirup-prod`, waits for container health, refreshes
the gateway's API DNS, then checks the public TLS endpoint. It accepts readiness
only with `status=ok`, production quality and data age <=90 minutes (the monitor
threshold is an operational guard, not the freshness SLA). Successful image
references are stored privately in `/var/lib/hirup/releases`. `latest` and local
preview tags are rejected. A failed update attempts the previously successful
API image and retains a nonzero exit status. A first failed deployment has no
previous image to restore and is reported as such; inspect inputs/health.

Caddy publishes HTTPS, then proxies to internal Nginx and the API. Caddy replaces
the client-IP header before the gateway uses it. Routing budgets are operational
defaults: plan 10/minute with burst 5, advice 3/minute with burst 2. Rejection is
429 RFC 9457 JSON with Retry-After. AQ/health are not given a new 429 status,
because their frozen contract does not declare it. Access/request-error logging
is disabled at the proxies so URLs containing locations are not persisted.

## Monitor uptime and enable P2 only when ready

Create `/etc/hirup/monitor.env` (root-owned, group hirup, mode 0640) with
`HIRUP_PUBLIC_URL=https://api.example.com`; `monitor.env.example` lists the name.
Then:

```bash
sudo systemctl enable --now hirup-monitor.timer
systemctl list-timers 'hirup-*'
journalctl -u hirup-monitor.service --since '1 hour ago'
```

The monitor distinguishes fresh `ok`, degraded/stale/synthetic AQ and unreachable
HTTPS. Reports contain only time/status/data age/quality, not the URL, client IP
or coordinates. It does not send email/Slack or provision an external monitoring
account. Someone must inspect failures during the operational period; production
restart policies and health checks keep containers running but do not fix bad data.

After staging the reviewed P2 environment and real inputs, place its **argv JSON array**, starting with
an absolute executable path, at `/etc/hirup/pipeline-command.json`. Place private
tokens in `/etc/hirup/pipeline.env` (root-owned, group hirup, mode 0640). No shell
command string is executed. Confirm the P2 environment is installed and outputs
match the frozen raster provenance/schema and the configured API paths. Then:

```bash
sudo systemctl start hirup-pipeline.service
sudo systemctl enable --now hirup-pipeline.timer
journalctl -u hirup-pipeline.service --since '1 hour ago'
```

The oneshot runs as UID 10001, with a 55-minute job timeout and only data-directory
write access. Systemd prevents overlapping instances. The schedule is hourly in
Asia/Jakarta, without replaying missed historical runs. Missing configuration is
not a successful inference job. Raw job output is discarded; a structured exit
status is journalled. Test the exact P2 command manually when debugging its data
failure, taking care to keep tokens out of captured output.

## Inspect, restart, rollback

For container operations, always supply the same explicit env files/project:

```bash
sudo docker compose --project-name hirup-prod \
  --env-file infra/images.env --env-file infra/deploy/images.env \
  --env-file /etc/hirup/deploy.env -f infra/deploy/compose.yml ps
```

Use the same command prefix with `logs --tail 80 api otp`, or `restart api`.
If API/gateway containers were replaced, use `up -d --force-recreate --no-deps
gateway caddy` to resolve the API again. Health/readiness and image-state checks
are required after manual recovery. Full raw routing engine logs are not uploaded
as test artefacts; use them only for administrator troubleshooting.

```bash
sudo python3 infra/deploy/ops.py rollback --url https://api.example.com
```

Rollback restores the previous API image, not P2 data, graphs, secrets or a VM
snapshot. Keep compatible publication artefacts and the previous image until the
new release has been verified. Do not remove certificate/data volumes. Avoid
`docker system prune`, broad process kills and restarting another Compose project.

## Local validation and remaining VM checks

Build `deploy-image` with a local preview tag and `deploy-test-image` with
`hirup-api-test:local-t7-3`. The test-only `local.compose.yml` uses Caddy internal
TLS on :8443, loopback API ports :8003/:8004, the seeded AQ fixture and the separate
CI routing network. It does not run bootstrap/UFW/systemd or trust the local CA in
the host OS. See `tests/integration/deploy_runner.py`; normal user containers are
not stopped. The local 4g OTP test override does not change production heap 8g.

Actual VM quota/cost, SSH/firewall exposure, public DNS/ACME renewal, persistent
volumes across reboot, timer execution and real P2 health/golden/latency must be
verified after a server is selected. Local synthetic AQ is regression/demo
evidence only, never model/impact validation.
