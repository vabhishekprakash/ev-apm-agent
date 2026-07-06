# Layer 2 Scope — per-connector vs pooled baselines

Owner: Akhil. Decision doc for which connectors get their own baseline model
and which fall back to the pooled cohort baseline.

## Decision

- **Per-connector baseline (own Isolation Forest + rolling stats):** connectors
  with **≥100 normal sessions** — the heavy (≥1000, n=7), medium (250–999,
  n=15), and light (100–249, n=13) tiers. 35 of 46 active connectors.
- **Pooled cohort baseline:** connectors with **<100 normal sessions** — the
  marginal (30–99, n=5) and sparse (<30, n=6) tiers. 11 connectors. Cohort key
  is vendor + firmware family (see data_audit_v0.md for the family groupings).

## Rationale

- 100 sessions is the smallest volume where per-connector mean/std drift
  statistics stop being noise-dominated on the observed feature set.
- Below 100, a vendor/firmware-cohorted pool gives a usable "normal" at the
  cost of losing connector-level specificity — acceptable for the 11 tail
  connectors (~24% of connectors, far less of session volume).

## Guardrails

- **Station-A (~4,439 sessions, ~19% of fleet volume) must not dominate the
  pooled model** — train pooled baselines with per-connector downsampling caps.
- The 7 chargers registered after Feb 2026 land in marginal/sparse by
  construction; do not read their tier as a health signal.
- Drop the single `connectorId=0` session on Station-A from all training.

## Decision update (Week 2 Day 1, 2026-07-04) — cohort vs global pooling

**Settled: hybrid.** Vendor families with ≥50 pooled-tier sessions keep their
own cohort Isolation Forest; thinner families (`prabhaev1` n=1, `acs285`
n=44) and any family unseen at inference route to a **global pooled model**
trained on the whole pooled tier (n=587, per-connector cap applied).
Implemented in notebook 03 + `Layer2Anomaly._model_file_for` fallback.

Verification (notebook 04): pooled-tier duration distributions per family are
coherent/unimodal for the ≥50-session families — cohorting holds for them;
below that the "cohort" was one connector's noise (the first training run
produced a prabhaev1 model trained on a single session).

## FPR measurement status (headline metric)

Chronological 80/20 holdout (most recent 20% per connector, notebook 04):
**overall FPR 3.62%** at the deployed threshold −0.1187 (5.26% at the SPEC
default −0.1), n = 2,015 held-out normals. Per-tier: heavy 3.3% / medium
3.5% / light 3.2% / pooled-tier 6.1% (n=148). Watch-list: `siemens` family
10.5% (n=76). Random-split calibration reference: 4.02% (notebook 03).

## Open

- Feature vector is still `duration_sec` + `start_hour` (audit flags 6/11 —
  measurand re-export pending, temperature field dead). Re-run notebooks 03/04
  when richer features land.
- Pooled-tier FPR (6.1%, n=148) exceeds the bar on a small sample — recheck
  after the full export.

## Temperature features: closed out (2026-07-05)

Out of scope for the hackathon — the field is dead at source (three
independent confirmations, audit flags 11/20/21). The implemented features
and tests remain in the codebase against the sampledValue contract for any
future export that carries real temperatures; no model, metric, or pitch
claim depends on them.
