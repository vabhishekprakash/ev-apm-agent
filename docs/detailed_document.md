# EV Asset Performance Management Agent — Detailed Document

**ET AI Hackathon 2026** · Team: V. Abhishek Prakash (Layer 1 + integration),
Akhil Prasad (Layer 2 + data audit), Hrishikesh (testing + documentation)

*Every quantitative claim below traces to `docs/data_audit_final.md` (numbered
audit flags) or a committed notebook; this document does not re-derive them.*

---

## 1. Problem statement

EV charge-point operators run critical infrastructure with no operational
rigor: chargers fail, and the operator finds out when a customer complains.
Downtime means lost revenue and stranded drivers, and technicians are
dispatched blind — often to faults that had already cleared themselves.

The telemetry that would have caught these faults already exists. Every
OCPP-compliant charging-management system (CMS) streams status
notifications, meter values, and session lifecycle events. Nobody is reading
it for fault signatures.

**What we built** is **AI Maintenance Decision Support for EV charging
infrastructure**: an agent that watches the CMS event stream and turns raw
telemetry into prioritized, explainable maintenance recommendations — each
carrying a maintenance priority, confidence, likely root cause, recommended
action, and impact class. It
tracks charger *behavior* over time — a behavior proxy, explicitly **not**
battery state-of-health or state-of-charge diagnostics. It runs beside any
OCPP-compliant CMS: replaying historical exports today, consuming a live
stream in production.

## 2. Approach

Two detection layers with complementary failure modes:

- **Layer 1 — deterministic.** State machines and point-event detectors for
  known fault signatures, fed through a vendor-code normalizer that resolves
  the delivered taxonomy's 659 canonical vendor codes onto the 19 OCPP-standard
  categories (the source CMS logs 20,202 distinct vendor strings —
  `data/reference/source_vendor_code_counts.csv`).
  Deterministic detection is precise, explainable, and needs no training data
  — the right tool for faults whose signatures are documented.
- **Layer 2 — unsupervised drift.** A per-connector Isolation Forest scores
  every closed charging session against that connector's own learned
  baseline, catching degradation that has no named fault code. Sparse
  connectors fall back to vendor-family pools, then a global pool.

Between detection and every alert sink sits an **alert prioritizer** that
assigns each alert a P1/P2/P3 tier and a human-readable deciding signal. This
is the alert-fatigue answer and the project's business centerpiece: a fault
that self-recovers in seconds is not the same event as one that never
recovers, and the operator should never see them at the same priority.

## 3. Architecture

```
CMS event stream (prod)  ─┐
                          ├─► Vendor-code normalizer ─► Layer 1 detectors ─┐
Replay harness (demo)   ──┘                         └─► Session tracker ───┤
                                                        └─► Layer 2 drift ──┤
                                                                            ▼
                                                                   Alert prioritizer
                                                                     (P1/P2/P3 +
                                                                    deciding signal)
                                                                            │
                                            ┌───────────────┬───────────────┤
                                            ▼               ▼               ▼
                                       UI dashboard    stdout JSON    Slack / PagerDuty
                                       (localhost:8000)               / CMS write API (prod)

Offline (training):  normal_sessions + recovered history
                     → notebooks 03–05 → models/*.pkl (committed)
```

Full diagram: `docs/architecture_v2.svg` (Mermaid source `architecture_v2.mmd`).

Three containerized services — `replay`, `detector`, `ui` — brought up by a
single `docker compose up`. Replay emits time-ordered JSON events; the
detector consumes them, runs both layers, and streams prioritized alerts; the
UI renders a live operator dashboard. No cloud dependency.

## 4. Data

Anonymized OCPP telemetry exports from a production CMS. Governance is
enforced in-repo: raw CMS data is never committed (gitignored), charge-box
IDs ship as SHA-256 hashes, geo coordinates are rounded to ~1 km, and
customer/RFID/IP fields are dropped at export. A committed audit script
(`tests/anonymization_audit.sh`) gates the repo and **caught real PII in a
delivered taxonomy before commit** — 16,260 card-tag values, 3,807
subscriber-phone rows, and 950 routable IPs, all masked (audit flag 22).

