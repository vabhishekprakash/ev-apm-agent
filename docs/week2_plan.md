# Week 2 plan — kickoff + Week 1 retro

Written at Week 1 close (2026-07-03), per SPEC Day 6 Joint Tasks 2–3.

## Week 1 retro

### What's actually working end-to-end (demoed)

- `replay | detector` pipeline on real capped exports: 6,000 events, 0 parse
  errors, all three Layer 1 detectors running in parallel.
- Synthetic fault fixtures (`tests/fixtures/day5_replay/`) produce the full
  alert set: err1051 candidate + final (recovery_seconds = 13.0, transient),
  err1024 (technician-dispatch-likely), telemetry_silence — each with its own
  `detector_source`, verified through the HTTP sink into the UI ring buffer
  with station-hash enrichment.
- Layer 2 on session close: 1,000 replayed sessions scored against the
  committed Isolation Forest artifacts — **4.3% flagged** at the calibrated
  threshold −0.1193 (held-out FP rate 4.02%, n = 2,013). Under the 5%
  acceptance bar; the number is logged in notebook 03 and the detector's
  stderr summary.
- 31 unit tests green.

### What's on paper but not verified (explicit list)

- **Real err1051/err1024 events** — the capped export contains zero fault
  rows, so both detectors are verified on synthetic fixtures reproducing the
  documented sequences, not on ground-truth CMS data. Blocked on the
  Workbench re-export.
- **Temperature / power-curve features** — implemented against OCPP
  sampledValue-shaped inputs and tested on synthetic sessions calibrated to
  the documented ~10°C PRABHAEV004N asymmetry; the capped export carries only
  `meter_reading_wh` (audit flag 6). The Isolation Forest feature vector is
  therefore only `duration_sec` + `start_hour` until the re-export lands —
  models must be retrained then.
- **Docker Compose e2e on this machine** — compose config is in place
  (event-bus volume replay→detector, detector→ui over the service network)
  and validates with `docker compose config`, but WSL2 reports
  *"virtualization is not enabled on this machine"*: CPU virtualization is
  disabled in BIOS/firmware, so Docker Desktop's Linux engine cannot start
  at all. **Action (Abhishek): enable VT-x/Virtual Machine Platform in
  firmware, reboot, then run `docker compose up` — first task of Week 2.**
  The containerized run is meanwhile validated by config + the functionally
  identical local pipeline (replay | detector with ALERT_SINK=http → ui).
- **229 telemetry_silence alerts on the capped export** — plausible cap
  artifacts (truncated sessions look silent), not individually triaged.
- **Pooled-cohort quality** — `prabhaev1` pooled model trained on n=1
  session; vendor-family cohorting is unvalidated for the thin families
  (SPEC risk 4 — global-pool fallback decision due Week 2 Day 2).

### What we underestimated

- **Data delivery risk**: two of three audit-tier assumptions (23k sessions,
  7 heavy connectors, 46 connectors) did not survive contact with the
  delivered export (10,090 / 1 / 38 — audit flag 7). Every model artifact
  carries a "retrain on full export" note. Budget standing hours for
  re-validation whenever data lands.
- **Threshold calibration**: the SPEC's LAYER2_THRESHOLD = −0.1 flags ~6% of
  held-out normals; hitting the <5% bar required calibrating to the 4%
  holdout quantile. Assume every pre-data constant needs a measurement pass.
- **Windows/toolchain friction** (BOMs, credential-picker hangs, Docker VM):
  reserve ~1 hr/week of slack; do not schedule it away.

## Week 2 Day 1 kickoff

1. **Alert prioritization logic** (judging hook — Business Impact 25%):
   rank alerts by classification severity (technician-dispatch >
   drift-anomaly > investigate > transient), recovery time, and per-connector
   recurrence count; surface rank in UI ordering and a priority badge.
2. **UI polish pass 1** (of the 3 hrs budgeted): per-connector drift panel
   (baseline vs live session features), alert filtering by detector_source,
   relative timestamps.
3. **False-positive measurement, formal**: freeze a held-out normal-session
   set, publish methodology (split seed, threshold, n) in
   `docs/fp_measurement.md`; re-measure when the full export lands. Headline
   metric for the deck — lead with it, not precision/recall.
4. **Deck outline v1**: problem → 13-second err1051 story → two-layer
   architecture → FP rate → deployment shapes (sidecar pitch).
5. **Carry-overs**: `docker compose up` verification on Abhishek's machine;
   err1024 data-owner follow-up (48-hr escalation window); pooled-vs-global
   fallback decision (Day 2); demo script draft before Week 4 recording.
