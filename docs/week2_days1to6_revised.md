# EV APM Agent — Week 2, Days 1–6 (Revised)

**Context anchor:** Week 1 closed at tag `v0.1.0-week1`. Working end-to-end: replay → detector (Layer 1: err1051 state machine + err1024 point event + telemetry-silence + Layer 2 per-connector IsoForest + pooled fallback) → minimal FastAPI UI. Both known faults fire correctly. Layer 2 FPR logged. Architecture diagram v1 photographed.

**Major mid-Week-1 finding:** Discovery of `Errornotify.csv` — the fleet's full **error taxonomy** (18,089 distinct combinations, 2.77M total fault occurrences, 19 OCPP-standard error categories). The "n=2 labeled faults" ceiling is dead. system-err1051 alone has 2,283 occurrences (not 2); system-err1024 has 531.

**This rewrites the modeling story:** Layer 1 expands from a 2-fault detector to a **6-category multi-fault detector**, and NLP normalization of ~17,300 noisy vendor codes to 19 standard buckets earns its place as a real deliverable (not future work).

**Week 2 debt from Week 1 (address in Day 1):**
1. Alert-prioritization ranking not built — Business Impact hook (25% of score)
2. UI is minimum-viable, undesigned
3. Layer 2 pooled-cohort verification pending
4. Formal held-out FPR measurement pending
5. err1024 handler final status — confirm data-owner reply or lock point-event version

**One new export needed before Day 4:** timestamped `status_notification` table filtered to `error_code != 'NoError'`, 90-day window, anonymized. Blocks Days 4–5's new work.

---

## Day 1 — Alert prioritization + taxonomy commit

### Abhishek — 2 hrs, branch `feat/abhishek-alert-priority`

**Task 1: Priority scoring model (60 min)**
Implement `AlertPrioritizer` in `detector/prioritizer.py`. Rules-based, tunable weights at top of file:

| Signal | Priority effect |
|---|---|
| err1051 with recovery ≤15s (self-cleared) | Downgrade → P3 (log only) |
| err1051 with recovery >15s or no recovery seen | Upgrade → P1 (technician) |
| err1024 (SLAC, technician-likely) | P2 default |
| Telemetry silence >90s, no StopTransaction | P1 (active session going dark) |
| Layer 2 drift, single session | P3 (watch) |
| Layer 2 drift, ≥3 consecutive sessions same connector | Upgrade → P2 (trending degradation) |
| Any alert on a connector with a P1 in last 24h | Upgrade one tier (repeat offender) |

Design the interface so **new fault categories (WeakSignal, GroundFailure, Under/OverVoltage) will slot in cleanly Day 4** — don't hardcode the alert types.

**Task 2: Wire prioritizer into alert flow (45 min)**
Every alert passes through `AlertPrioritizer` before reaching the UI sink. Payload gains `priority_tier` and `priority_score` fields.

**Task 3: Unit tests for priority logic (15 min)**
`tests/test_prioritizer.py`: assert transient err1051 → P3, non-recovering err1051 → P1, consecutive-drift → P2 escalation, repeat-offender upgrade. Synthetic alerts, no real data required.

**Acceptance:** every alert carries priority tier; 13s recovery signal demonstrably downgrades transients; consecutive drift escalates.

### Akhil — 2 hrs, branch `feat/akhil-holdout-and-taxonomy`

**Task 1: Commit Errornotify.csv as reference data (15 min)**
Move to `data/reference/error_taxonomy.csv` and commit. Already anonymized (no PII in a taxonomy table). Add to `docs/data_audit_v0.md` an addendum noting: 19 OCPP standard categories, 2.77M total events, 17,553 distinct vendor codes.

**Task 2: Formal held-out FPR measurement (60 min)**
`notebooks/04_holdout_evaluation.ipynb`. Chronological 80/20 split (most recent 20% held out, mimics production). Retrain IsoForest per-connector on the 80%. Score held-out 20%. Report:
- Overall FPR
- Per-tier FPR (heavy / medium / light)
- Per-vendor-family FPR
- Anomaly-score distribution on held-out normals

This is the headline defensible metric. If overall FPR >5%, tune `contamination` down and re-measure.

**Task 3: Verify pooled-cohort baselines (30 min)**
Plot per-vendor-family feature distributions for sparse/marginal connectors. If cohorts are coherent, keep vendor-cohort pooling. If noisy, fall back to a single global pooled model. Decision documented in `docs/layer2_scope.md`.

**Task 4: Request StatusNotification event export (15 min)**
Send SQL to data owner for the timestamped fault event export (see §5.4 in `SPEC.md`). Blocks Day 4. Do this at the START of the day — 48-hr lead time on data-owner replies is normal.

