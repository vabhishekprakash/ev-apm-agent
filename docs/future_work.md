# Future work (scope-freeze ledger — Week 3 Day 1)

Scope froze at Week 3 Day 1 per the Week 3 plan. Everything below is
explicitly OUT of the submission; proposals from here to submission day land
in this file, not in code.

## Detection
- **GroundFailure dedup / rate-limiting** — the real export shows 79,480
  events in 14 months on one fleet segment (chattering sensor cohort, flag
  22); production needs episode-collapse before alerting. The prioritizer's
  file-top constants are the tuning surface.
- **err1051 full-evidence corroboration** — the machine is real-verified
  end-to-end on the status spine (88/88, flag 25) and on a full
  connector-month with transaction linkage (2/2 episodes, pk 2036074,
  flag 27); only the meter-zero corroborating step still awaits a
  meter-bearing fault window on real data.
- **err1024 meter-signature gate** — the crash signature (current/power ≈ 0,
  supply nominal) can suppress false positives once measurand telemetry
  streams live (flag 21).
- Detectors for the remaining 13 OCPP categories (HighTemperature,
  PowerMeterFailure, EVCommunicationError next by observed volume).

## Layer 2
- Temperature features — the located export is now ON DISK (flag 27a:
  65,994 real readings with Body/Outlet sensor location, 3 connectors,
  60 days), delivered after the scope freeze. Integration = map the
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
- Live OCPP-J adapter (websocket CSMS stub → event contract) so the agent
  consumes simulator/live traffic directly, not just CSV replays — pending
  written approval for any company-owned simulator (2026-07-10 assessment).
- NL fault query; multi-tenant SaaS shape (deck slide 9).

## Tooling
- ~~`graphify` CLI not installed~~ — **RESOLVED 2026-07-08**: installed
  (0.9.5, runs as `py -m graphify` on this machine), graph current.
- ~~pk-namespace mapping for the fault-export fleet segment~~ — **RESOLVED
  2026-07-08**: delivered, station names hashed per protocol, committed as
  `data/reference/fault_segment_stations.csv`; enrichment covers all 113
  connectors (audit flag 24).