**Two-tier fleet framing.** *Source scale* (the production CMS, evidenced by
aggregate-count CSVs under `data/reference/`, not reproducible from the
delivered slice): **655 chargers across 130+ manufacturer families and 209
manufacturer-model configurations, 33.5M events (3.4M status + 30.1M
telemetry), and 103,081 sessions** (`manufacturer_inventory.csv`,
`source_event_totals.csv`, `source_session_count.csv`). *Delivered / validated
slice* (what the system was built and measured on): **39 stations, 80
connectors, 19 firmware versions, and 10,090 normal sessions**
(`total_stations.csv`, `charger_stations.csv`, `normal_sessions.csv`).

Real fault data arrived late and in pieces, each analyzed and documented:

- `error_taxonomy.csv` — 17,954 rows, 19 OCPP categories, **659 distinct
  canonical vendor codes** (the delivered working taxonomy). The source CMS
  logs 20,202 distinct vendor strings over 1.74M occurrences
  (`source_vendor_code_counts.csv`); the delivered 659 resolve 100% (flag 22).
- `missing_real_faults.csv` — 79,681 real fault events: GroundFailure 79,480,
  WeakSignal 150, OverVoltage 51 (flag 22).
- `err1024_err1051_status_sequences.csv` — 21,910 rows of real err-code
  sequences across 6 connectors (flag 23).
- `err1024_crash_signature.csv` — the err1024 mechanism, 3 real events
  (flag 21).

**Honest data limitations.** Temperature was absent (all-zero) in every
fault-window export (flags 11/20); a late wide-matrix export proved real
values exist at source (28–66 °C, n=79 — flag 26), and a final post-freeze
delivery added 65,994 located readings (Body/Outlet sensors — flag 27). Both
arrived after the Week 3 scope freeze, so temperature features stay out of
this submission and are ledgered as future work. The err1051 machine is
real-verified end-to-end on its status spine (88/88 real sequences, flag 25)
and on a full connector-month with transaction linkage (2/2 episodes, flag
27); its meter-zero corroborating step is exercised only on fixtures, because
no delivered fault window carries meter rows.

## 5. Methods

**Layer 1.** `err1051` is a five-step state machine
(IDLE → first-seen → meter-zero → second-seen → stop → recovery) that
classifies transient (≤15 s) versus technician-dispatch (>15 s) recoveries.
`err1024` is a point-event handler confirmed final by its crash signature —
"energized but never charging" (227 V nominal, current/power ≈ 0), no retry
sequence to model (flag 21). Telemetry-silence fires when an active session
goes quiet past a threshold. WeakSignal, GroundFailure, and Under/OverVoltage
are point-event detectors keyed on the canonical category from the vendor-code
normalizer. A schema difference between fixtures and real streams — system-err
codes live in `vendor_error_code` with `error_code=OtherError` — was found on
the real export and handled by matching either column (flag 23).

**Prioritizer.** Rules with tunable weights at the top of the file: transient
err1051 → P3, unrecovered → P1, GroundFailure → P1 (safety), and data-driven
escalations — WeakSignal bursts, 24-hour voltage repeats, ≥3 consecutive drift
sessions, repeat offenders, and a **station-wide** rule (a second connector of
the same station faulting within 60 s → P1), motivated by the finding that
**88% of real fault episodes hit both plugs within 5 s** (flag 19).

**Layer 2.** Per-connector Isolation Forests (`contamination='auto'`,
`random_state=42`) on a `duration_sec` + `start_hour` feature vector, with
vendor-family and global pooled fallback for sparse connectors. The SPEC's
default threshold −0.1 flagged ~6% of held-out normals; we **calibrated** to
−0.1187 (notebooks 03–04). An expanded-normal retrain from reconstructed
session history shipped only after passing an FPR-non-degradation gate
(flag 17).

