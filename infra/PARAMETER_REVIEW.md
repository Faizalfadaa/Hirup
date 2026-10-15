# Parameter review and data handoff

The frozen contract remains unchanged. This worksheet collects review tasks and
source candidates; it does not verify constants or authorize filling missing
values. Human reviewers must read the original source, choose applicability to
Jakarta and record the reviewed value, unit, range, source/version and reviewer.

## Priority review queue

| Input | Current effect | Review evidence needed |
|---|---|---|
| ISPU PM2.5 | Production tiles unavailable; categories not invented | Regulatory limits, interpolation, rounding, averaging period and treatment of hourly model fields |
| Mode micro-environment factors and ventilation | Initial contract values emit verification warnings | Original study/table, exposure setting, activity, population, units and uncertainty |
| Cigarette equivalent | Uses existing contract constant | Original concentration-time communication rule and limitations; not an individual health prediction |
| Indoor factor and daily mean | Daily dose share can be null | Sourced indoor/ambient assumption and complete-day AQ coverage |
| Emission factors | CO2 can be null | Vehicle-km vs passenger-km, occupancy, CO2 vs CO2e, fuel/technology and geographic applicability |
| Transit fares | Cost can be null | Current operator rules by route/distance, transfer, concession and date |
| Fuel cost | Cost can be null | Sourced consumption per km and current fuel price; avoid confusing km/l with l/km |
| Congestion profile | Raw OSRM estimate; factor can be null | Hourly observed/published profile and its road/time coverage |
| Trunk penalty | Active routing requires explicit configuration | Agreed routing preference; document separately from scientific factors |
| Inequality index | Index/rank remain null | Approved normalization, boundary version, green/population sources and treatment of missing regions |

Not every `verified_by: null` entry is a scientific constant: several entries
are explicit product/routing choices. Review those as choices, without inventing
a literature citation. Existing warnings are not evidence that every number is
missing, or that a fixture test scientifically validates the values.

## Primary source candidates

- ISPU: [Permen LHK 14/2020 in JDIH BPK](https://peraturan.bpk.go.id/Details/163466/permen-lhk-no-14-tahun-2020).
  The registry lists it as applicable at this review. Read the actual annex and
  averaging requirements before applying categories to hourly predictions.
  This registry check alone does not verify breakpoints or implementation.
- Ventilation: [US EPA Exposure Factors Handbook](https://www.epa.gov/expobox/about-exposure-factors-handbook),
  Chapter 6 named in the contract. Confirm the actual table and activity group;
  an ambient concentration is not an inhaled dose.
- Cigarette communication rule: [Berkeley Earth's original memo](https://berkeleyearth.org/air-pollution-and-cigarette-equivalence/).
  Review its population health-risk framing before communicating short-trip
  equivalents. It does not establish identical particle mass or an individual's
  clinical risk, and no contract value is changed by linking it here.
- The exact-title [2017 commuter systematic review](https://doi.org/10.1016/S2468-2667(16)30021-4)
  is published in *The Lancet Public Health*. The specification's bibliography
  labels this title as PLoS ONE. Propose that bibliographic correction to the
  documentation owner; do not silently edit the spec or treat identification
  of a paper as verification of the contract's numerical mode factors.
- [The six-mode study identified by PMC5679559](https://pmc.ncbi.nlm.nih.gov/articles/PMC5679559/)
  examines a roadway in Salt Lake City. Its geographic setting must stay visible
  when reviewing applicability to Jakarta; it is not the Delhi study.
- Emissions: [2026 UK government conversion factors and methodology](https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026).
  These describe UK activity data. Their use for Jakarta needs an explicit
  applicability decision; do not label a UK proxy as a verified local factor.
- Fares: obtain the current official tariff documents from each operator,
  including [TransJakarta](https://transjakarta.co.id/) and
  [MRT Jakarta](https://jakartamrt.co.id/). A promotion or an old annual report
  is not enough to establish the normal tariff for the requested travel date.
- The Delhi reference and each numerical mapping still require identification
  and human review. A secondary summary is not enough to verify a local factor.

## Review record template

For each proposed input record: contract key; exact source URL/document version;
page/table; proposed value/range/unit; averaging/time/geographic applicability;
conversion calculation; uncertainty; reviewer/date; affected API output; tests
and contract announcement required. Keep the result a proposal until reviewed.
Changes to `contracts/` require P1's approved change and team announcement.

## Handoff requests to prepare

These are checklists to share manually, not messages sent by the application.

- P2: versioned model binaries, metadata/registry and checksums; validation/OOF
  reports; real input access/provenance; atomic raster publication, city medians,
  complete historical and kelurahan coverage. Agree retention and failed-run behavior.
- P4: representative 50-OD file with its schema/IDs and validation; real MRT/LRT
  GTFS source, service dates, shapes and license. Do not substitute seeded OD
  or synthetic AQ for impact evidence.
- P3: APK build, API base URL configuration, quality/error display, offline
  fixtures and screenshots. Test 404/503, approximate endpoint locations and
  merged route labels on the actual device.
- Submission owners: final APK/video/deck/Figma links and confirmed AI tool roles.
  Technical documentation can be drafted now; final release evidence waits for
  the actual artifacts and real evaluation.
