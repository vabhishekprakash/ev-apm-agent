# Future work (scope-freeze ledger — Week 3 Day 1)

Scope froze at Week 3 Day 1 per the Week 3 plan. Everything below is
explicitly OUT of the submission; proposals from here to submission day land
in this file, not in code.

**Status at 2026-07-16:** 13 ledger items — **2 resolved** (tooling),
**2 mostly resolved** (err1051 corroboration: meter-zero step left;
raw OCPP-J ingestion: live-socket transport left), **1 unblocked but open**
(temperature: data landed, integration queued), **8 open** (GroundFailure
dedup, err1024 meter gate, 13 remaining categories, lead-time re-run,
autoencoder L2, alert-log download, per-station rollup + sinks, NL query /
SaaS).

## Detection
- **GroundFailure dedup / rate-limiting** — the real export shows 79,480
  events in 14 months on one fleet segment (chattering sensor cohort, flag
  22); production needs episode-collapse before alerting. The prioritizer's
  file-top constants are the tuning surface.
- **err1051 full-evidence corroboration** — **MOSTLY RESOLVED 2026-07-14**:
  real-verified end-to-end on the status spine (88/88, flag 25) and on a
  full connector-month with transaction linkage (2/2 episodes, pk 2036074,
  flag 27). *Remaining:* only the meter-zero corroborating step, which
  awaits a meter-bearing fault window on real data.
- **err1024 meter-signature gate** — the crash signature (current/power ≈ 0,
  supply nominal) can suppress false positives once measurand telemetry
  streams live (flag 21).
- Detectors for the remaining 13 OCPP categories (HighTemperature,
  PowerMeterFailure, EVCommunicationError next by observed volume).

## Layer 2
- Temperature features — **UNBLOCKED, integration still open**: the located
  export is ON DISK (flag 27a: 65,994 real readings with Body/Outlet sensor
  location, 3 connectors, 60 days), delivered after the scope freeze, and
  the raw-OCPP adapter already flattens live Temperature sampled values
  (Body/EV/Inlet/Outlet observed on the real log). Integration = map the
  long-format export onto the sampledValue contract, revive
  `_temp_asymmetry_features` (code and tests already in place, flags
  11/20/26), retrain via notebooks 03–04.
- Lead-time re-run with power/temperature features (current verdict:
  orthogonal, lift 0.57× — docs/layer2_leadtime.md; the flag-27a
  temperature volume makes this re-run finally possible).
- Autoencoder Layer 2; per-connector online retraining cadence.

## Product
- Alert-log download button (judge quality-of-life, exit-doc nice-to-have 3).
- Per-STATION rollup view (per-connector health rollup SHIPPED 2026-07-08
  via week_3_recommended_plan — `detector/health_rollup.py`);
  Slack/PagerDuty sink implementations.
- ~~Raw OCPP-J ingestion so the agent consumes native CMS logs, not just
  flattened CSVs~~ — **MOSTLY RESOLVED 2026-07-12→16** (PRs #59/#60/#66):
  `detector/ocpp_log_adapter.py` parses raw OCPP-J frames (batch
  `--format raw-ocpp` and streaming `--follow` file-tail), anonymizes at
  ingestion, and reconciles to native connector keys; verified on the real
  CMS log (20/20 frames, alert in UI 3.1 s after append). *Remaining:* a
  true live WebSocket/CSMS socket transport — the tail mode streams at
  arrival cadence but is not a live connection — plus written approval
  before touching any company-owned simulator (2026-07-10 assessment).
- NL fault query; multi-tenant SaaS shape (deck slide 9).

## Tooling
- ~~`graphify` CLI not installed~~ — **RESOLVED 2026-07-08**: installed
  (0.9.5, runs as `py -m graphify` on this machine), graph current.
- ~~pk-namespace mapping for the fault-export fleet segment~~ — **RESOLVED
  2026-07-08**: delivered, station names hashed per protocol, committed as
  `data/reference/fault_segment_stations.csv`; enrichment covers all 113
  connectors (audit flag 24).
