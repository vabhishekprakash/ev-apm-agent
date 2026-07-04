# Demo script v1 — 3–4 min narrated walkthrough (Week 2 Day 3)

Setup before recording: `docker compose down -v && MSYS_NO_PATHCONV=1
REPLAY_SPEED_MULTIPLIER=60 docker compose up` — browser on
`localhost:8000`, drift panel pre-selected on connector 2009529.

Every narration line has an on-screen anchor (Task 2 reconciliation table
at the bottom). Numbers match `docs/deck_outline.md` exactly.

---

**0:00–0:20 — problem** *(slide over black or the empty dashboard)*
> "EV charging operators find out a charger is broken when a customer
> complains. The telemetry that would have told them sits unread in their
> charging-management system. We read it."

**0:20–0:40 — what we built** *(dashboard visible, feed still quiet)*
> "This is an asset-performance agent for EV charging fleets. It watches the
> CMS event stream, detects fault sequences as they happen, and turns them
> into prioritized, explainable alerts. It tracks charger behavior — we are
> explicitly not doing battery diagnostics."

**0:40–1:30 — prioritization story** *(replay running; feed filling)*
> "This is a 90-day fleet history replaying at sixty-to-one. Watch the
> err1051 socket fault — here's one that recovered by itself in 13 seconds.
> The agent files it as P3, log-only: *[point at the grey badge and the
> deciding signal 'self-recovered in 13s']*. No technician truck rolls.
> This other one never recovered — it goes straight to P1 with 'no recovery
> observed' *[point at red badge]*. In our recovered fault history, roughly
> 4 in 10 faults self-clear within 15 seconds — that's the alert fatigue we
> delete, without hiding the real failures."

**1:30–2:20 — degradation story** *(drift panel, connector 2009529)*
> "Every closed charging session is scored against this connector's own
> learned baseline — an Isolation Forest per connector, nine hundred
> sessions of history on this one. The blue line is the session anomaly
> score; red dots are sessions that crossed the threshold. This is
> session-profile drift on real fleet data — the connector's behavior
> changing before anyone files a ticket."

**2:20–3:00 — proof + deployment** *(summary header in view)*
> "Thirty-nine stations, eighty connectors, twelve vendor brands, nineteen
> firmware versions. Our false-positive rate on a chronological held-out
> split is 3.6 percent — measured, not vibes. It deploys as a sidecar
> container next to any OCPP-compliant CMS: docker compose up, point it at
> the event stream, alerts go wherever your ops live."

**3:00–3:30 — close**
> "Charging infrastructure is being built faster than anyone is learning to
> operate it. Fleet and charge-point operators get grid-scale ops rigor
> from data they already own — no new hardware, net-zero-aligned. That's
> the agent."

---

## Task 2 — claim ↔ UI reconciliation

| Narration claim | On-screen anchor | Status |
|---|---|---|
| P3 "self-recovered in 13s" | deciding-signal column, grey badge | ✅ live (fixture + replay) |
| P1 "no recovery observed" | deciding-signal column, red badge | ✅ live |
| ~4 in 10 self-clear ≤15 s | narration only (audit flag 12) | ✅ documented, no UI element needed |
| Per-connector baseline, ~900 sessions | drift panel session count label | ✅ live (658 scored in replay + label) |
| Anomaly score + flagged dots | drift panel SVG | ✅ live |
| FPR 3.6% | narration; summary header shows live flag rate | ✅ (header shows replay flag rate — say "held-out" out loud, don't point) |
| 39/80/12/19 fleet numbers | narration only | ✅ audited |
| 6 fault categories | **NOT claimable yet** — feed shows 3 categories today | ⚠️ cut from v1 narration; add after Day 4–5 verification |
| Temperature asymmetry | — | ❌ cut (dead field, flag 11) |

## Task 3 — strongest 20-second clip (hook)

**The self-recovery downgrade at 0:40–1:00**: two visually identical
err1051 faults, one turning grey (P3, "self-recovered in 13s"), one turning
red (P1, "no recovery observed — technician"). It is the whole business
case in one screen. Use as thumbnail + opening hook of the final video.
(Runner-up: drift panel red-dot cluster, if the taxonomy story lands later.)
