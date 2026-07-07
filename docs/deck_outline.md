# Deck outline v1 — 9 slides (Week 2 Day 3)

Mapped to judging criteria: Innovation 25% / Business Impact 25% /
Technical Excellence 20% / Scalability 15% / UX 15%.
Every number below passed the honesty audit (bottom of file).

## 1. Problem *(Business Impact)*
- EV charge-point operators run critical infrastructure with no ops rigor:
  faults are found by customer complaint, not monitoring.
- Downtime = lost revenue + stranded drivers; technicians dispatched blind.

## 2. Insight *(Innovation)*
- The CMS event stream already carries everything needed — status codes,
  meter values, session lifecycles. **No new hardware.**
- Fault signatures are legible in OCPP telemetry if you know the sequences.

## 3. What it is *(framing — locked sentences)*
- An asset-performance agent that watches the CMS event stream and turns raw
  telemetry into prioritized, explainable fault alerts.
- It tracks charger *behavior* over time — a behavior proxy, explicitly NOT
  battery diagnostics.
- It runs beside any OCPP-compliant CMS: replay today, live stream in
  production.

## 4. Architecture *(Technical Excellence)*
- Two layers: deterministic Layer 1 (fault-sequence state machines +
  telemetry-silence) and Layer 2 per-connector Isolation Forests with a
  pooled fallback for sparse connectors.
- Alert prioritizer between detection and UI — every alert carries its tier
  and the deciding signal.
- [Architecture v2 diagram — asset issue filed]

## 5. Alert-fatigue solution *(Business Impact centerpiece)*
- Rules-based tiers: self-recovered faults (≤15 s) auto-downgrade to P3 log
  entries; unrecovered faults escalate to P1 technician dispatch.
- Real err1051 events (n=190): **80% self-recover within 15 s (median
  10 s)** — the downgrade deletes exactly that noise. Across ALL fault
  types only ~42% self-clear (n=2,041) — the majority of everything else
  is dispatch-worthy, which is why every other category defaults P2/P1.
- Trending degradation (≥3 consecutive drift sessions) and repeat offenders
  escalate automatically.

## 6. Proof *(Technical Excellence / Scalability)*
- Fleet observed: **39 stations, 80 connectors, 12 vendor brands, 19
  firmware versions.**
- **10,090 delivered normal sessions** modeled (23,084 audited at source;
  balance pending re-export).
- Error taxonomy delivered and committed: **19 OCPP-standard categories,
  17,857 distinct vendor codes — 100% resolve to a labeled category**
  (0% unlabeled residue; PII-scrubbed before commit).
- **Headline metric: 3.62% false-positive rate** on a chronological held-out
  split (n = 2,015), per-tier breakdown available.
- **6 of 19 categories detected; 5 real-event verified at 100% detection**
  (err1024 99/99, GroundFailure 79,480/79,480, WeakSignal 150/150,
  Under/OverVoltage 688/688, telemetry-silence) — err1051's full state
  machine fixture-verified with real sequence-shape + recovery validation
  (80% ≤15 s, n=190).

## 7. Demo *(UX)*
- Live UI: replay streaming, P1/P2/P3 color-coded feed with deciding
  signals, summary header, per-connector drift panel on the demo connector
  (Station-A plug 1 — 946 real fault episodes).

## 8. Deployment *(Scalability)*
- Sidecar container beside the operator's existing CMS — subscribes to the
  event stream (poll/queue/webhook), pushes alerts to Slack/PagerDuty/CMS
  write API. `docker compose up` today.
- Scale path: CMS vendor licenses detection logic as a platform feature.

## 9. Future work *(one slide, no promises)*
- Autoencoder Layer 2, NL fault query, multi-tenant SaaS, retry-loop
  learning for repeat offenders.

---

## Honesty audit (Task 2)

| Claim | Status |
|---|---|
| "Behavior proxy, not battery diagnostics" | Framing locked on slide 3; nothing in slides 4–7 crosses it. |
| No "predictive maintenance" headline | Absent. Drift panel is "degradation tracking". **Day 5 verdict: the lead-time analysis came back negative (lift 0.57× — docs/layer2_leadtime.md); the pitch line is "orthogonal degradation tracking", permanently, unless richer features change the result.** |
| No per-category precision/recall | None claimed anywhere — no held-out fault set exists. FPR is the only quantitative claim. |
| FPR 3.62% | Measured, chronological holdout, notebook 04, n=2,015. Deployed threshold −0.1187. Defensible by both presenters. |
| "19 categories / 17,857 vendor codes / 100% resolved" | Taxonomy delivered 2026-07-06, PII-scrubbed, committed as data/reference/error_taxonomy.csv; coverage measured (0.9% shape-rules + labeled-field fallback — framed as "resolves", never "routed by rules"). |
| "6 of 19 categories, 5 real-verified" | Real fault exports delivered 2026-07-05/06: detection 100% per category on 80k+ real events; err1051 machine needs a combined status+meter+txn window (flag 23) — stated as such. |
| "80% of err1051 self-recovers ≤15 s (median 10 s)" | Measured on 190 real err1051 events (flag 23); the mixed-fault 42% (n=2,041, flag 12) is quoted alongside — both attributed. |
| Temperature/asymmetry claims | **None** — temperature field is dead in real data (flag 11). |
| 23,084 sessions | Stated as "audited at source"; modeling claims use the delivered 10,090 only. |

## Assets (all delivered)

1. Architecture v2 — docs/architecture_v2.svg (+ .mmd source).
2. FPR chart — docs/assets/fpr_chart.png.
3. Category-coverage chart — docs/assets/category_coverage.png.
4. Hook GIF — docs/assets/hook_selfrecovery.gif (final video: Week 3).
