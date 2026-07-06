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
- Reality check from 2,041 real fault episodes: ~42% self-recover within
  15 s — the downgrade removes that noise; the majority that don't are
  exactly the dispatch-worthy cases.
- Trending degradation (≥3 consecutive drift sessions) and repeat offenders
  escalate automatically.

## 6. Proof *(Technical Excellence / Scalability)*
- Fleet observed: **39 stations, 80 connectors, 12 vendor brands, 19
  firmware versions.**
- **10,090 delivered normal sessions** modeled (23,084 audited at source;
  balance pending re-export).
- Error taxonomy: **19 OCPP-standard categories, 2.77M fault occurrences**
  (per CMS taxonomy table; delivery pending — provenance note).
- **Headline metric: 3.62% false-positive rate** on a chronological held-out
  split (n = 2,015), per-tier breakdown available.
- Target: 6 of 19 categories detected by Layer 1 (err1051, err1024,
  telemetry-silence live; WeakSignal, GroundFailure, Under/OverVoltage land
  with the fault-event export).

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
| "2.77M fault events / 19 categories" | From the CMS taxonomy table cited in the Week 2 spec; **Errornotify.csv not yet delivered to the repo** — slide carries "per CMS error taxonomy" provenance until it lands. Framed as "operates across the observed fault taxonomy", NOT "trained on 2.77M faults". |
| "6 of 19 categories" | 3 live today + 3 implemented against documented patterns pending the fault-event export — slide 6 says "target", flips to "detected" only after Day 4–5 verification on real events. |
| "~42% self-recover ≤15 s" | Measured on 2,041 recovered Station-A episodes (audit flag 12). Replaces the older "13-second transient" story, which described the fast quartile only. |
| Temperature/asymmetry claims | **None** — temperature field is dead in real data (flag 11). |
| 23,084 sessions | Stated as "audited at source"; modeling claims use the delivered 10,090 only. |

## Missing assets (Task 3 — filed as GitHub issues)

1. Architecture diagram v2 (proper tooling) — due Week 2 Day 6.
2. FPR chart (per-tier bar + score distribution) for slide 6.
3. Category-coverage chart once the fault-event export lands.
4. Demo GIF / 20-second hook clip for slide 7 and the video thumbnail.
