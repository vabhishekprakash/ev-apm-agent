# Week 3 plan (drafted at Week 2 close, 2026-07-04)

## Week 2 retro (Joint Task 1)

**What's demoable end-to-end now that wasn't at Week 1 close:**
- Prioritized, color-coded alert feed with deciding signals (the 13s
  downgrade is visible, not just implemented); live stats header + category
  coverage chips; per-connector drift panel on real replay data.
- All 6 target fault categories firing through the containerized stack —
  UnderVoltage verified on 18 real events (flag 18), the rest
  fixture-verified.
- Two-source demo runbook proven (compose raw replay + fault-story
  injection onto one dashboard).

**On paper but not verified:**
- WeakSignal / GroundFailure / err1051 / err1024 on *real* events — blocked
  on the fault-event export (request sent; escalate Week 3 Day 1).
- Vendor-code normalizer coverage % — blocked on Errornotify.csv delivery.
- Lead-time on richer features — current verdict is negative
  (docs/layer2_leadtime.md); stays "orthogonal degradation tracking" unless
  the measurand re-export changes it.

**What the taxonomy discovery changed that we didn't fully absorb:**
- The story stopped being "2 labeled faults" and became "operate across the
  observed taxonomy" — but the taxonomy FILE never arrived. Week 2 built the
  machinery (normalizer, category detectors, coverage tooling) against
  documented shapes; the pitch keeps provenance notes until the CSV lands.
  Absorb this: chase the two data deliveries before polishing anything else.

## Week 3 Days 1–3 (Joint Task 2 — concrete kickoff)

**Day 1 — slides + data chase**
- Build deck slides 1–6 from `docs/deck_outline.md` (Google Slides).
- FPR chart + category-coverage chart from notebooks 04 / category_metrics
  (issues #20, #21).
- Escalate both pending exports (fault events, Errornotify) — morning.

**Day 2 — UI must-fixes + slides 7–9**
- Feed sort toggle (tier | newest) and category filter chips
  (docs/demo_dryrun_w2.md must-fix list).
- Slides 7–9 + speaker notes; numbers cross-checked against
  data_audit_final flags 14–18.

**Day 3 — demo takes**
- Record demo per script v2 two-source runbook; multiple takes; capture the
  20-second hook clip (issue #22).
- Watch-back → demo script v3 if needed.

## Rest of Week 3
- "Detailed document" deliverable: architecture, data, methods, results,
  deployment — assembled from docs/ (audit final, layer2_scope, leadtime,
  category_metrics, demo runbook).
- Repo make-public sequence: final governance sweep (no raw CSMS data, no
  secrets), squash any stray branches, README badge pass, then flip.
- If the fault-event export lands: real-event verification for the remaining
  categories + regenerate category_metrics + flip deck slide 6 from
  "target" to "detected".

## Week 2 debt carried
- UI must-fix list (sort toggle, filter chips) — Day 2 above.
- Errornotify.csv taxonomy commit + normalizer coverage measurement.
- err1024 sequence confirmation (data owner) — point-event handler stays
  final otherwise.
