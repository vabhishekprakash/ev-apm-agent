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

- **PRABHAEV004N (~4,439 sessions, ~19% of fleet volume) must not dominate the
  pooled model** — train pooled baselines with per-connector downsampling caps.
- The 7 chargers registered after Feb 2026 land in marginal/sparse by
  construction; do not read their tier as a health signal.
- Drop the single `connectorId=0` session on PRABHAEV004N from all training.

## Open

- Cutoffs are Week 1 heuristics; revisit after the first false-positive-rate
  measurement on held-out normal sessions (the headline metric — no held-out
  fault set exists).