**Acceptance:** taxonomy CSV committed, FPR number locked with breakdowns, pooling decision made, StatusNotification export requested.

### Joint — 30 min

- Merge Week 1 stragglers.
- Confirm priority tiers → UI colors (P1 red, P2 amber, P3 grey).
- Confirm FPR number — both must be able to defend it.
- Confirm the taxonomy discovery is now in the pitch: "19 OCPP-standard categories, 2.77M fault events observed."

---

## Day 2 — UI polish + drift panel

### Abhishek — 2 hrs, branch `feat/abhishek-ui-polish`

**Task 1: Priority-aware alert feed (60 min)**
Rework alert list:
- Sort by priority tier, then recency
- Color-code: P1 red, P2 amber, P3 grey
- Each row: tier badge, timestamp, hashed charger (truncated), connector, fault category, classification, and the *deciding signal* text ("self-recovered in 12s" / "no recovery, technician" / "3 consecutive drift sessions")

The deciding-signal text is what makes prioritization visible to a judge — do not skip.

**Task 2: Summary header (30 min)**
Top-of-page counters, live-updating: active P1 count, P2 count, sessions processed, current FPR, categories detected (6 target by end of Week 2). Gives a 3-second "this is an ops dashboard" impression.

**Task 3: Demo-mode replay speed control (30 min)**
UI-visible speed toggle (or documented env var). Confirm replay honors `REPLAY_SPEED_MULTIPLIER` and UI keeps up under 60× compression.

**Acceptance:** prioritized, color-coded, human-readable feed with visible deciding signals + live summary header.

### Akhil — 2 hrs, branch `feat/akhil-drift-panel`

**Task 1: Per-connector drift data endpoint (60 min)**
Detector exposes per-connector feature trends over time: temp asymmetry, peak temp, CC-CV taper slope, per session in chronological order. Data behind the "degradation tracking" claim.

**Task 2: Drift visualization (45 min)**
Per-connector panel in UI: pick a connector, see feature trend lines over session history with anomaly-flagged sessions marked. Chart.js via CDN or server-rendered SVG. **Temp-asymmetry trend is the money shot** — it's the concrete, intuitive signal.

**Task 3: Pick the demo connector (15 min)**
Identify the single most demo-worthy connector — visible drift trend + known faults + high session volume. `Station-A` is the leading candidate (has both err1051 and err1024, ~4,439 normal sessions). Document choice and rationale.

**Acceptance:** judge can select a connector and see its degradation trend visually.

### Joint — 30 min

- Review UI together on Abhishek's demo machine.
- Pick demo narrative connector jointly.
- Screen-record rough 2-minute run. Watch back. Note confusions — that's demo-script raw material.
- **Check on StatusNotification export status.** If not received by Day 3 morning, follow up.

---

## Day 3 — Deck outline + demo script draft

### Abhishek — 2 hrs, branch `feat/abhishek-deck-outline`

**Task 1: Deck outline v1 (75 min)**
`docs/deck_outline.md`, 9 slides mapped to judging criteria (Innovation 25%, Business Impact 25%, Technical Excellence 20%, Scalability 15%, UX 15%):

1. **Problem** — operators lack ops rigor for EV assets; faults found by customer complaint
2. **Insight** — CMS data already carries everything needed; no new hardware
3. **What it is** — three locked framing sentences; explicitly NOT battery diagnostics
4. **Architecture** — two-layer diagram; multi-category Layer 1 + per-connector Layer 2 drift
5. **Alert-fatigue solution** — prioritization + 13s self-recovery downgrade (Business Impact centerpiece)
6. **Proof** — 39 stations, 23k normal sessions, 5+ vendors, 19 firmware versions, **2.77M fault events observed across 19 OCPP-standard categories, 6 detected by our Layer 1**, FPR number
7. **Demo** — live UI walkthrough
8. **Deployment** — sidecar container next to existing CMS
9. **Future work** — autoencoder, NL query, multi-tenant SaaS, retry-loop learning for repeat offenders

Each slide 2–3 bullets, not prose. Speaker notes reference defensible numbers.

**Task 2: Honesty audit of deck claims (30 min)**
Every claim checked against:
- "Behavior proxy, not battery diagnostic" boundary
- No "predictive maintenance" headline
- No precision/recall on faults per category (still no per-category held-out fault set)
- FPR is the quantitative claim
- "Detected 6 of 19 categories" — do NOT overclaim as "trained on 2.77M faults"; frame as "operates across the observed fault taxonomy"

