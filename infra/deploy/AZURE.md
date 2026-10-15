# Azure deployment preparation

This is a deployment decision and preparation guide, not evidence of a live
service. Use the existing [runbook](RUNBOOK.md) for bootstrap, release, rollback,
firewall, TLS and timer operations. No cloud resources are created by this guide.

## Recommended starting point

Use one dedicated Ubuntu 24.04 x86-64 VM with 4 vCPU, 16 GiB RAM, persistent
storage and the existing Compose stack. Keep OTP heap at 8g in production.
`Standard_D4s_v5` is one matching Azure size, not a quota or price guarantee;
[Microsoft lists it as 4 vCPU / 16 GiB](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/dsv5-series).
Select a size actually available to the subscription and chosen region.

This choice reuses the tested topology and keeps graph/raster storage close to
the API. A managed database is not required by the current file-based backend.
A future PostGIS or Rust/Go change should follow measured workload needs and
its own migration plan. A separate static project website can be hosted elsewhere.

## Subscription owner worksheet

Have the subscription owner fill these locally before any resource creation.
Do not put subscription identifiers, credentials or contact details in Git.

| Decision | Record locally |
|---|---|
| Credit | Remaining credit, expiration date, spending limit |
| Region and size | Available x86-64 size; total and VM-family vCPU quota |
| Storage | Persistent disk size/type; allowance for inputs, images and retained COGs |
| Network | Public IP cost, DNS ownership, traffic allowance, administration IP |
| Duration | Required service uptime and deletion/retention date |
| Budget | VM + disks + IP + traffic + backup, calculated for the whole duration |
| Access | Named administrator and SSH key already held by that administrator |

[Azure for Students](https://learn.microsoft.com/en-us/azure/education-hub/about-azure-for-students)
describes a $100 credit valid for one year for eligible students. Check the
actual account balance and terms; this is not unlimited free VM hosting.
[vCPU quotas](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas)
apply both regionally and by VM family. A listed size can still be unavailable.

Use the [pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
with the selected region and uptime. Do not use a generic monthly price as a
quote. [Budget alerts](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets)
notify about consumption; they do not stop resources automatically.

## Ordered preparation

1. Obtain the worksheet decisions and approve the actual resource cost.
2. Provision only the chosen VM and persistent disk. Use the runbook's network
   rules: SSH from the administration IP, public TCP 80/443, internal engines.
3. Point an owned API domain to the VM. Begin with DNS-only records so proxy
   trust and per-IP limits retain their documented behavior.
4. Install a reviewed source revision, build immutable API/worker images and
   transfer validated routing graphs. Verify graph checksums and feed validity.
5. Stage the real P2 handoff using [INTEGRATION.md](INTEGRATION.md). The API
   consumes the atomic publication; the worker needs model files and inputs.
6. Validate Compose, health/data age and API operations. Missing AQ must remain
   degraded/503; never enable synthetic data in production to pass readiness.
7. Test real public TLS, forbidden-port exposure, second SSH login, reboot,
   hourly publication/refresh, rate limits, redacted logs and rollback.
8. Measure golden latency on that VM with the real publication. Keep synthetic
   integration reports separate from model validation and the 50-OD impact report.

## Acceptance evidence

Record the reviewed revision/image digests, UTC/WIB timestamp, resource size,
graph/data versions, public TLS result, health quality/data age, timer result,
restart/reboot/rollback result and golden report. Keep private infrastructure
details and raw logs out of published reports. A successful local fixture run
does not satisfy these production checks.

If quota or budget prevents this VM, evaluate another persistent Linux host
with the same resource requirements before changing application architecture.
Never reduce production memory to the CI-only 4g exception without a separate
measurement and decision. Do not promise production readiness until the real
data and server acceptance checks have passed.
