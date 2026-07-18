# Slide source pack — build-ready

**Tagline (locked): "AI Maintenance Decision Support for EV Charging Infrastructure".** Surface vocabulary: "Maintenance Recommendation" (not "alert"), "Maintenance Priority" (not "priority tier") — every recommendation carries confidence, likely root cause, recommended action, and impact class.

Transcribe into Google Slides; every number is locked against
`docs/data_audit_final.md` (single source of truth). Asset paths are
repo-relative. Speaker notes are written to be read aloud at ~30–40 s/slide.

---

## Slide 1 — Problem *(Business Impact)*
**Bullets**
- EV charge-point operators run critical infrastructure with no ops rigor —
  faults are found by customer complaint.
- Downtime = lost revenue + stranded drivers; technicians dispatched blind.

**Speaker notes:** "EV charging operators find out a charger is broken when a
customer complains. The telemetry that would have told them sits unread in
their charging-management system. Downtime costs revenue and strands
drivers — and when a technician is dispatched, they go in blind."

## Slide 2 — Insight *(Innovation)*
**Bullets**
- The CMS event stream already carries everything needed. **No new hardware.**
- Fault signatures are legible in OCPP telemetry — if you know the sequences.

**Speaker notes:** "Our insight: the data already exists. Status codes, meter
values, session lifecycles — every OCPP-compliant charger already reports
them. Fault signatures are sitting in that stream, legible, if you know the
sequences to look for."

## Slide 3 — What it is *(locked framing)*
**Bullets** *(verbatim, do not edit)*
- An asset-performance agent that watches the CMS event stream and turns raw
  telemetry into prioritized, explainable fault alerts.
- Tracks charger *behavior* over time — explicitly NOT battery diagnostics.
- Runs beside any OCPP-compliant CMS: replay today, live stream in production.

## Slide 4 — Architecture *(Technical Excellence)*
**Visual:** `docs/architecture_v2.svg` (full-bleed)
**Bullets**
- Layer 1 deterministic: fault-sequence state machine + 5 point-event
  categories + telemetry-silence, behind a vendor-code normalizer.
- Layer 2: per-connector Isolation Forests, vendor-family pools, global
  fallback — scoring every closed session.
- Alert prioritizer between detection and every sink.

**Speaker notes:** "Two layers. Layer one is deterministic — state machines
and point detectors for known fault signatures, fed through a normalizer:
the source CMS logs over twenty thousand distinct vendor code strings, and
the delivered taxonomy's six hundred fifty-nine canonical codes all resolve
onto the nineteen OCPP standard categories. Layer two learns each
connector's normal and flags drift. Between detection and the dashboard sits the prioritizer — every
alert leaves with a tier and the reason, in plain language."

## Slide 5 — Alert-fatigue solution *(Business Impact centerpiece)*
**Visual:** `docs/assets/hook_selfrecovery.gif` (or a still of it)
**Bullets**
- Self-recovered faults auto-downgrade to P3 log entries; unrecovered escalate
  to P1 dispatch.
- Real err1051 (n=190): **80% self-recover ≤15 s, median 10 s** — that noise
  is deleted. Across ALL fault types only ~42% self-clear (n=2,041) — the
  rest deserve their P1/P2.
- Trending drift (≥3 sessions), repeat offenders (24 h), and station-wide
  patterns (both plugs <60 s) escalate automatically.

**Speaker notes:** "Here's the business case in one screen: two identical
socket faults. One self-recovers in thirteen seconds — the agent files it
grey, P3, no truck rolls. One never recovers — it goes red, P1, technician.
In one hundred ninety real occurrences of this fault, eighty percent
self-recovered within fifteen seconds. That's the alert fatigue we delete —
without hiding the forty-plus percent of everything else that genuinely
needs a human."

## Slide 6 — Proof *(Technical Excellence / Scalability)*
**Visuals:** `docs/assets/fpr_chart.png` + `docs/assets/category_coverage.png`
**Bullets**
- Source scale (production CMS, `data/reference/` evidence CSVs):
  **655 chargers / 130+ manufacturer families / 209 models, 33.5M events,
  103,081 sessions.**
- Delivered / validated slice: **39 stations, 80 connectors, 19 firmware
  versions, 10,090 normal sessions modeled.**
- Taxonomy: **19 OCPP categories; 659 delivered canonical vendor codes —
  100% resolve** (PII-scrubbed, committed). Source scale: 20,202 distinct
  vendor strings, 1.74M occurrences (`source_vendor_code_counts.csv`).
- **FPR 3.62%** on a chronological held-out split (n=2,015).
- **6 of 19 categories detected; all six real-event verified at 100%
  detection** on 80k+ real events (err1024 99/99; GroundFailure
  79,480/79,480; WeakSignal 150/150; Under/OverVoltage 688/688;
  telemetry-silence) — err1051's machine real-verified end-to-end on 88 real
  status-spine sequences plus a connector-month with transaction linkage
  (flags 25/27); only its meter-zero step remains fixture-only. *(If asked
  why the dashboard counter says "7 of 19": it counts Under- and OverVoltage
  as separate OCPP categories; the pitch counts voltage as one.)*

**Speaker notes:** "The numbers we'll defend: three-point-six-two percent
false positives on a chronological holdout — measured the way production
would experience it. One hundred percent detection on over eighty thousand
real fault events, all six categories real-event verified. And every one of
the six hundred fifty-nine vendor codes in the delivered taxonomy resolves
to a labeled OCPP category — out of more than twenty thousand distinct
vendor strings observed at source."

## Slide 7 — Demo *(UX)*
**Visual:** live demo or the dry-run recording; fallback still of the feed.
- Runbook: docs/demo_script.md (prefill sequences + demo fixture at 0;
  streaming --follow tail on camera; drift panel auto-selected on 4784325).
- Say the honesty line verbatim when the drift panel is on screen: the arc
  is demo data played through the real committed model — real fleet reads
  noisier (lead-time doc).

## Slide 8 — Deployment *(Scalability)*
**Bullets**
- Sidecar container beside the operator's existing CMS: subscribes to the
  event stream, pushes alerts to Slack / PagerDuty / CMS write API.
- `docker compose up` today — no cloud dependency.
- Scale path: CMS vendors license the detection logic as a platform feature.

## Slide 9 — Future work *(one slide, no promises)*
- Autoencoder Layer 2 · NL fault query · multi-tenant SaaS · retry-loop
  learning for repeat offenders · GroundFailure episode dedup.
  (Full ledger: docs/future_work.md.)

---

### Consistency rules for the builder
1. Numbers come ONLY from `data_audit_final.md` flags 14–28; if a slide and
   the audit disagree, the audit wins.
2. Never say: predictive maintenance, battery health, precision/recall,
   "trained on the 33.5M source events" (we modeled the 10,090 delivered
   sessions), or any temperature claim.
3. Say "resolves to labeled categories", not "routed by rules".
4. err1051: "real-verified end-to-end — 88/88 real status-spine sequences
   plus 2/2 episodes of a connector-month with transaction linkage (flags
   25/27); only the meter-zero corroborating step remains fixture-only."
