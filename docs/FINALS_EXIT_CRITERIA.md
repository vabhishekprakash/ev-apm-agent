# EV APM Agent — Finals-Qualification Exit Criteria

**Purpose:** the single authoritative document defining what must be true for the ET AI Hackathon 2026 submission to qualify for finals. If every gate below is green, submit. If any hard gate is red, extend and fix before submitting. Soft gates and stretch targets are ranked so time-constrained trade-offs are pre-decided.

**Owner check-in cadence:** read this document at the start of Week 3 Day 1, Day 4, and Day 6. Update the status column, not the criteria.

---

## Section 0 — Project identity

**Track:** AI for Industrial EV Supply Chain & Asset Intelligence: Accelerating Net Zero
**Sub-component:** EV Asset Performance Management (APM) Agent
**Team:** Abhishek (Layer 1, integration, UI), Akhil (Layer 2, data, evaluation)
**Repo:** `ev-apm-agent`
**Submission format:** public GitHub URL + 3–4 minute demo video + detailed document

**Locked positioning statement:**
> AI Maintenance Decision Support for EV Charging Infrastructure. Real-time fault detection and per-connector degradation tracking across a heterogeneous fleet, delivered as actionable maintenance recommendations grounded in the CMS data operators already have. Not a battery diagnostic. Not predictive maintenance in the lead-time sense — decision support in the operational sense. Deploys as a sidecar container next to an existing CMS.

Every deck slide, video narration line, and README paragraph must be reconcilable with the sentence above. Deviations are disqualifying.

---

## Section 1 — Judging criteria mapping

The hackathon rubric weights each criterion. Every hard gate below is tagged with which criterion it defends. If a criterion has no hard gate defending it, we lose the weight.

| Criterion | Weight | Hard gates defending it |
|---|---|---|
| Innovation | 25% | I1, I2, I3 |
| Business Impact | 25% | B1, B2, B3, B4 |
| Technical Excellence | 20% | T1, T2, T3, T4, T5, T6 |
| Scalability | 15% | S1, S2, S3 |
| User Experience | 15% | U1, U2, U3 |

Total gates: 19 hard, 12 soft, 6 stretch.

---

## Section 2 — Hard gates (non-negotiable)

**Rule:** if any hard gate fails at the Day 6 pre-submission check, do not submit. Extend by one day, fix, re-check.

### Innovation (25%)

**I1 — Two-layer architecture is documented and demonstrated.**
Layer 1 is deterministic (state machines + point-event handlers + telemetry-silence sub-detector); Layer 2 is unsupervised per-connector anomaly detection with pooled fallback. Both are shown in the architecture diagram, both fire visibly in the demo, and both are described in the detailed document with technical justification.
- Verified by: architecture_v2.svg exists; demo shows Layer 1 and Layer 2 alerts distinctly; §3.1 of detailed document explains the choice.

**I2 — Vendor code normalization is implemented, not aspirational.**
The rule-based normalizer routes ≥80% of the 17,553 vendor error strings to one of the 19 OCPP standard categories. Coverage is measured, logged, and pitched as a real capability.
> **Status annotation (2026-07-16):** "17,553" is a stale spec-era estimate. Canonical figures (see `docs/claims_evidence.md`): **20,202 distinct vendor strings at source** (`data/reference/source_vendor_code_counts.csv`) and a **delivered working taxonomy of 659 canonical codes at 100% resolution** — the ≥80% bar is met on the delivered taxonomy, measured by `detector/vendor_code_normalizer.py --measure-coverage`.
- Verified by: `detector/vendor_code_normalizer.py` exists with tests; coverage number ≥80% documented in `docs/category_metrics.md`.

**I3 — The self-recovery signal drives a real decision, not a note.**
The 13s recovery threshold demonstrably downgrades transient err1051 events from P1 to P3, and this is visible in the demo as a concrete example ("err1051 self-recovered in 12s → downgraded to log-only").
- Verified by: demo footage shows at least one transient and one non-recovering err1051 with different tiers.

### Business Impact (25%)

**B1 — System outputs maintenance recommendations, not just alerts.**
Every alert payload carries four fields beyond category and timestamp: `maintenance_priority` (P1/P2/P3), `recommended_action` (dispatch/schedule/monitor/log), `likely_root_cause` (from category-driven lookup), and `impact_class` (revenue-impacting / safety-flagged / non-revenue transient).
- Verified by: alert schema documented; UI shows all four fields; test suite asserts every alert has all four populated.

