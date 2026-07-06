# EV APM Agent — Week 1, Days 4–6

**Context anchor:** Day 3 complete, `main` at `9da7d0d`. Day 1–3 close-out done: repo skeleton, `.gitignore`/`.dockerignore`/`.env.example` in, Pattern B structure adopted (`detector/layer1.py`, `detector/layer2.py`), `detector/ocpp_messages.py` + `replay/main.py` v0 + `docs/data_audit_v0.md` + `docs/layer2_scope.md` committed.

**Pending from Day 3 rollover:**
1. `data/reference/*.csv` — commit four inventory CSVs if on disk (2-min task, no Workbench needed)
2. `meter_values` and `heartbeat` exports — blocked on Workbench access
3. err1024 reproducible sequence — blocked on data owner reply (48-hr escalation timer running)

**Day 4–6 assumes items 1 and 2 clear by end of Day 4 morning.** If Workbench access slips further, Layer 1 err1024 handler stays as point-event stub and Layer 2 training set uses whatever normal-session CSVs are already local.

---

## Day 4 — First working detector, first real features

### Abhishek — 2 hrs, branch `feat/abhishek-err1051-transitions`

**Task 1: Implement err1051 state machine transitions (75 min)**
Fill in `Err1051Detector.consume(event)` in `detector/layer1.py`. Transitions per the 5-step sequence:

| From state | Event | Guard | To state | Side effect |
|---|---|---|---|---|
| `IDLE` | StatusNotification | `errorCode == 'err1051'` | `ERR_FIRST_SEEN` | log first-seen timestamp |
| `ERR_FIRST_SEEN` | MeterValues | voltage AND current AND power == 0 | `METER_ZERO` | log meter-zero timestamp |
| `METER_ZERO` | StatusNotification | `errorCode == 'err1051'` AND status == 'Finishing' | `ERR_SECOND_SEEN` | log second-seen timestamp |
| `ERR_SECOND_SEEN` | StopTransaction | `reason == 'Other'` | `STOP_TXN` | log stop timestamp, emit **candidate alert** |
| `STOP_TXN` | StatusNotification | `status == 'Available'` | `AVAILABLE` | compute recovery_seconds, classify transient (≤15s) vs technician-dispatch (>15s), emit **final alert** |
| any | timeout (>60s in non-IDLE) | — | `IDLE` | log stuck-state warning, reset |

Emit alerts as dict/dataclass, print to stdout for now. Wiring into UI comes Day 5.

**Task 2: Wire replay → detector via stdin (30 min)**
`replay/main.py` already prints JSON events per line. Extend `detector/main.py` to read stdin, parse each line into the right OCPP dataclass via `detector/ocpp_messages.py`, and pass to `Err1051Detector.consume()`. Run end-to-end:
```bash
python replay/main.py --input data/raw/status_notification_20260630.csv | python detector/main.py
```
Should see the state machine fire on the two known err1051 transactions.

**Task 3: Manual verification (15 min)**
Grep replay output for the two known fault `transactionId` values. Confirm detector emits alert for each. Log any mismatches as GitHub Issues; do not fix inline.

**Acceptance:** end-to-end pipeline shows one alert per known err1051 event, with correctly computed recovery_seconds.

### Akhil — 2 hrs, branch `feat/akhil-features-temp`

**Task 1: Peak temperature feature (45 min)**
Implement in `detector/layer2.py`:
```python
def _peak_temp_features(session_meter_values: list) -> dict:
    # returns: peak_temp_body, peak_temp_c1, peak_temp_c2
    # None for measurands not present in session
```
Filter `measurand == 'Temperature'` from MeterValues, group by sensor location (charger body, connector outlet 1, connector outlet 2), take max per session. Handle missing sensors gracefully.

**Task 2: Temperature asymmetry feature (45 min)**
```python
def _temp_asymmetry_features(session_meter_values: list) -> dict:
    # returns: temp_asymmetry_max, temp_asymmetry_mean, temp_asymmetry_final
    # asymmetry = abs(outlet_1_temp - outlet_2_temp) per timestamp
```
Only computable for two-connector stations reporting both outlets. Return None for single-outlet sessions. Reference the ~10°C observed asymmetry as the calibration target — you should see this range on normal sessions from `Station-A`.