**Task 3: Identify missing assets (15 min)**
List what deck needs that doesn't exist (polished architecture diagram, FPR chart, category-coverage chart, demo GIF). Log as GitHub Issues for Week 3.

**Acceptance:** 9-slide outline mapped to criteria, honesty-audited, missing assets logged.

### Akhil — 2 hrs, branch `feat/akhil-demo-script`

**Task 1: Demo script v1 (75 min)**
`docs/demo_script.md`. 3–4 min narrated walkthrough:

- **0:00–0:20** — problem, one sentence, operator's pain
- **0:20–0:40** — what we built, three framing sentences
- **0:40–1:30** — live UI: replay running, alerts streaming, err1051 self-recovering (P3) vs non-recovering (P1). Prioritization story.
- **1:30–2:20** — drift panel: demo connector, temp-asymmetry climbing, Layer 2 flagging pre-fault. Degradation-tracking story.
- **2:20–3:00** — proof: 39 stations, 2.77M fault events across 19 categories, FPR number, deployment shape (sidecar container), one future-work line
- **3:00–3:30** — close: net-zero framing, buyer is fleet + charge-point operators

Write actual narration sentences, not just topics. Time each section by reading aloud.

**Task 2: Reconcile script vs UI (30 min)**
Run demo while reading script. Every claim in narration must have a corresponding on-screen element. Where it doesn't, cut the claim or file a UI gap as an Issue for Day 4.

**Task 3: Identify strongest 20-second clip (15 min)**
Most convincing moment — likely the self-recovery downgrade or temp-asymmetry drift climb. Becomes the thumbnail/opening hook. Document.

**Acceptance:** timed 3–4 min script with real narration, claims reconciled with UI, hook moment identified.

### Joint — 30 min

- Read demo script aloud together while running UI. Time honestly.
- Cross-check: deck outline and demo script tell the same story with the same numbers.
- **Confirm StatusNotification export received.** If not, escalate. Day 4 is blocked without it.

---

## Day 4 — Multi-category fault mining (new work, unlocked by taxonomy)

**Requires:** StatusNotification event export landed on shared drive by start of Day 4.

### Abhishek — 2 hrs, branch `feat/abhishek-multicategory-detectors`

**Task 1: Category pattern audit (45 min)**
Load StatusNotification export. For each of the P1 target categories (`WeakSignal`, `GroundFailure`, `UnderVoltage`, `OverVoltage`), pull all events. For each: check sequence patterns before/after — do errors fire in bursts? Are they followed by StopTransaction? Any recovery signal like err1051's 13s? Document findings in `docs/multicategory_audit.md`.

**Task 2: Implement point-event handlers for 3 categories (60 min)**
Add to `detector/layer1.py`:
- `WeakSignalDetector` — point event, but track burst rate per connector (>5 in 5 min = escalate)
- `GroundFailureDetector` — point event, always P1 (electrical safety)
- `UnderOverVoltageDetector` — combined handler, point event, escalates if repeated on same connector within 24h

Wire into `detector/main.py`. Each emits alerts with `fault_category` field distinguishing them.

**Task 3: Extend prioritizer for new categories (15 min)**
Update `AlertPrioritizer` rules table:
- GroundFailure → P1 default (safety)
- UnderVoltage / OverVoltage → P2 default, P1 if repeated 24h
- WeakSignal → P3 default, P2 if burst (>5/5min)

Add to test file.

**Acceptance:** Layer 1 now detects 6 fault categories (err1051, err1024, WeakSignal, GroundFailure, Under/OverVoltage, telemetry-silence). All fire correctly on real replayed data.

### Akhil — 2 hrs, branch `feat/akhil-vendor-code-normalization`

**Task 1: Vendor code normalizer — rule-based (75 min)**
Create `detector/vendor_code_normalizer.py`. Parse `vendor_error_code` strings from `Errornotify.csv` taxonomy and route to OCPP standard `error_code` bucket via rules:

- `system-err*` → keep as-is (already tagged with OCPP category via `error_code` field)
- `0x*` hex codes → lookup table keyed on top ~50 hex codes by volume
- `ER###`, `C###`, `NN-NNN`, `AlarmN-ErrN` → family-family regex → OCPP category
- Freeform strings (`"SignalWeak:11/JIO 4G Jio/FDD LTE/0"`, `"R:63.9V"`) → prefix-based routing (`SignalWeak` → WeakSignal; `R:*V` → voltage-related)
- Fallback: use the `error_code` field already present (which is already the OCPP category)

Target: **~90% of the 17,553 vendor codes routed by rules.** The long tail can fall through to OCPP `error_code` — that's fine because that field is already labeled.

