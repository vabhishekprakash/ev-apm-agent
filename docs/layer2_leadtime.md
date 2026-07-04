# Layer 2 ↔ Layer 1 lead-time analysis (Week 2 Day 5)

**Verdict: no reliable lead-time signal. The deck's central pitch line is the
backup framing — "orthogonal degradation tracking" — not early warning.**

## Method (notebook 05)

- 3,484 sessions reconstructed from the recovered PRABHAEV004N status history
  (Charging-episode boundaries; 60 s–24 h sanity bounds), connectors
  2009529/2009530, Oct 2025 → Jul 2026.
- 1,896 Layer-1-visible fault episodes (Faulted transitions) on the same
  connectors and window.
- Sessions scored chronologically with the *baseline* per-connector models
  (trained only on delivered normal sessions — no leakage from the Day 5
  retrain). Drift flag = score < −0.1187.
- "Pre-fault window" = the 5 sessions immediately before each fault episode.

## Result

| | drift-flag rate |
|---|---|
| Pre-fault windows (2,542 sessions) | **2.83%** |
| Background (942 sessions) | **4.99%** |
| Lift | **0.57×** |

Two honest reads, both fatal to a lead-time claim:
1. Flags are *less* frequent before faults than elsewhere — the opposite of a
   leading indicator on this feature set (`duration_sec` + `start_hour`).
2. This station faults so often that pre-fault windows cover 73% of all
   sessions — there is barely a "background" to lead against. A lead-time
   story on this data would be statistically indefensible even if the lift
   were positive.

## What this means for the pitch (SPEC risk 3 resolved)

- **Use:** "Layer 2 tracks each connector's behavioral baseline and flags
  drift — an orthogonal health signal to Layer 1's fault detection."
- **Do not use:** "flags at-risk connectors N sessions before the fault."
- Re-run when richer features land (power-curve, temperature — audit flags
  6/11): duration-only drift plausibly cannot see electrical precursors; the
  question stays open for the *feature-complete* model, and this file is the
  honest baseline to beat.

## Side result — expanded-normal retrain (Task 1, shipped)

Adding fault-adjacent-excluded reconstructed sessions to training (gated on
held-out FPR not degrading):

| connector | +normals | held-out FPR before → after |
|---|---|---|
| 2009529 | +998 | 1.74% → **1.16%** |
| 2009530 | +937 | 2.84% → 2.84% |

Gate passed; deployed artifacts for both connectors updated
(`isoforest_index.pkl` carries the `expanded_normals` markers).
