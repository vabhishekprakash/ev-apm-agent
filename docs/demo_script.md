# Demo script v2 — 3–4 min narrated walkthrough (revised after dry-run #1)

Setup before recording (prefill instantly, then inject live — never point a
camera at `demo_replay` at 60×: its 79-hour span means ~50 minutes to the
first alert):

1. Terminal 1 — dashboard: `cd ui && python -m uvicorn main:app --port 8000`
2. Prefill BOTH sources at `REPLAY_SPEED_MULTIPLIER=0` (each is one command;
   run sequentially into the same dashboard):
   `DATA_DIR=data/interim/sequences_replay REPLAY_SPEED_MULTIPLIER=0
   python replay/main.py | (cd detector && ALERT_SINK=http
   ALERT_URL=http://localhost:8000/alerts python main.py)` — the real
   err-sequence export: 4 categories, all three tiers, 67 real
   self-recovered err1051 P3s. Then the same command with
   `DATA_DIR=tests/fixtures/demo_replay` — adds the GroundFailure safety
   pill, session-drift rows, and the degrade-then-fault arc; the drift
   panel auto-selects connector 4784325 with zero clicks.
3. Live beat for the camera — the streaming tail (verified ~3 s
   append-to-dashboard). Do NOT re-inject a fixture that was already
   prefilled: that produces duplicate rows on screen. Instead:
   `head -20 data/raw/logs_sample.csv > /tmp/live_feed.csv`, then
   `python replay/main.py --format raw-ocpp --follow /tmp/live_feed.csv |
   (cd detector && ALERT_SINK=http ALERT_URL=http://localhost:8000/alerts
   python main.py)` — and on camera append the prepared fault frames:
   `cat tests/fixtures/ocpp_raw/live_append_frames.csv >> /tmp/live_feed.csv`
   A new grey P3 row ("self-recovered in 5s") lands in the queue within
   ~3 seconds, and the EVENT clock and events counter jump with it.
   (Meter-only appends move nothing visible — the dashboard reacts to
   alerts; that is why the append file is a fault spine.) Narrate
   precisely: "streaming ingestion tailing a growing log — not a live CMS
   socket; the appended frames are demo frames through the same parser
   that handled the real log you saw prefilled."
4. Browser on `localhost:8000`; leave the drift panel on the auto-selected
   connector 4784325. On-camera motion for the prioritization beat comes
   from clicking a queue row (decision trace expands) and a health tile
   (drift panel switches) — both instant.

Every narration line has an on-screen anchor (Task 2 reconciliation table
at the bottom). Numbers match `docs/deck_outline.md` exactly.

---

**0:00–0:20 — problem** *(slide over black or the empty dashboard)*
> "EV charging operators find out a charger is broken when a customer
> complains. The telemetry that would have told them sits unread in their
> charging-management system. We read it."

**0:20–0:40 — what we built** *(dashboard visible, feed still quiet)*
> "This is AI maintenance decision support for EV charging fleets. It
> watches the CMS event stream, detects fault sequences as they happen, and
> turns them into prioritized, explainable maintenance recommendations —
> each with a recommended action, a likely root cause, and an impact class.
> It tracks charger behavior — we are explicitly not doing battery
> diagnostics."

**0:40–1:30 — prioritization story** *(prefilled queue on screen; click the
err1051 chip to filter, then click the P3 row — the decision trace expands
on camera)*
> "The queue behind these is a real fleet error-sequence export. Watch the
> err1051 socket fault — here's one that recovered by itself in 13 seconds.
> The agent files it as P3, log-only: *[point at the grey badge and the
> deciding signal 'self-recovered in 13s'; click the row — the decision
> trace shows every rule that fired]*. No technician truck rolls. This
> other one never recovered — it goes straight to P1 with 'no recovery
> observed' *[point at red badge]*. Across a hundred and ninety real
> occurrences of this fault, eighty percent self-recovered within fifteen
> seconds — that's the alert fatigue we delete, without hiding the real
> failures."

**1:30–2:20 — degradation story** *(drift panel, auto-selected connector
4784325)*
> "Every closed charging session is scored against this connector's own
> learned baseline — an Isolation Forest per connector, with a pooled
> fallback for sparse ones. The blue line is the session anomaly score; red
> dots crossed the flag threshold; the amber flag is the fault that
> followed. To be precise about what you're seeing: this connector is demo
> data played through our real committed model — the scores and flags are
> the model's actual outputs. On the real fleet this panel reads noisier —
> our lead-time analysis says degradation tracking is a complement to
> detection, not a crystal ball, and we published that number."

**2:20–3:00 — proof + deployment** *(summary header in view)*
> "The source system spans six hundred fifty-five chargers across more than
> a hundred and thirty manufacturer families; we validated on a delivered
> slice of thirty-nine stations, eighty connectors, nineteen firmware
> versions. The UnderVoltage alerts you're seeing are real fleet data — six
> hundred thirty-seven events in the sequence export, all caught. Our
> false-positive rate on a chronological held-out split is 3.6 percent —
> measured, not vibes; at the untuned default threshold it's 5.3 percent,
> still under our five percent bar. It deploys as a sidecar container next
> to any OCPP-compliant CMS: docker compose up, point it at the event
> stream, alerts go wherever your ops live."

**3:00–3:30 — close**
> "Charging infrastructure is being built faster than anyone is learning to
> operate it. Fleet and charge-point operators get maintenance
> recommendations with grid-scale ops rigor from data they already own —
> no new hardware, net-zero-aligned. That's maintenance decision support,
> as an agent."

---

## Task 2 — claim ↔ UI reconciliation

| Narration claim | On-screen anchor | Status |
|---|---|---|
| P3 "self-recovered in 13s" | deciding-signal column, grey badge; decision trace on click | ✅ live (day5 injection + real sequence prefill) |
| P1 "no recovery observed" | deciding-signal column, red badge | ✅ live |
| 80% of 190 real err1051 ≤15 s | narration (flag 23); the prefilled queue holds 67 real self-recovered P3s | ✅ documented |
| Degradation arc | drift panel, auto-selected 4784325 | ✅ live — **narrate as demo data through the real committed model** (real fleet reads noisier; lead-time doc) |
| Anomaly score + flagged dots + fault flag | drift panel SVG | ✅ live |
| FPR 3.6% (5.3% at untuned default) | narration; summary header shows the validated number | ✅ (say "held-out" out loud) |
| Source 655 / 130+ / delivered 39 / 80 / 19 | narration only (two-tier per claims_evidence.md) | ✅ audited |
| 6 fault categories | coverage chips + feed — all six real-event verified (flags 18/22/23/25/27); the dashboard counter reads **7 of 19** on mixed streams because it counts Under- and OverVoltage separately | ✅ claimable |
| Temperature asymmetry | — | ❌ cut (absent from delivered exports; flags 11/20/26) |

## Task 3 — strongest 20-second clip (hook)

**The self-recovery downgrade at 0:40–1:00**: two visually identical
err1051 faults, one turning grey (P3, "self-recovered in 13s"), one turning
red (P1, "no recovery observed — technician"). It is the whole business
case in one screen. Use as thumbnail + opening hook of the final video.
(Runner-up: drift panel red-dot cluster, if the taxonomy story lands later.)
