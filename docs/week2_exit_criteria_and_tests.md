# EV APM Agent — Week 2 Exit Definition & Acceptance Tests

**Purpose:** Freeze what "done" looks like at end of Week 2, and give you executable test cases to prove it. Passing all tests below = the prototype is aligned with the ETAI Hackathon 2026 problem statement and meets the bar for finals contention.

---

## Part 1 — What the system should DO by end of Week 2

### Behavior contract (in plain language)

The system, when given a stream of OCPP-shaped events replayed from real anonymized CMS data, must:

1. **Detect faults instantly.** Any of the 6 target fault categories firing in the event stream produces an alert in the UI within 2 seconds of the source event's replay timestamp.
2. **Distinguish transient from technician-required faults.** err1051 events that self-recover within 15 seconds are downgraded to P3; those that don't recover are P1. This is visible on-screen.
3. **Track per-connector degradation over time.** For each connector with sufficient normal-session history, the drift panel shows temperature asymmetry, peak temperature, and CC-CV taper coefficients trending across sessions, with anomaly-flagged sessions visually marked.
4. **Prioritize alerts.** Every alert carries a P1/P2/P3 tier and a human-readable deciding-signal string. Feed sorts by priority, then recency.
5. **Normalize vendor error codes to a standard taxonomy.** Any of ~17,553 vendor-specific error strings routes to one of 19 OCPP-standard categories, with measured coverage ≥80%.
6. **Operate across a heterogeneous fleet.** 39 stations, 5+ vendor families, 19 firmware versions — Layer 2 either builds per-connector baselines (for the 35 well-sampled connectors) or falls back to pooled vendor-cohort baselines (for the 11 sparse ones).
7. **Deploy as a container next to a CMS.** `docker compose up` starts three services (replay, detector, UI). No cloud dependencies, no external services required.

### What the system should NOT do (guardrails)