**Task 2: Coverage measurement (30 min)**
Report per-vendor-family and overall coverage. What % of `vendor_error_code` values route to a named OCPP category via rules vs. fall through to the `error_code` field? What % remain "OtherError"?

**Task 3: Integrate into detector event pipeline (15 min)**
On every StatusNotification event, `vendor_code_normalizer.normalize(vendor_error_code, error_code)` returns canonical category. Detector routes to the right sub-detector based on canonical category, not raw string.

**Acceptance:** vendor-code normalizer with measured coverage, integrated into detector, defensible as a "vendor-agnostic across the observed error taxonomy" pitch bullet.

### Joint — 30 min

- Merge Day 3 branches.
- Standup: confirm all 6 categories fire in the UI on replay of the fault event stream.
- Quick discussion: does the taxonomy discovery change any deck slide? Update outline if so.

---

## Day 5 — Category-coverage measurement + repo hardening

### Abhishek — 2 hrs, branch `feat/abhishek-category-metrics`

**Task 1: Per-category detection metrics (60 min)**
For each of the 6 detected categories, on replay of the fault event stream, measure:
- Total events observed
- Total events detected (should be 100% for the point-event categories)
- Alert priority distribution (what % P1/P2/P3)
- Median time-to-alert from event

Emit as `docs/category_metrics.md` and a JSON summary the UI can display.

**Task 2: UI category coverage panel (45 min)**
Add a small summary block to the UI: "6 of 19 categories detected. 4,671 P1 events, 12,203 P2, 87,301 P3 in last replay." Or whatever the real numbers turn out to be. Judge sees breadth of coverage instantly.

**Task 3: LICENSE + README polish (15 min)**
Add MIT LICENSE. Polish README with:
- Locked framing sentences (top of file)
- One-paragraph "what it is"
- Architecture diagram embedded (v1 photograph until v2 is drawn)
- Quickstart: `docker compose up`
- Demo commands
- Attribution: hackathon, team names, data provenance disclaimer

**Acceptance:** category metrics measured and surfaced in UI, repo submission-ready from a docs perspective.

### Akhil — 2 hrs, branch `feat/akhil-week3-prep`

**Task 1: Retrain Layer 2 with expanded normal set (45 min)**
Now that Layer 1 catches 6 categories, more sessions can be confidently labeled as "normal" (i.e., sessions where none of the 6 categories fired). Retrain per-connector IsoForest on the expanded normal set. Compare FPR to Day 1's number. Should be as good or better.

**Task 2: Layer 2 + Layer 1 correlation analysis (60 min)**
For connectors with Layer 2 drift alerts, check: how many later show Layer 1 fault events? This is the *lead-time story*, done honestly:
- If drift precedes faults reliably → strong pitch line ("Layer 2 flags at-risk connectors N sessions before Layer 1 detects the fault")
- If drift is uncorrelated → don't claim lead time; frame Layer 2 as "orthogonal degradation tracking"

Document result in `docs/layer2_leadtime.md`. This is the single strongest pitch differentiator if it lands.

**Task 3: Data audit final refresh (15 min)**
Update `docs/data_audit_v0.md` → rename `data_audit_final.md`. Include the taxonomy numbers, category-coverage numbers, refreshed FPR, and the lead-time finding.

**Acceptance:** Layer 2 retrained, lead-time analysis done and documented, data audit final version committed.

### Joint — 30 min

- Merge Day 4 branches.
- Review lead-time finding together. This determines the deck's central pitch line — decide it now.
- Screen-record demo dry-run #2 (post-Day-4 category expansion). Watch back. Note any UI gaps.

---

## Day 6 — Week 2 close, dry-run recording, Week 3 kickoff plan

### Abhishek — 2 hrs, branch `feat/abhishek-demo-record`

**Task 1: Full demo dry-run recording (75 min)**
End-to-end demo, run and recorded. Not the final take — a rehearsal. Include:
- All 6 categories firing during replay
- Priority tier examples (P1/P2/P3 each visible)
- Drift panel walkthrough on demo connector
- Category coverage panel

Watch back. Time it. Note every moment that confuses or lingers.

**Task 2: UI final polish list (30 min)**
Based on watch-back, list every UI gap. Prioritize into "must-fix Week 3" vs "acceptable for final."

**Task 3: Demo script revision v2 (15 min)**
Update `docs/demo_script.md` based on what actually worked in the dry-run. This becomes the recording script for Week 4.

**Acceptance:** dry-run recorded and watched, UI fixes prioritized, demo script v2 committed.

### Akhil — 2 hrs, branch `feat/akhil-architecture-v2`

