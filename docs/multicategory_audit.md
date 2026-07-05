# Multi-category fault audit (Week 2 Day 4, Task 1)

**Status: pattern audit blocked on the fault-event export** — the request is
drafted (`data/sql/fault_events.sql`, sent Week 2 Day 1) and the capped
`status_notification` export contains zero fault rows, so per-category
sequence analysis (bursts, StopTransaction coupling, recovery signals like
err1051's) cannot run yet. This file records what IS known and how the Day 4
implementation was verified meanwhile.

## What real data shows so far

- **Recovered PRABHAEV004N history** (41k rows): 2,041 `Faulted` episodes
  with clear burst structure and a wide recovery spread (median 33 s, p75
  ~245 s — audit flag 12), but **no error codes** — categories
  indistinguishable in this file. It proves fault episodes cluster and
  self-recover at very different speeds, motivating the burst and
  repeat-offender escalations.
- **Fault-evidence windows** (master_training_set, 46 events): voltage stays
  nominal while current/power collapse (flag 10) — relevant to future
  UnderVoltage guard design: a *supply* voltage fault will look different
  from these *load-side* faults.
- **Taxonomy scale** (per Week 2 spec; Errornotify.csv delivery pending):
  19 OCPP categories, 2.77M occurrences, ~17.5k vendor code strings.

## Implementation shipped (verified on fixture until the export lands)

| Category | Handler | Escalation (prioritizer) |
|---|---|---|
| WeakSignal | point event | P3; >5 events / 5 min → P2 burst |
| GroundFailure | point event | always P1 (electrical safety) |
| UnderVoltage / OverVoltage | combined point event | P2; repeat on same connector within 24h → P1 |

- Detectors are **stateless**, keyed on the canonical category from
  `vendor_code_normalizer.normalize(vendor_error_code, error_code)`;
  all escalation state lives in `AlertPrioritizer` (one place, one clock).
- Fixture `tests/fixtures/day4_multicategory/` replays a weak-signal burst,
  a ground fault, and a 5-hour-spaced voltage pair: e2e produces P3→P2 burst
  escalation, P1 ground fault, and P2→P1 voltage repeat, alongside the
  Week 1 categories.

## To re-run when the export lands

1. Replay `data/raw/fault_events.csv` end-to-end; confirm all 6 categories
   fire on real events (Day 4 acceptance flips from fixture- to real-verified).
2. Per-category sequence audit: burst rates, StopTransaction coupling,
   recovery signatures → tune the escalation thresholds in
   `detector/prioritizer.py` (they are the file-top constants).
3. Run `py scripts/normalizer_coverage.py` for the measured coverage number
   (Task 2) — target ≥90% routed by rules; the long tail falls through to
   the labeled `error_code` field by design.

## err1024 update (2026-07-05) — blocker closed

The crash signature (`data/raw/err1024_crash_signature.csv`, 3 real events)
confirms the point-event design as final: supply nominal (227.4–227.9 V,
~49.9 Hz), current/power ≈ 0, energy flat — no retry or recovery sequence to
model. Detector docstring updated; burst/repeat escalation stays in the
prioritizer, which also gains the **station-wide P1 escalation** (88% of real
fault episodes are simultaneous both-plug events — audit flag 19).