**B2 — Alert-fatigue reduction is quantified.**
The P3-downgrade rate on transient err1051 events is measured and reported ("N% of err1051 alerts self-recover within 15s and are downgraded"). This is one of the deck's headline business numbers.
- Verified by: number computed from replay, documented in `docs/category_metrics.md`, appears on deck slide 5.

**B3 — Buyer and deployment shape are explicit.**
The deck and detailed document name the buyer (fleet operators, charge-point operators) and the deployment topology (sidecar Docker container next to an existing CMS). No SaaS or vendor-partnership fantasy in the primary pitch.
- Verified by: deck slide 8; detailed document §7.

**B4 — Per-connector health rollup exists.**
Each connector carries a health state (Healthy / Degrading / At-risk / Faulted) derived from recent Layer 2 drift trajectory and unresolved Layer 1 alerts. Rule-based, not learned. Visible in UI drift panel or a dedicated column.
- Verified by: `detector/health_rollup.py` exists; UI displays health state per connector; test asserts state transitions on synthetic drift sequences.

### Technical Excellence (20%)

**T1 — Six fault categories detected on real replayed data.**
err1051, err1024, WeakSignal, GroundFailure, Under/OverVoltage, and telemetry-silence all fire correctly on the anonymized `status_notification` export. Not synthetic, not mocked.
- Verified by: `pytest tests/test_layer1_categories.py` all pass; demo shows each category firing at least once.

**T2 — Layer 2 FPR ≤ 5% on chronological held-out split.**
Held-out 20% (most recent) of normal sessions per connector produces overall false-positive rate ≤5%. Per-tier breakdown reported (heavy / medium / light).
- Verified by: `notebooks/04_holdout_evaluation.ipynb` produces the number; test asserts it; number appears on deck slide 6.

**T3 — Reproducible runs.**
Same input → same output. IsoForest models load from disk deterministically. Fixed random seeds throughout.
- Verified by: `pytest tests/test_reproducibility.py` passes.

**T4 — Unit tests cover all detectors and the prioritizer.**
Every Layer 1 detector, the prioritizer, and the vendor code normalizer have at least one test asserting a documented behavior.
- Verified by: `pytest tests/ -v` all pass; test count ≥20.

**T5 — Feature values are physically plausible on real sessions.**
On a curated sample of 10 real normal sessions, extracted features fall within documented ranges (body temp 20–60°C, outlet temp 20–95°C, asymmetry 0–30°C, taper slope ≤0, energy >0).
- Verified by: `tests/test_layer2_features.py` passes.

**T6 — No overclaiming in the deck or document.**
No claim of predictive lead time on labeled faults. No precision/recall on fault classification. No battery health diagnostics. No fabricated dollar figures. Every quantitative claim is traceable to a computed number in the repo.
- Verified by: honesty audit checklist (§4) completed and signed off by both engineers.

### Scalability (15%)

**S1 — Fleet coverage evidenced.**
The 39 stations, 68 physical connectors, 5+ vendor families, and 19 firmware versions are called out in the deck, the demo, and the detailed document. Vendor diversity is not hypothetical.
> **Status annotation (2026-07-14):** the committed inventory is authoritative — **80 connectors** (`charger_stations.csv`), not 68 (68 was the connectorId=0-excluded count). Vendor diversity is now evidenced at **source scale: 655 chargers / 130+ manufacturer families / 209 models** (`data/reference/manufacturer_inventory.csv`), superseding "5+ vendor families". Use the two-tier framing in `docs/claims_evidence.md`.
- Verified by: numbers appear on deck slide 6, in demo narration between 2:20–3:00, and in detailed document §4.

**S2 — Per-connector + pooled fallback is documented and tested.**
Sparse connectors route to pooled vendor-cohort models. Decision (vendor-cohort vs. global-pooled) is documented with evidence.
- Verified by: `docs/layer2_scope.md` states the decision with rationale; test asserts sparse-connector fallback path.

**S3 — Container-based deployment works from a fresh clone.**
`git clone && cp .env.example .env && docker compose up` starts all three services and produces a reachable UI on `localhost:8000` within 30 seconds. No cloud services required.
- Verified by: end-to-end test `bash tests/e2e_cold_start.sh` passes on a machine that has never seen the repo before.