- Claim to diagnose battery state-of-health or state-of-charge directly
- Claim predictive lead time on err1051 or err1024 without evidence from lead-time analysis
- Present precision/recall on faults as if supervised classification is happening (it isn't; not enough labels per category)
- Show any real (non-hashed) charger IDs, customer data, RFIDs, IPs, or precise geo coordinates
- Detect `InternalError` (too broad), `Available after Finishing Status`, or `Transaction Stopped` (not faults)

---

## Part 2 — What the system should LOOK like by end of Week 2

### UI surfaces (verified by screen inspection)

**Top of page — summary header:**
- Active P1 count (live)
- Active P2 count (live)
- Sessions processed count (live)
- Current false-positive rate (from held-out measurement, static during demo)
- Categories detected: "6 of 19"

**Middle — priority-sorted alert feed:**
- Each row: tier badge (P1 red / P2 amber / P3 grey), timestamp, hashed charger ID (truncated to 8 chars), connector ID, fault category, classification, deciding-signal text
- Sorted P1 → P2 → P3, then most recent first within tier
- Live-updating as replay produces new events

**Right (or bottom) — per-connector drift panel:**
- Connector selector dropdown
- Three trend lines: temp asymmetry, peak temp, CC-CV taper slope
- Anomaly-flagged sessions marked with vertical bars or dots on the trend
- Chosen demo connector loads by default

**Small — category coverage badge:**
- "6 of 19 OCPP categories detected"
- Optional: mini bar chart of event volume per category

### Repo state (verified by `git ls-tree`)

```
ev-apm-agent/  (tagged v0.2.0-week2)
├── data/
│   ├── raw/                    (gitignored, populated locally)
│   ├── reference/
│   │   ├── total_stations.csv
│   │   ├── charger_stations.csv
│   │   ├── cp_firmware.csv
│   │   ├── normal_sessions.csv
│   │   └── error_taxonomy.csv  (from Errornotify.csv)
│   └── sql/                    (6 committed .sql files)
├── detector/
│   ├── main.py
│   ├── ocpp_messages.py
│   ├── layer1.py               (6 detectors + telemetry-silence)
│   ├── layer2.py               (feature extractor + IsoForest inference)
│   ├── prioritizer.py
│   └── vendor_code_normalizer.py
├── replay/main.py
├── ui/main.py
├── models/                     (per-connector + pooled IsoForest artifacts)
├── docs/
│   ├── SPEC.md
│   ├── data_audit_final.md
│   ├── layer2_scope.md
│   ├── multicategory_audit.md
│   ├── layer2_leadtime.md
│   ├── architecture_v2.svg
│   ├── deck_outline.md
│   ├── demo_script.md
│   └── category_metrics.md
├── tests/                      (see Part 3)
├── notebooks/                  (audit + evaluation notebooks)
├── docker-compose.yml
├── LICENSE
├── README.md
└── .env.example
```

---

## Part 3 — Executable acceptance tests

These are the tests that prove alignment with the problem statement. Group them by concern. Each has a *what it checks*, *how to run it*, and *pass criteria*.

### Suite A — Layer 1 correctness (deterministic detectors)

**A1. err1051 full state machine on real fault transaction**
- **What it checks:** the reproducible 5-step sequence fires the alert exactly once with correct recovery time
- **How:** replay `data/raw/status_notification_20260630.csv` filtered to a known err1051 transaction; inspect detector stdout
- **Pass criteria:**
  - Exactly one alert emitted with `fault_category == 'err1051'`
  - `recovery_seconds` field populated, value in range 10–20s
  - `priority_tier == 'P3'` (self-recovered, downgraded)
  - Alert appears in UI within 2s of replay of the final `Available` status

```python
# tests/test_err1051_full_sequence.py
def test_err1051_transient_downgraded_to_p3():
    events = load_replay_events("tests/fixtures/err1051_transient.jsonl")
    detector = Err1051Detector()
    alerts = run_detector(detector, events)
    assert len(alerts) == 1
    assert alerts[0].fault_category == 'err1051'
    assert 10 <= alerts[0].recovery_seconds <= 20
    assert alerts[0].priority_tier == 'P3'
    assert 'self-recovered' in alerts[0].deciding_signal.lower()
```

**A2. err1051 non-recovering escalates to P1**
- **What it checks:** if `Available` status never arrives, or arrives >15s later, priority is P1
- **How:** synthetic fixture with err1051 sequence but no `Available` status within window
- **Pass criteria:** alert emitted, `priority_tier == 'P1'`, deciding_signal contains "no recovery" or "technician"

**A3. err1024 point event fires immediately**
- **What it checks:** on a single `StatusNotification(errorCode='err1024')`, an alert fires within one event-loop cycle
- **Pass criteria:** alert emitted, `fault_category == 'err1024'`, `priority_tier == 'P2'` default

**A4. Telemetry silence during active session**
- **What it checks:** a session that opens (StartTransaction), receives MeterValues, then goes silent for >90s without StopTransaction, produces a silence alert
- **Pass criteria:** exactly one silence alert emitted at silence threshold; `priority_tier == 'P1'`; alert clears/does not repeat once MeterValues resume or StopTransaction fires

**A5. New Layer 1 categories fire (Day 4 work)**
- **What it checks:** WeakSignal, GroundFailure, UnderVoltage, OverVoltage detectors each fire on real event replays
- **Pass criteria:** for each category, at least one alert emitted from the real event export; correct `fault_category` label; correct default priority per prioritizer rules

### Suite B — Alert prioritization logic

**B1. Priority tier is assigned to every alert**
- **What it checks:** no alert reaches the UI without a `priority_tier` and `priority_score`
- **How:** run detector on full replay, dump all alerts, assert every one has both fields
- **Pass criteria:** 100% coverage

**B2. Consecutive drift escalates**
- **What it checks:** three Layer 2 drift alerts on the same connector within a rolling window trigger a P2 escalation from the default P3
- **Pass criteria:** 1st and 2nd drift alerts are P3, 3rd is P2, deciding_signal contains "3 consecutive"

**B3. Repeat-offender upgrade**
- **What it checks:** any alert on a connector with a P1 in the last 24h is upgraded one tier
- **Pass criteria:** synthetic sequence with a P1 followed by a P3 on same connector — the P3 becomes P2

**B4. Prioritizer weights are configurable**
- **What it checks:** weights defined at top of `prioritizer.py`, changing them changes outcomes without code changes
- **Pass criteria:** modify a weight, rerun same fixture, tier changes as expected

### Suite C — Layer 2 anomaly detection

**C1. FPR on chronological held-out normal sessions**
- **What it checks:** on the most recent 20% of normal sessions per connector (held out from training), the fraction flagged as anomalous is ≤5% overall
- **How:** `notebooks/04_holdout_evaluation.ipynb` produces the number; test asserts it
- **Pass criteria:** overall FPR ≤ 5%, per-tier FPR reported for heavy/medium/light

**C2. Per-connector baselines exist for viable connectors**
- **What it checks:** every connector with ≥100 normal sessions has a saved IsoForest artifact
- **Pass criteria:** `models/` contains 35 per-connector artifacts + pooled cohort artifacts covering the 11 sparse connectors

**C3. Feature extraction produces sane values on real sessions**
- **What it checks:** on 10 random normal sessions, extracted features fall within physically plausible ranges
- **Pass criteria:**
  - Peak body temp: 20–60°C
  - Peak outlet temp: 20–95°C
  - Temp asymmetry: 0–30°C (with 10°C observed as the calibration reference)
  - Peak power > 0, taper slope ≤ 0 (power decreases post-peak)
  - Session duration > 0
  - Energy delivered > 0

**C4. Layer 2 falls back correctly for sparse connectors**
- **What it checks:** a sparse connector's session gets scored by the pooled vendor-cohort model, not by a nonexistent per-connector model
- **Pass criteria:** no `FileNotFoundError`; correct model artifact used per lookup rule in `layer2.py`

**C5. Downstream anomaly flag is deterministic**
- **What it checks:** scoring the same session twice produces the same anomaly score
- **Pass criteria:** IsoForest artifacts are loaded from disk and produce reproducible scores

### Suite D — Vendor code normalization

**D1. Coverage on the taxonomy CSV**
- **What it checks:** ≥80% of the 17,553 vendor codes in `error_taxonomy.csv` route to a named OCPP category via rules (not fall through to "OtherError")
- **Pass criteria:** coverage number computed, documented, ≥80%

**D2. Known vendor code families route correctly**
- **What it checks:** for a curated fixture of 30 vendor codes across families (system-err*, ER###, C###, AlarmN-ErrN, NN-NNN, 0xHEX, freeform strings), each routes to the expected OCPP category

```python
# tests/test_vendor_normalizer.py
CASES = [
    ("system-err1051", "OtherError", "err1051"),
    ("ER017",         "WeakSignal", "iongrid_weak_signal"),
    ("C025",          "InternalError", "tucker_c025"),
    ("Alarm1-Err4",   "GroundFailure", "siemens_alarm1_err4"),
    ("0x0001",        "UnderVoltage", "exicom_0x0001"),
    ("SignalWeak:11/JIO 4G", "WeakSignal", "freeform_signal_weak"),
    # ...
]
def test_normalizer_family_routing():
    for vendor_code, expected_ocpp, _ in CASES:
        assert normalize(vendor_code).ocpp_category == expected_ocpp
```

**D3. Fallback path is safe**
- **What it checks:** an unknown vendor code falls through to the OCPP `error_code` field, never raises
- **Pass criteria:** no exception; category = whatever `error_code` says

### Suite E — Data quality guards

**E1. connectorId=0 sessions are dropped from training**
- **What it checks:** the one REDACTED-STATION-PREFIX connectorId=0 session does not appear in any Layer 2 training set
- **Pass criteria:** training data audit shows connectorId=0 count == 0

**E2. NaN vendor rows are handled**
- **What it checks:** the single row in `chargepoint.csv` with NaN vendor/model/firmware does not crash pooled-cohort lookup
- **Pass criteria:** normalizer treats missing vendor as "unknown" cohort; test passes without raising

**E3. Anonymization holds throughout**
- **What it checks:** grep the entire repo (all committed files, all notebook outputs) for patterns that could be real charger IDs, IPs, phone numbers, RFID formats
- **How:** a repo-wide grep script
- **Pass criteria:** zero hits on the un-hashed forms; every charger reference is a 64-char SHA-256 hash

```bash
# tests/anonymization_audit.sh
#!/bin/bash
# Real charger IDs from earlier prompts (REDACTED-STATION-PREFIX, etc.)
if grep -rE "REDACTED-STATION-PREFIX" --include="*.csv" --include="*.md" --include="*.ipynb" .; then
    echo "FAIL: raw charger ID found"
    exit 1
fi
# IPv4 patterns
if grep -rE "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" --include="*.csv" --include="*.md" --include="*.ipynb" .; then
    echo "FAIL: IP address found"
    exit 1
fi
echo "PASS"
```

### Suite F — End-to-end pipeline

**F1. `docker compose up` cold start**
- **What it checks:** from a fresh clone, `cp .env.example .env && docker compose up` starts all three services and UI responds on `localhost:8000` within 30s
- **Pass criteria:** three containers healthy, UI returns 200 OK

**F2. Full replay produces expected alert volume**
- **What it checks:** on a full 90-day replay at 60× speed, the alert count per category matches the taxonomy volume within ±5%
- **Pass criteria:** alert counts per category logged and compared to `data/reference/error_taxonomy.csv`

**F3. UI shows priority sorting**
- **What it checks:** during replay, headless-browser test asserts P1 alerts appear above P2 above P3 in the DOM
- **Pass criteria:** DOM order matches priority order at any snapshot in time

**F4. Drift panel loads for demo connector**
- **What it checks:** clicking the demo connector in the dropdown renders three trend lines with anomaly markers
- **Pass criteria:** panel renders, no console errors, at least one anomaly marker visible

### Suite G — Judging-criteria alignment (subjective, but testable)

These aren't pytest — they're structured self-review checks.

**G1. Innovation (25%)**
- The two-layer architecture (deterministic + unsupervised) is documented in `docs/architecture_v2.svg` and `docs/deck_outline.md`
- The vendor code normalization angle is documented with measured coverage
- The 13s self-recovery signal is used as a real prioritization input, not just noted

**G2. Business Impact (25%)**
- The buyer is named on slide 8 (fleet operators, charge-point operators)
- Alert-fatigue reduction is quantified: P3-downgrade rate on transient err1051 events
- Deployment shape (sidecar container) is explicit

**G3. Technical Excellence (20%)**
- All 6 detectors have unit tests (Suite A)
- Layer 2 FPR is measured on chronological held-out split (Suite C1)
- Vendor coverage is measured (Suite D1)
- Architecture diagram is precise, not hand-wavy

**G4. Scalability (15%)**
- Runs on 39 stations, 5+ vendor families, 19 firmware versions — evidence in `docs/data_audit_final.md`
- Per-connector + pooled fallback strategy is documented
- Container deployment model documented, no cloud lock-in

**G5. UX (15%)**
- Priority tiers are color-coded and visible in <3 seconds of viewing the UI
- Deciding-signal text is human-readable ("self-recovered in 12s", not "recovery_seconds=12")
- Drift panel is intuitive (one dropdown, three trend lines, anomaly markers)

---

## Part 4 — The "gold-spot" definition

To feel confident the prototype is finals-competitive, all of the following must be true at end of Week 2:

### Must-pass hard gates (any failure = not finals-ready)

1. **Suite A, B, C, D, E, F all pass.** All executable tests green.
2. **FPR ≤ 5% overall on chronological held-out split.** Non-negotiable — this is the headline defensible number.
3. **6 fault categories visibly fire on real replayed data in the UI.** Not synthetic, not mocked. Real events from `status_notification` export.
4. **Vendor code normalizer coverage ≥ 80%.** Below this, the "vendor-agnostic" pitch line weakens.
5. **Anonymization audit passes (Suite E3).** A data leak in a public hackathon repo is a disqualifying event.
6. **`docker compose up` works from a fresh clone.** If a judge tries it and it fails, credibility gone.
7. **Demo dry-run recorded, ≤ 4 minutes, tells the same story as the deck.** No deck-demo mismatch.

### Should-pass soft targets (any failure = weaker but recoverable)

1. **Lead-time result documented.** Whether Layer 2 predicts Layer 1 or is orthogonal, the answer is written down. Ambiguity here hurts.
2. **Temp-asymmetry visibly climbs on demo connector.** The money-shot visual for degradation tracking.
3. **All 6 detectors handled by prioritizer, not just err1051.** Ensures the priority story generalizes.
4. **Pooled-cohort decision made and documented.** Vendor-cohort vs. global-pooled, with evidence.
5. **Speaker notes reference the same numbers on every slide.** Cross-checked against `data_audit_final.md`.

### Nice-to-have signals (bonus, don't sacrifice hard gates for these)

1. Layer 2 drift precedes Layer 1 faults by measurable margin (the strongest possible pitch line)
2. Vendor coverage ≥ 90%
3. UI includes a "download alert log" button (judge quality-of-life)
4. Detailed document is in the format the organizer prefers (not just Markdown)

---

## Part 5 — How to run all tests

```bash
# Unit + integration tests
pytest tests/ -v

# Anonymization audit
bash tests/anonymization_audit.sh

# End-to-end docker
docker compose down -v
docker compose up -d
sleep 30
curl -f http://localhost:8000/ || echo "F1 FAIL"
python tests/e2e/test_full_replay.py

# Coverage measurements
python detector/vendor_code_normalizer.py --measure-coverage \
    data/reference/error_taxonomy.csv

# FPR measurement
jupyter nbconvert --to notebook --execute notebooks/04_holdout_evaluation.ipynb
```

Add all of the above to a `Makefile` or a `scripts/run_all_tests.sh` for one-command invocation. Automate before Week 3 Day 1.

---

## Part 6 — Test cases NOT to write

To avoid over-engineering for a hackathon:

- **Do NOT** write tests asserting precision/recall on fault classification. There aren't enough labels per category for this to be meaningful.
- **Do NOT** write tests asserting lead-time is above a threshold. It's a data-dependent finding, not a design guarantee.
- **Do NOT** write load / stress tests. Fleet is 39 stations. Anything you build will handle it.
- **Do NOT** write tests for the UI's visual polish (font sizes, spacing). Judge's opinion, not verifiable.
- **Do NOT** write tests for the deck or video. Those are reviewed manually.

---

## Part 7 — When to declare Week 2 done

All of the following, in order:

1. `pytest tests/ -v` — all green
2. `bash tests/anonymization_audit.sh` — pass
3. `docker compose up` from a fresh clone — UI reachable
4. FPR number computed and ≤ 5%
5. Vendor coverage ≥ 80%
6. Demo dry-run recorded and watched by both engineers
7. Deck outline, demo script, architecture diagram v2 all committed
8. Tag `v0.2.0-week2` pushed to `main`

If step 1 or 2 fails on Day 6, extend Week 2 by one day and cut a Day 1 Week 3 task. Do not tag until green.