**Task 3: Unit test both features on real data (30 min)**
Load one normal session from `data/raw/meter_values_*.csv` (once available). Run both feature functions. Assert types and reasonable value ranges (body temp 20–60°C, outlet temp 20–90°C, asymmetry 0–30°C). Write assertions in `tests/test_layer2_features.py`.

**Acceptance:** both features produce sane numbers on ≥3 real normal sessions. Test file passes.

### Joint — 30 min

- Merge Day 3 PRs if still open. `main` should not lag behind.
- Standup: confirm Workbench exports landed. If not, Akhil switches to Task 1/2 on whatever meter_values data is locally available (the OCPP evidence excerpt has enough for scaffolding).
- Escalation check on err1024. If 48 hours have passed with no data-owner reply, send a follow-up email today.

---

## Day 5 — err1024, remaining features, first pooled baseline

### Abhishek — 2 hrs, branch `feat/abhishek-err1024-silence`

**Task 1: err1024 point-event handler (45 min)**
Implement `Err1024Detector` in `detector/layer1.py`. Simpler than err1051 — single-transition:
```
IDLE → StatusNotification(errorCode='err1024') → emit alert(fault_code='err1024', mechanism='SLAC handshake timeout', classification='technician-dispatch-likely')
```
If the data owner reply arrived and confirms retry sequence or recovery-time signal, extend accordingly. If no reply, ship the point-event version with a TODO comment.

**Task 2: Telemetry-silence sub-detector (60 min)**
Implement `TelemetrySilenceDetector` in `detector/layer1.py`. Tracks active sessions (opened by StartTransaction, not yet closed by StopTransaction). For each active session, tracks last-seen MeterValues timestamp. If `now - last_seen > SILENCE_THRESHOLD_SECONDS` (default 90s — 3× the observed 30s meter cadence), emit a silence-alert.

Configurable via env var `SILENCE_THRESHOLD_SECONDS` in `.env.example`. Reset when either MeterValues arrive or StopTransaction fires.

**Task 3: Wire both new detectors into `detector/main.py` (15 min)**
All three detectors (Err1051, Err1024, TelemetrySilence) run in parallel on the event stream. Alerts stream to stdout with a `detector_source` field distinguishing them.

**Acceptance:** end-to-end pipeline emits alerts for err1051, err1024, AND silence events on replay. All three detector sources visible in output.

### Akhil — 2 hrs, branch `feat/akhil-features-power-baseline`

**Task 1: CC-CV power-curve features (60 min)**
Implement in `detector/layer2.py`:
```python
def _power_curve_features(session_meter_values: list) -> dict:
    # returns: peak_power, cc_cv_taper_slope, cc_cv_peak_frac_final
```
- `peak_power` — max Power.Active.Import in session
- `cc_cv_taper_slope` — linear regression slope of power over time during the tapering phase (post-peak)
- `cc_cv_peak_frac_final` — final power as fraction of peak power (proxy for how "full" the charge got)

Reference: the SoC proxy strategy from the original project brief (Section 5). This is the primary feature set for sessions where SoC reports 0.

**Task 2: Duration and energy features (30 min)**
```python
def _session_scale_features(session_transaction: dict, session_meter_values: list) -> dict:
    # returns: duration_sec, energy_wh, energy_per_second
```
`energy_wh` from Energy.Active.Import.Register (last - first reading). `duration_sec` from Transaction start/stop timestamps.

**Task 3: First per-connector baseline (30 min)**
`notebooks/02_baseline_v0.ipynb`: for the 7 heavy-tier connectors (≥1000 sessions), compute per-connector mean and std of each feature. Save as `models/baselines_v0.pkl`. This is a summary-stat baseline, not an Isolation Forest — that lands Day 6.

**Acceptance:** 5 features computable per session, baselines saved for 7 heavy-tier connectors, sanity-check plots in notebook confirm distributions look reasonable (no everything-is-zero features, no infinity values from division).

### Joint — 30 min

- PR reviews from Day 4 branches. Merge cleanly.
- Look at Akhil's feature distributions together. Any red flags (all-zero temp, all-NaN asymmetry) get logged as Issues.
- Confirm architecture diagram v1 gets sketched **tomorrow** — do not let it slip past Day 6.

