# EV APM Agent — Team Video Script & Screen Guide

**Purpose of this doc:** everything your team needs to record the 3–4 minute
submission video in one pass — what's actually built and working, what to say,
which screen is on camera at each second, which button to press, and exactly
what should appear when you press it. Every number below is reproducible from
the committed repo (see `docs/claims_evidence.md`); every screen behavior was
tested with Playwright before this doc was written.

---

## PART 1 — What's actually working (read this before recording)

Not a wishlist. Everything in this section renders live, passes its test, or
is measured from a committed file.

### The core pipeline
- **Layer 1 — deterministic detection.** Six fault categories, all real-event
  verified: err1051 (5-step state machine), err1024, telemetry-silence,
  WeakSignal, GroundFailure, Under/OverVoltage. A vendor-code normalizer
  resolves the delivered 659-code taxonomy to these categories at 100%.
- **Layer 2 — learned degradation tracking.** Per-connector Isolation Forest,
  pooled fallback for sparse connectors, **3.62% false-positive rate** on a
  chronological held-out split (n=2,015) — reproduces via
  `notebooks/04_holdout_evaluation.ipynb`.
- **The prioritizer.** Every alert gets a P1/P2/P3 tier plus a plain-English
  "deciding signal" — the business centerpiece: a fault that self-recovers in
  seconds is not the same event as one that never recovers.
- **92 automated tests, all green.** Anonymization audit passes. Cold
  `docker compose up` from a fresh clone works and auto-populates.
- **Raw OCPP-J log ingestion**, including a streaming tail mode
  (`--follow`) — verified appending a real frame to a growing log produces a
  new row on the dashboard in **2.6 seconds**.

### The headline numbers (all reproducible — cite these, not others)
| Number | What it means | Where it comes from |
|---|---|---|
| **80% of 190 real err1051 events self-recover ≤15s** (median 10s) | The alert-fatigue story | `docs/category_metrics.md` |
| **3.62% false-positive rate** | Layer 2 is measured, not vibes | notebook 04, n=2,015 |
| **6 of 19 OCPP categories, all six real-event verified** | Not synthetic, not mocked | `docs/category_metrics.md` (dashboard UI counter shows "7 of 19" because it splits Under/OverVoltage — mention this only if asked) |
| **659 canonical vendor codes, 100% resolved** | Vendor-agnostic normalizer works | `detector/vendor_code_normalizer.py --measure-coverage` |
| **655 chargers / 130+ manufacturer families** (source scale) | Real-world scale, honestly tiered | `data/reference/manufacturer_inventory.csv` |
| **39 stations / 80 connectors / 10,090 sessions** (delivered/validated) | What we actually built and measured on | `data/reference/*.csv` |

**Do not say:** "predictive maintenance," "battery health," any precision/recall
number, any dollar figure, or "trained on the 33.5M source events" (we
modeled the delivered 10,090). These are locked anti-claims — say so if asked
why, it's a strength, not a gap.

### The UI — what's on screen and what it does
1. **Maintenance queue** — prioritized P1 (red) / P2 (amber) / P3 (grey) rows,
   each with category, impact class, recommended action, and a plain-English
   deciding signal. Click any row → it expands.
2. **"Why this recommendation" decision trace** — the panel that opens on
   click. Shows Detected → Likely cause → Deciding rule → (for err1051)
   Self-recovery check → Escalations → Recommendation → Conclusion → a
   one-sentence "In short" summary. Footer states plainly: *"Recorded
   decision logic — deterministic rules and lookups; the summary restates
   the fields above, nothing is generated."* This is the panel that survives
   a judge cross-checking against the code.
3. **Category coverage** — a fraction bar ("N of 19"), bright chips for seen
   categories sorted worst-tier-first, a labeled row of dim "not yet
   observed" chips for the rest.
4. **Connector health** — Faulted / At-risk / Degrading / Healthy tiles,
   clickable, feeds the drift panel.