**Evaluation.** The headline metric is measured on a **chronological**
per-connector 80/20 holdout (most recent 20% held out — production-mimicking),
not a random split. A lead-time analysis tested whether Layer 2 drift precedes
Layer 1 faults; it does not (lift 0.57×), so Layer 2 is framed honestly as
orthogonal degradation tracking rather than early warning (flag 17).

## 6. Results

- **False-positive rate: 3.62%** on the chronological held-out split
  (n = 2,015, threshold −0.1187). Per tier: heavy 3.3% / medium 3.5% /
  light 3.2% / pooled 6.1%; `siemens` family 10.5% (n=76) on the watch list
  (flag 14). This is the headline defensible number — comfortably under the
  5% acceptance bar.
- **Vendor-code coverage: 100% of the 659 delivered canonical codes resolve to
  a labeled OCPP category**, 0% unlabeled residue. Framed honestly: shape rules
  decide a minority (152 of 659) and the already-labeled `error_code` field the
  rest — "resolves to a labeled category", never "routed by rules" (flag 22).
- **Real-event detection: 100% per category** — err1024 99/99, GroundFailure
  79,480/79,480, WeakSignal 150/150, OverVoltage 51/51, UnderVoltage 637/637
  (plus 18/18 on the capped export). **All six categories are real-event
  verified**: err1051's machine fired end-to-end on 88/88 real status-spine
  sequences and 2/2 episodes of a full connector-month with transaction
  linkage; only its meter-zero corroborating step remains fixture-only
  (flags 18, 22, 23, 25, 27). (The dashboard's coverage counter reads
  "7 of 19" on mixed streams — it counts Under- and OverVoltage as separate
  OCPP categories; this document counts voltage as one.)
- **The 13-second story, vindicated on real data:** across 190 real err1051
  events, median recovery is 10 s and **80% self-recover within 15 s** — so
  the P3 downgrade removes exactly that noise. Across *all* fault types only
  ~42% self-clear (n=2,041), which is why every other category defaults to
  P2/P1 (flags 12, 23).
- **Pipeline:** `docker compose up` from a fresh clone brings all services up
  with the UI answering HTTP 200; 79 automated tests pass (76 on a fresh
  clone — 3 skip without a gitignored real-data file); the anonymization
  audit passes.

## 7. Deployment

The production shape is a **sidecar container** beside the operator's existing
CMS: it subscribes to the event stream (REST poll, message queue, or
webhooks) and pushes prioritized alerts to Slack, PagerDuty, or the CMS's own
write API. `ALERT_SINK` toggles between stdout (development) and HTTP (the UI
or a production sink). There is no cloud dependency and no vendor lock-in —
the same container runs on a laptop or beside a fleet's CMS. Model training is
offline; only the committed `.pkl` artifacts are loaded for inference, so
inference runs on any hardware.

Scale path: a CMS vendor licenses the detection logic and bundles it as a
platform feature.

## 8. Future work

Tracked in full in `docs/future_work.md`. Highlights:

- **GroundFailure episode dedup / rate-limiting** — the real export shows
  79,480 events in 14 months on one fleet segment (a chattering-sensor
  cohort); production needs episode-collapse before alerting.
- **err1051 meter-zero corroboration** on a meter-bearing real fault window
  (status-spine and transaction-linkage steps are already real-verified —
  flags 25/27).
- **Temperature features** — a located export (65,994 readings, Body/Outlet
  sensors) landed post-freeze (flag 27); code and tests are already in
  place, integration is queued.
- **Autoencoder Layer 2**, natural-language fault query, multi-tenant SaaS,
  and detectors for the remaining 13 OCPP categories.

## 9. Team

| Name | Responsibility |
|------|----------------|
| V. Abhishek Prakash | Layer 1 detectors, prioritizer, replay/detector/UI integration, Docker pipeline |
| Akhil Prasad | Layer 2 modeling, data audit, taxonomy + normalization, evaluation notebooks |
| Hrishikesh | Manual testing, documentation review, submission logistics |

*Provenance: anonymized OCPP telemetry from a production charging-management
system. Charge-box IDs SHA-256-hashed; geo rounded; customer/RFID/IP
dropped at export. Raw exports are never committed. MIT licensed.*