### User Experience (15%)

**U1 — Maintenance priority is visible in ≤3 seconds of viewing the UI.**
Color-coded tier badges (P1 red, P2 amber, P3 grey) are the first thing a viewer notices in the alert feed. Summary header shows live P1/P2/P3 counts.
- Verified by: usability review — both engineers can point to the priority signal within 3 seconds of a UI screenshot.

**U2 — Deciding-signal text is human-readable.**
Every alert carries a plain-English deciding-signal string ("self-recovered in 12s", "no recovery, technician", "3 consecutive drift sessions on this connector"). No raw variable names.
- Verified by: `tests/test_alert_readability.py` asserts no snake_case leaks into user-facing fields; manual review of 10 sampled alerts.

**U3 — Drift panel tells a story visually.**
The chosen demo connector's drift panel shows temperature asymmetry climbing over the session history, with anomaly-flagged sessions visually marked. A judge who has never used the system can look at the panel and understand "this connector is degrading."
- Verified by: usability review; hook-moment clip identified for demo.

---

## Section 3 — Soft gates (recover if you must, but don't strip)

If time-pressured Day 6, these can slip to "documented but not polished." Do not drop them entirely.

**SG1 — Lead-time analysis result documented.**
Whether Layer 2 drift precedes Layer 1 faults or is orthogonal, the answer is written in `docs/layer2_leadtime.md` with evidence. If leading, it becomes the deck's central pitch line. If orthogonal, framing shifts to "complementary degradation signal."

**SG2 — Category coverage breakdown chart in deck.**
A visual showing 6 detected of 19 observed, with volume per category. Reinforces the multi-category story.

**SG3 — Layer 2 confidence score surfaced.**
IsoForest anomaly score normalized to 0–100 confidence, visible next to Layer 2 alerts. Layer 1 alerts show confidence 100 by construction — this becomes a pitch bullet ("deterministic Layer 1 delivers certainty; probabilistic Layer 2 delivers early warning").

**SG4 — Root cause lookup covers all 6 categories.**
`detector/root_cause_map.py` has an entry for each detected category with a plain-English root cause description.

**SG5 — Impact class is triaged into three buckets.**
Revenue-impacting, safety-flagged, non-revenue transient — every alert carries one.

**SG6 — Demo narrates the maintenance-decision-support framing, not just detection.**
The word "recommendation" appears at least twice in the demo narration. The word "maintenance" appears at least three times.

**SG7 — Architecture diagram is properly tooled.**
`docs/architecture_v2.svg` from Excalidraw/draw.io/Mermaid, not a photograph of a whiteboard.

**SG8 — Detailed document exceeds 1,500 words.**
The "detailed document" deliverable is substantive, not a page. Covers problem, approach, architecture, data, methods, results, deployment, future work.

**SG9 — README is submission-quality.**
Includes locked positioning statement, quickstart (`docker compose up`), architecture diagram embedded, video link, contributors, data provenance disclaimer, LICENSE.

**SG10 — GitHub Issues are closed or moved to future work.**
`main` branch has no lingering open Issues at submission time. Anything not shipping is in `docs/future_work.md`.

**SG11 — Repo history is clean.**
No secrets ever committed (git log audit). No `data/raw/*.csv` in history. No `.env` in history.

**SG12 — Speaker notes cross-check.**
Every number spoken in the demo appears in the deck speaker notes and matches `docs/data_audit_final.md`.

---

## Section 4 — Honesty audit checklist (T6)

Both engineers walk this together on Week 3 Day 5. Both sign off.

- [ ] "Predictive maintenance" is NOT the deck headline
- [ ] "Battery health" / "state of health" / "state of charge diagnostics" appear NOWHERE in deliverables
- [ ] No precision/recall numbers on fault classification (n=2 per category, not viable)
- [ ] No dollar figures per alert
- [ ] No "days to failure" specific numbers
- [ ] No implied vendor partnerships or CMS-vendor deals
- [ ] Layer 2 lead-time claim (if made) is backed by SG1 analysis with numbers
- [ ] FPR number on every slide, video moment, and document paragraph is the same number
- [ ] Fleet stats two-tier per docs/claims_evidence.md: delivered 39 stations / 80 connectors / 10,090 sessions / 19 firmware; source 655 chargers / 130+ mfr families / 33.5M events / 103,081 sessions — consistent across deck, video, document
- [ ] "AI Maintenance Decision Support" framing consistent across all surfaces
- [ ] Every capability shown in the demo exists in the repo
- [ ] Every capability described in the document is demonstrable in the demo