---

## Day 6 — Isolation Forest, architecture diagram, Week 1 close

### Abhishek — 2 hrs, branch `feat/abhishek-ui-alerts`

**Task 1: Minimal FastAPI dashboard (75 min)**
`ui/main.py`: single-page FastAPI app with:
- `GET /` — HTML page (single file, vanilla JS + a tiny bit of CSS, no framework)
- `GET /alerts` — JSON endpoint returning last N alerts from an in-memory ring buffer
- `POST /alerts` — accepts alerts from detector service

Detector service (Day 5) writes to stdout; add a mode where it POSTs alerts to `http://ui:8000/alerts` instead. Toggle via env var `ALERT_SINK={stdout,http}`.

Frontend polls `/alerts` every 2 seconds and renders a scrolling list: timestamp, hashed_charge_box_id, connectorId, fault_code, classification (transient/technician), recovery_seconds if applicable.

Not fancy. Judge-readable is the bar.

**Task 2: Docker Compose end-to-end (30 min)**
Update `docker-compose.yml` so `docker compose up` starts replay → detector → ui with correct network config. Replay reads from a mounted `./data/raw/` volume. Detector connects to ui via service name. UI exposes port 8000 to host.

**Task 3: Record demo dry-run (15 min)**
Full pipeline start, watch alerts appear in UI during replay of the two known fault transactions. Screen-record for reference (not the final demo). Log any issues.

**Acceptance:** `docker compose up`, open browser to `localhost:8000`, see alerts stream in during replay.

### Akhil — 2 hrs, branch `feat/akhil-isoforest`

**Task 1: Train Isolation Forest per-connector (75 min)**
`notebooks/03_isoforest_training.ipynb`:
- For each heavy/medium/light-tier connector (35 total), train an Isolation Forest on that connector's normal-session feature vectors
- Use scikit-learn defaults with `contamination='auto'` and `random_state=42`
- Save models as `models/isoforest_<hashed_charge_box_id>_<connector_id>.pkl`
- For marginal/sparse connectors (11 total), train **one pooled model per vendor-family cohort** and save as `models/isoforest_pooled_<vendor_family>.pkl`

**Task 2: Layer 2 inference wrapper (30 min)**
In `detector/layer2.py`, implement `Layer2Anomaly.score(session_features, hashed_charge_box_id, connector_id)`:
- Look up the right model (per-connector if available, else pooled by vendor)
- Return raw anomaly score + boolean flag (`score < threshold`)
- Threshold configurable via env var `LAYER2_THRESHOLD` (default -0.1)

**Task 3: Wire Layer 2 into detector on session close (15 min)**
When `StopTransaction` fires and the session was not fault-flagged by Layer 1, extract features, score with Layer 2, emit an anomaly alert if flagged. Alert type `layer2_drift`, distinct from Layer 1 alerts.

**Acceptance:** on replay of the full 90-day dataset, Layer 2 flags <5% of normal sessions (false-positive rate — the headline defensible metric). Number logged.

### Joint — 90 min (extended for Week 1 close)

**Task 1: Architecture diagram v1 (45 min)**
Whiteboard together. Both of you. Sketch the runtime topology showing:
- CMS event stream (real prod) OR replay harness (demo mode) on the left
- Detector service in the middle with Layer 1 (state machines + silence) and Layer 2 (feature extractor + IsoForest per-connector + pooled fallback) as sub-boxes
- Alert bus and UI on the right
- Trained model artifacts as an offline training pipeline feeding into Layer 2

Photograph the whiteboard. Commit as `docs/architecture_v1.png`. Refine in a tool (Excalidraw, draw.io, Mermaid) in Week 2.

**Task 2: Week 1 retro (30 min)**
Three questions, answer honestly:
- What's actually working end-to-end? Demo it.
- What's on paper but not verified? List explicitly.
- What did we underestimate? Adjust Week 2 hours accordingly.

**Task 3: Week 2 Day 1 kickoff plan (15 min)**
Written into a `docs/week2_plan.md` stub. Should cover: alert prioritization logic build, UI polish, false-positive rate measurement on held-out normals, first draft of deck outline.

---

## End-of-Week-1 acceptance checklist

Copy this to a GitHub Issue titled `Week 1 exit criteria` and check off:

- [ ] `main` at a tagged commit `v0.1.0-week1`
- [ ] `docker compose up` runs the full pipeline on Abhishek's machine
- [ ] Replay of the two known fault transactions produces correct err1051 and err1024 alerts in the UI
- [ ] Telemetry-silence detector fires on synthetic silence scenarios (unit test)
- [ ] 5 session-level features computable on any real normal session
- [ ] Isolation Forest baselines exist for 35 heavy/medium/light connectors + N pooled cohort models
- [ ] Layer 2 false-positive rate on held-out normals measured and logged (number, not "seems reasonable")
- [ ] Architecture diagram v1 photographed and committed
- [ ] `docs/data_audit_v0.md`, `docs/layer2_scope.md`, `docs/week2_plan.md` all in repo
- [ ] err1024 sequence question resolved (either data owner replied, or point-event handler confirmed as final)
- [ ] All Day 4–6 branches merged, `main` clean

---

## Risks flagged into Week 2

1. **UI is minimum-viable and undesigned.** Week 2 needs polish for demo video. Budget 3 hrs.
2. **No alert-prioritization logic yet** — the 13-second signal is captured in the err1051 detector but not surfaced as a priority ranking. This is a judging-criteria hook (Business Impact 25%). Week 2 Day 1 task.
3. **False-positive rate is the only defensible quantitative metric** — deck framing must lead with it, not with precision/recall.
4. **Layer 2 pooled model for sparse connectors is a bet** — if vendor-family cohorting doesn't produce sensible baselines (verify with distribution plots Day 6), fall back to a single global pooled model. Decision Week 2 Day 2.
5. **Demo script not started** — Week 2 must produce a written narrative before the recording Week 4.

## Deferred to Week 2+

- Alert prioritization ranking (Business Impact hook)
- UI visual polish, per-connector drift panel
- Held-out normal-session false-positive measurement (formal, not just "logged")
- Deck outline v1
- Demo script v1
- Data-owner enrichment ask for the NaN-vendor row and connector-0 anomaly
---

# Week 2 findings addendum (2026-07-04, at v0.2.0-week2)

- **Taxonomy discovery, partially absorbed:** the Errornotify error-taxonomy
  numbers (19 OCPP categories / 2.77M occurrences / ~17.5k vendor codes)
  reshaped the story, but the CSV itself has NOT been delivered — the
  normalizer's lookup tables and coverage measurement
  (scripts/normalizer_coverage.py) await it. Provenance notes ride every
  taxonomy claim until then.
- **Layer 1 detects 6 categories:** err1051 (state machine + recovery
  classification), err1024 (point event), telemetry-silence, WeakSignal
  (burst escalation), GroundFailure (safety P1), Under/OverVoltage (24h
  repeat escalation). UnderVoltage verified on 18 real events (audit flag
  18); the rest fixture-verified pending the fault-event export
  (data/sql/fault_events.sql, request sent W2D1).
- **Vendor code normalization** shipped as shape-rule engine with
  taxonomy-fed lookup tables (detector/vendor_code_normalizer.py); unmapped
  codes fall through to the already-labeled error_code field by design.
- **Alert prioritization live:** P1/P2/P3 with deciding signals; 13s
  self-recovery downgrade, drift-streak and repeat-offender escalations
  (detector/prioritizer.py).
- **FPR (headline metric): 3.62%** chronological per-connector holdout at
  the deployed threshold −0.1187 (notebook 04, n=2,015); expanded-normal
  retrain shipped for 2009529/2009530 after passing the FPR gate
  (notebook 05).
- **Lead-time verdict: negative** (lift 0.57× — docs/layer2_leadtime.md).
  The pitch line is "orthogonal degradation tracking". Re-evaluate only if
  the measurand re-export enables richer features.
- **Identity correction:** Station-A (alias) = charge-box hash 0c70c6b0…, CN.TH, connectors
  2009529/2009530 (+ plug-0 2013696). Week 1 materials mislabeled d4416bd8….
- **Deck outline v1** (honesty-audited) and **demo script v2** (two-source
  runbook, dry-run #1 proven) committed; UI must-fix list in
  docs/demo_dryrun_w2.md; Week 3 plan in docs/week3_plan.md.