**Task 1: Polished architecture diagram (75 min)**
Rebuild `docs/architecture_v1.png` (whiteboard photo) as `docs/architecture_v2.svg` in Excalidraw, draw.io, or Mermaid. Show:
- CMS event stream (real prod) OR replay harness (demo mode) as input
- Detector service: Layer 1 sub-boxes (6 category detectors + vendor code normalizer), Layer 2 sub-boxes (feature extractor + per-connector IsoForest + pooled fallback)
- Alert prioritizer between detector and UI
- UI as output (or alerts pushed to Slack/PagerDuty/CMS write API in production)
- Offline training pipeline (dashed lines) feeding Layer 2 models

Commit both the source file (`.excalidraw`, `.drawio`, or `.mmd`) and the exported SVG/PNG.

**Task 2: Week 3 plan draft (30 min)**
`docs/week3_plan.md`. Should cover:
- Deck slides built from outline (actual slides in Google Slides or PowerPoint)
- Final demo recording
- Final documentation write-up (the "detailed document" deliverable)
- Repo make-public sequence
- Any Week 2 debt (UI fixes, missing features flagged from dry-run)

**Task 3: Tag `v0.2.0-week2` and update SPEC.md (15 min)**
Update the master `SPEC.md` with Week 2 findings: taxonomy discovery, 6-category detector list, vendor code normalization, updated FPR, lead-time result, deck outline, demo script status. Tag the release.

**Acceptance:** polished architecture diagram in repo, Week 3 plan drafted, SPEC.md updated, `v0.2.0-week2` tag pushed.

### Joint — 60 min (extended for Week 2 close)

**Task 1: Week 2 retro (30 min)**
Three questions:
- What's demoable end-to-end now that wasn't at Week 1 close?
- What's on paper but not verified?
- What did the taxonomy discovery change that we didn't fully absorb?

**Task 2: Week 3 kickoff planning (30 min)**
Agree Days 1–3 of Week 3 with concrete tasks. Should focus on: slide-building, final demo recording, detailed documentation.

---

## End-of-Week-2 checklist

- [ ] Alert prioritization live, 3 tiers, deciding signal visible in UI
- [ ] Formal FPR on chronological held-out split, per-tier + per-vendor
- [ ] Pooled-cohort decision made and documented
- [ ] UI polished: color-coded feed, summary header, drift panel, category coverage
- [ ] Demo connector chosen
- [ ] Deck outline v1 (9 slides, mapped to criteria, honesty-audited)
- [ ] Demo script v2 (timed, real narration, reconciled with UI, hook moment identified)
- [ ] `Errornotify.csv` committed as `data/reference/error_taxonomy.csv`
- [ ] StatusNotification event export landed and processed
- [ ] Layer 1 detects 6 fault categories (err1051, err1024, WeakSignal, GroundFailure, Under/OverVoltage, telemetry-silence)
- [ ] Vendor code normalizer built with measured coverage
- [ ] Per-category detection metrics measured, surfaced in UI
- [ ] Layer 2 retrained on expanded normal set
- [ ] Lead-time analysis done, deck pitch line decided
- [ ] Data audit final version committed
- [ ] Architecture diagram v2 (proper tooling, not whiteboard)
- [ ] Demo dry-run recorded and watched
- [ ] README polished, LICENSE added
- [ ] All Week 2 branches merged, `main` clean, tagged `v0.2.0-week2`
- [ ] `docs/week3_plan.md` drafted

---

## Risks flagged into Week 3

1. **6-category expansion is real but shallow** — each new category is a point-event detector, not a state machine. This is honest and adequate, but don't let the deck imply deeper analysis than exists.
2. **Vendor code normalizer coverage may miss** — if rule-based coverage <80%, either invest more time or reframe as "normalization for the top N categories by volume."
3. **Lead-time story is a coin flip until Day 5 finishes** — if Layer 2 drift doesn't correlate with Layer 1 events, the pitch's central differentiator gets weaker. Have a backup framing ready ("orthogonal degradation signal for infrastructure health tracking").
4. **UI feature creep** — 6 categories, 3 tiers, drift panel, coverage panel, summary header is a lot to fit legibly. If UI gets crowded, cut coverage panel first.
5. **Deck vs demo consistency** — with the mid-week scope expansion, ensure Week 3 doesn't ship a deck claiming 6 categories and a demo showing 2.

## Deferred to Week 3

- Actual slides built from outline
- Final demo recording (multiple takes, best cut)
- "Detailed document" deliverable — write-up covering architecture, data, methods, results, deployment
- Repo made public
- Submission package assembled                                                                              