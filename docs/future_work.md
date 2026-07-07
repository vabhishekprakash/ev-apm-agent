# Future work (scope-freeze ledger — Week 3 Day 1)

Scope froze at Week 3 Day 1 per the Week 3 plan. Everything below is
explicitly OUT of the submission; proposals from here to submission day land
in this file, not in code.

## Detection
- **GroundFailure dedup / rate-limiting** — the real export shows 79,480
  events in 14 months on one fleet segment (chattering sensor cohort, flag
  22); production needs episode-collapse before alerting. The prioritizer's
  file-top constants are the tuning surface.
- **err1051 full-machine real verification** — needs one combined
  status + meter_values + transaction export window (the status-only
  sequence export validates shape + recovery stats only, flag 23).
- **err1024 meter-signature gate** — the crash signature (current/power ≈ 0,
  supply nominal) can suppress false positives once measurand telemetry
  streams live (flag 21).
- Detectors for the remaining 13 OCPP categories (HighTemperature,
  PowerMeterFailure, EVCommunicationError next by observed volume).

## Layer 2
- Temperature features on a future export with a live sensor field
  (flags 11/20 — code and tests already in place).
- Lead-time re-run with power/temperature features (current verdict:
  orthogonal, lift 0.57× — docs/layer2_leadtime.md).
- Autoencoder Layer 2; per-connector online retraining cadence.

## Product
- Alert-log download button (judge quality-of-life, exit-doc nice-to-have 3).
- Per-station rollup view; Slack/PagerDuty sink implementations.
- NL fault query; multi-tenant SaaS shape (deck slide 9).

## Tooling
- `graphify` CLI not installed on the dev machine — the CLAUDE.md
  knowledge-graph workflow is inoperative; install or drop the instruction.
- pk-namespace mapping for the fault-export fleet segment (113 connectors,
  zero inventory overlap — enrichment misses by design until then).