Sign-off: **Abhishek ______  Akhil ______  Date ______**

---

## Section 5 — Stretch targets (bonus, do not sacrifice hard gates for these)

Ranked by ROI on judging criteria. Only pursue if all hard gates are green by Week 3 Day 4.

**ST1 — Layer 2 lead-time is measurably positive.**
Drift precedes fault by a median of N sessions with confidence intervals. Single strongest pitch line if it lands.

**ST2 — Vendor code normalizer coverage ≥ 90%.**
Above the 80% floor, adds credibility to "vendor-agnostic across observed taxonomy."

**ST3 — Category-specific reproducible sequences identified for 1+ new category.**
Beyond err1051, if any of WeakSignal / GroundFailure / Under-OverVoltage shows a reproducible pre-fault sequence in the event export, encode as a state machine. Transforms Layer 1 from "6 detectors, mostly point events" to "multi-category sequence intelligence."

**ST4 — Downloadable alert log button in UI.**
CSV export of the current alert feed. Judge quality-of-life feature.

**ST5 — Repo has a 30-second GIF in the README.**
Top-of-README animated GIF showing the demo money shot. Enormous first-impression lift for judges browsing repos.

**ST6 — Post-submission LinkedIn / X thread drafted.**
Not judged, but useful for team profile. Save 30 min Day 6 for it.

---

## Section 6 — Executable verification (single command)

By end of Week 3 Day 5, this command must produce all-green output:

```bash
make verify
# or:
bash scripts/run_all_tests.sh
```

Contents:

```bash
#!/bin/bash
set -e

echo "=== Unit tests ==="
pytest tests/ -v --tb=short

echo "=== Anonymization audit ==="
bash tests/anonymization_audit.sh

echo "=== Reproducibility ==="
python tests/test_reproducibility.py

echo "=== FPR measurement ==="
jupyter nbconvert --to notebook --execute \
    notebooks/04_holdout_evaluation.ipynb \
    --output /tmp/fpr_check.ipynb

echo "=== Vendor coverage ==="
python detector/vendor_code_normalizer.py \
    --measure-coverage data/reference/error_taxonomy.csv \
    --min-coverage 0.80

echo "=== End-to-end cold start ==="
docker compose down -v
docker compose up -d
sleep 30
curl -f http://localhost:8000/ > /dev/null
python tests/e2e/test_full_replay.py
docker compose down

echo "=== ALL GATES GREEN ==="
```

If this script exits 0, the technical bar is met.

---

## Section 7 — Deliverables inventory

Every item is required for submission. Missing any = incomplete submission.

| Deliverable | Location | Owner | Format | Hard-gate references |
|---|---|---|---|---|
| Public GitHub repo | `github.com/<org>/ev-apm-agent` | Abhishek | URL | T1–T6, S3, all SG |
| 3–4 min demo video | Hosted URL (link from README) | Abhishek | MP4, 1080p, ≤4 min | I1, I3, U1–U3, B1 |
| Detailed document | `docs/detailed_document.pdf` | Akhil | PDF, ≥1,500 words | SG8, T6, all technical |
| Architecture diagram | `docs/architecture_v2.svg` | Akhil | SVG or PNG from tooling | I1, SG7 |
| Deck | Google Slides link in README | Both | 9 slides + speaker notes | All criteria |
| README | `README.md` at repo root | Abhishek | Markdown | SG9 |
| LICENSE | `LICENSE` at repo root | Abhishek | MIT | SG9 |
| Data audit | `docs/data_audit_final.md` | Akhil | Markdown | S1, T2 |
| Test suite | `tests/` | Both | pytest + shell | T3, T4, T5, verify script |
| Submission form | Organizer portal | Akhil | as required | — |

---

## Section 8 — Go / No-go decision matrix

At Week 3 Day 6 morning standup, walk this matrix:

```
                    Hard gates green?
                      /            \
                    YES             NO
                    /                \
              Soft gates ≥80%?     Extend 1 day.
                /       \          Fix failing hard gates.
              YES        NO        Re-check.
              /           \
       All deliverables   Ship, note gaps
       present?           in postmortem.
        /      \
      YES       NO
      /          \
   SUBMIT       Complete missing.
                Re-check.
```

**No condition permits submission with a failing hard gate.** Extend before shipping broken.

---

## Section 9 — Post-submission

- Screenshot submission confirmation
- Tag `v1.0.0-submission` on `main`
- Close `v1.0-submission` GitHub milestone
- Write `docs/postmortem.md`:
  - What worked
  - What we underestimated
  - What we cut and would keep next time
  - What we kept and would cut next time
  - Numeric outcomes (FPR, vendor coverage, categories detected, tests passing)
- Archive raw video takes and shared drive contents
- Team debrief: 30 minutes, no agenda beyond the postmortem doc

---

## Section 10 — Anti-goals (things to avoid at all costs)

These are the specific failure modes most likely to eliminate the project from finals contention. Read this list on Week 3 Day 1 and Day 6.

1. **Demo-deck mismatch.** Deck claims a capability the demo doesn't show. Hard gate T6 catches this; check anyway.
2. **A single un-hashed charger ID in a notebook output.** Anonymization is not "mostly." Grep audit is mandatory.
3. **Broken `docker compose up` from a fresh clone.** Judges do try this. If it fails, credibility collapses.
4. **Overclaiming predictive lead time.** The data does not support it on labeled faults. Multiple prior scoping conversations have locked this. Do not backslide under pressure.
5. **Fabricated business numbers.** Dollar figures per alert, days-to-failure specifics, technician hours saved — all disqualifying if a judge asks how you derived them and you cannot answer.
6. **"AI-washing" the deterministic layer.** Layer 1 is rules, not ML. Say so plainly. Judges reward honest framing over hype.
7. **Feature creep in Week 3.** The scope is frozen on Day 1. Anything proposed after Day 1 goes to `docs/future_work.md`, not to `main`.
8. **Skipping the postmortem.** Not a submission gate, but the discipline signals professionalism if judges review the repo history.

---

## Section 11 — Final green-light checklist (Day 6, pre-submission)

Copy this checklist to a GitHub Issue titled `submission-day-checklist` and check off in order. Do not submit with any unchecked box.

**Hard gates (Section 2):**
- [ ] I1 — Two-layer architecture documented, demonstrated
- [ ] I2 — Vendor code normalizer coverage ≥80%
- [ ] I3 — Self-recovery signal demonstrably downgrades a transient in the demo
- [ ] B1 — Every alert has priority, action, root cause, impact class
- [ ] B2 — Alert-fatigue reduction number computed and pitched
- [ ] B3 — Buyer and deployment shape explicit in deck and document
- [ ] B4 — Per-connector health rollup exists and is visible
- [ ] T1 — Six fault categories fire on real data
- [ ] T2 — Layer 2 FPR ≤5% on chronological held-out split
- [ ] T3 — Reproducibility test passes
- [ ] T4 — ≥20 unit tests passing
- [ ] T5 — Feature values physically plausible on 10 sessions
- [ ] T6 — Honesty audit signed by both engineers
- [ ] S1 — Fleet stats two-tier (delivered 39/80/10,090/19 + source 655/130+/33.5M/103,081 per claims_evidence.md) in deck, demo, document
- [ ] S2 — Pooled fallback documented and tested
- [ ] S3 — `docker compose up` cold start works on fresh machine
- [ ] U1 — Maintenance priority visible in ≤3s of UI viewing
- [ ] U2 — All user-facing text is plain English
- [ ] U3 — Drift panel visibly tells the degradation story

**Soft gates (Section 3):**
- [ ] SG1–SG12 checked, none critical failures

**Deliverables (Section 7):**
- [ ] Repo public with LICENSE
- [ ] Video uploaded, link in README
- [ ] Detailed document exported to PDF
- [ ] Architecture diagram from proper tooling
- [ ] Deck accessible
- [ ] README polished
- [ ] Data audit final version committed
- [ ] Test suite green (`make verify` all-pass)
- [ ] Submission form completed

**Verification (Section 6):**
- [ ] `make verify` exit 0 on clean machine

**Sign-off:**
- Abhishek ______ Date ______
- Akhil ______ Date ______

Only when every box is checked: **submit.**