5. **Per-connector drift chart** — the money shot. Auto-selects a connector
   with zero clicks on launch. Shows the anomaly-score line, a shaded
   "flagged zone" above the threshold, ringed red dots on flagged sessions,
   and amber flag markers where a real fault followed.
6. **Topbar** — pipeline-link status dot, live event clock, throughput
   readout ("live · N events/s") that moves during the streaming beat.

### The one honesty caveat to narrate — say it, don't hide it
The drift panel's default connector (**4784325**) plots **demo session data
run through the real, committed model** — not live fleet history. Say this
out loud when the panel is on screen: *"This connector is demo data played
through our real committed model — the scores and flags you're seeing are
the model's actual outputs. On the real fleet this panel reads noisier —
we measured that and published it as an honest negative result."* This
line is what separates you from a team that got caught overclaiming.

---

## PART 2 — Pre-recording setup (do this once, before you hit record)

Three terminals. Do this in order — **do not** skip straight to step 3, and
**do not** replay `demo_replay` at 60× (its history spans ~79 hours of event
time; you'd wait ~50 minutes for the first alert on camera).

**Terminal 1 — the dashboard**
```bash
cd ui && python -m uvicorn main:app --port 8000
```

**Terminal 2 — prefill BOTH real and demo data, instantly (run one after the
other, each completes in a few seconds)**
```bash
DATA_DIR=data/interim/sequences_replay REPLAY_SPEED_MULTIPLIER=0 \
  python replay/main.py | (cd detector && ALERT_SINK=http \
  ALERT_URL=http://localhost:8000/alerts python main.py)

DATA_DIR=tests/fixtures/demo_replay REPLAY_SPEED_MULTIPLIER=0 \
  python replay/main.py | (cd detector && ALERT_SINK=http \
  ALERT_URL=http://localhost:8000/alerts python main.py)
```
After this, the queue is full, the coverage panel shows real category
variety, and the drift panel has auto-selected connector 4784325 with its
degrade-then-fault arc already visible. **This is your starting screen.**

**Terminal 3 — prep the live-streaming beat (don't run yet)**
```bash
head -20 data/raw/logs_sample.csv > /tmp/live_feed.csv
python replay/main.py --format raw-ocpp --follow /tmp/live_feed.csv | \
  (cd detector && ALERT_SINK=http ALERT_URL=http://localhost:8000/alerts \
  python main.py)
```
Start this terminal running *before* you begin recording narration for the
live-streaming beat (Scene 5) — it needs a few seconds to catch up on the
backlog. Leave the append command typed but not yet executed in a fourth
window:
```bash
cat tests/fixtures/ocpp_raw/live_append_frames.csv >> /tmp/live_feed.csv
```
Pressing Enter on that line is your camera cue in Scene 5 — a new grey P3
row lands within **~3 seconds**, verified.

**Browser:** open `http://localhost:8000` fullscreen, zoom to a comfortable
recording size, and do a dry click-through once before recording (open a
trace, click a health tile, click a coverage chip) so nothing surprises you
live.

---

## PART 3 — THE SCRIPT (shot-by-shot, ~3:30 runtime)

Format per beat: **[TIME]** narration cue → **SCREEN:** what's on camera →
**ACTION:** exact click/keystroke → **SHOWS:** what appears as a result.

---

### Scene 1 — The problem (0:00–0:20)
**SCREEN:** Title card or the dashboard sitting quiet (queue already
populated from setup, but don't scroll or click yet — let it sit).

> "EV charging operators find out a charger is broken when a customer
> complains. The telemetry that would have told them sits unread in their
> charging-management system. We read it."

**ACTION:** none — hold the shot.

---

### Scene 2 — What we built (0:20–0:40)
**SCREEN:** Full dashboard, slow pan or static wide shot. Topbar and KPI band
visible.

> "This is AI Maintenance Decision Support for EV charging fleets. It
> watches the CMS event stream, detects fault sequences as they happen, and
> turns them into prioritized, explainable maintenance recommendations —
> each with a recommended action, a likely root cause, and an impact class.
> It tracks charger *behavior* — we are explicitly not doing battery
> diagnostics."

**ACTION:** none.
**SHOWS:** KPI band top row — Active P1 / Active P2 counts, false-alarm rate
(3.62%), categories-detected fraction, self-cleared percentage. This is the
first thing a viewer's eye should land on.

---

### Scene 3 — The self-recovery downgrade (0:40–1:05) — THE HOOK
**This is your strongest 20 seconds. If you only have time to nail one
scene, nail this one.**

**SCREEN:** Maintenance queue.
**ACTION:** Click the **err1051 chip** in the Category Coverage panel to
filter the queue to err1051 rows only.
**SHOWS:** Two visually similar err1051 rows, different tiers.

> "Watch the err1051 socket fault. Here's one that recovered by itself in a
> few seconds."

**ACTION:** Click on the **grey P3 err1051 row** (deciding signal starts
"self-recovered in…").
**SHOWS:** The "Why this recommendation" decision-trace panel expands
beneath the row — Detected, Likely cause, Deciding rule, Self-recovery
check, Recommendation, Conclusion, and the "In short" one-line summary.

> "The agent files it as P3, log-only — no technician truck roll. *[point at
> the trace's Self-recovery check line]* This is the actual rule that
> fired, not a summary written after the fact — the footer says so:
> deterministic logic, nothing generated."

**ACTION:** Click the row again to collapse it, then click a **red P1**
row elsewhere in the queue (any P1 with "no recovery observed" or a silence
signal).
**SHOWS:** Red badge, "Dispatch technician" in bold, a different deciding
signal.

> "This one never recovered — straight to P1, dispatch. Across a hundred and
> ninety real occurrences of this fault, eighty percent self-recovered
> within fifteen seconds. That's the alert fatigue we delete, without
> hiding the twenty percent that genuinely need a human."

---

### Scene 4 — The degradation story (1:05–1:55)
**SCREEN:** Scroll down to the Per-Connector Drift panel. It should already
be showing connector **4784325** (auto-selected — no click needed).

> "Every closed charging session is scored against this connector's own
> learned baseline — an Isolation Forest per connector, with a pooled
> fallback for sparse ones."

**ACTION:** Point at the rising blue line, then the shaded red zone above
the dashed threshold, then the ringed red dots, then the amber fault flag
at the right edge.
**SHOWS:** Flat scores early → climbing line → threshold crossed → flagged
sessions (red dots) → the err1051 fault marker right where the arc peaks.

> "The blue line is the session anomaly score. The shaded region is the
> flag zone — above that line, a session gets flagged. Red dots are
> sessions that crossed it. The amber flag is the fault that followed."

**Say the honesty line here, verbatim — do not skip this:**

> "To be precise about what you're looking at: this connector is demo
> session data, played through our real, committed model — the scores and
> flags are the model's actual outputs, not scripted. On our real fleet
> this panel reads noisier. We tested whether drift *predicts* faults ahead
> of time — it doesn't, and we published that negative result rather than
> hide it. This is a complement to detection, not a crystal ball."

**Optional 5-second addition if you have room:** click a different **health
tile** (any real connector, e.g. one marked Faulted) to switch the drift
panel and show the noisier real-fleet contrast, then click back to 4784325.

---

### Scene 5 — Live streaming ingestion (1:55–2:20) — the technical flex
**SCREEN:** Split or quick-cut to the terminal running the `--follow` tail
(from Terminal 3 setup), then back to the dashboard queue + topbar.

> "Beyond CSV replay, we built streaming ingestion — the agent can tail a
> growing OCPP-J log file and anonymize, parse, and score each frame as it
> lands."

**ACTION:** In the fourth terminal, press Enter on the prepared append
command:
```bash
cat tests/fixtures/ocpp_raw/live_append_frames.csv >> /tmp/live_feed.csv
```
**SHOWS:** Within ~3 seconds — a new grey P3 row appears at the top of the
queue ("self-recovered in 5s"), the topbar's EVENT clock updates, and the
throughput readout shows "live · N events/s."

> "That's a new fault landing on the dashboard in real time. To be exact:
> this simulates live ingestion by tailing a file — it's not a live CMS
> socket connection, and we say so in our own docs. The frames are demo
> frames run through the same parser that handled our real fleet log."

---

### Scene 6 — Proof + deployment (2:20–3:00)
**SCREEN:** Back to the full dashboard wide shot, KPI band and coverage
panel in frame.

> "The source system this was built against spans over six hundred fifty
> chargers across more than a hundred and thirty manufacturer families.
> We validated on a delivered slice of thirty-nine stations, eighty
> connectors, nineteen firmware versions, and ten thousand ninety real
> sessions. Our false-positive rate on a chronological held-out split is
> three-point-six-two percent — measured, not vibes. It deploys as a
> sidecar container next to any OCPP-compliant CMS: docker compose up,
> point it at the event stream, alerts go wherever your ops already live."

**ACTION:** none, or a slow zoom on the category coverage fraction bar.
**SHOWS:** "6 of 19" (or "7 of 19" if the split-voltage counter shows) —
if asked in Q&A why the number differs, the honest answer is the dashboard
counts Under/OverVoltage as two categories.

---

### Scene 7 — Close (3:00–3:30)
**SCREEN:** Full dashboard, static, confident final frame.

> "Charging infrastructure is being built faster than anyone is learning to
> operate it. Fleet and charge-point operators get maintenance
> recommendations with grid-scale ops rigor, from data they already own —
> no new hardware, net-zero-aligned. That's maintenance decision support,
> as an agent."

**ACTION:** Fade out or cut to a title card with the repo URL.

---

## PART 4 — Delivery notes for whoever's on camera/mic

- **Rehearse the two honesty lines out loud** (Scene 4's "demo data through
  the real model" and Scene 5's "not a live CMS socket") until they sound
  confident, not apologetic. They are your credibility, not a weakness —
  say them like you're proud of the rigor, because you should be.
- **If a click doesn't register in the first take, don't panic-click.** Every
  interaction in this script was tested to respond instantly except the
  Scene-5 append, which is 2–3 seconds — hold the shot, don't cut early.
- **Never say a number that isn't in the Part 1 table above.** If you're
  tempted to round up or add a claim mid-take, stop and re-check
  `docs/claims_evidence.md` first — every number there has a reproduction
  command a judge can run.
- **If Q&A gets adversarial**, the two hardest questions and their honest
  answers are already written out in `docs/deck_outline.md`'s honesty-audit
  table and `docs/claims_evidence.md` — read those once before the defense,
  not during it.

---

## PART 5 — Quick reference: full command block (copy-paste for a dry run)

```bash
# Terminal 1
cd ui && python -m uvicorn main:app --port 8000

# Terminal 2 (run both lines in sequence, each finishes in seconds)
DATA_DIR=data/interim/sequences_replay REPLAY_SPEED_MULTIPLIER=0 \
  python replay/main.py | (cd detector && ALERT_SINK=http \
  ALERT_URL=http://localhost:8000/alerts python main.py)
DATA_DIR=tests/fixtures/demo_replay REPLAY_SPEED_MULTIPLIER=0 \
  python replay/main.py | (cd detector && ALERT_SINK=http \
  ALERT_URL=http://localhost:8000/alerts python main.py)

# Terminal 3 (start a minute before Scene 5)
head -20 data/raw/logs_sample.csv > /tmp/live_feed.csv
python replay/main.py --format raw-ocpp --follow /tmp/live_feed.csv | \
  (cd detector && ALERT_SINK=http ALERT_URL=http://localhost:8000/alerts \
  python main.py)

# Terminal 4 (your Scene-5 camera cue — press Enter live)
cat tests/fixtures/ocpp_raw/live_append_frames.csv >> /tmp/live_feed.csv

# Browser
http://localhost:8000
```

To reset between takes: `Ctrl-C` all terminals, then re-run from Terminal 1.
No Docker required for this flow (faster iteration than `docker compose`),
but the cold-clone Docker path (`docs/RUNBOOK.md` §1) is what a judge will
actually run, so do one full Docker dry-run before submission day too.
