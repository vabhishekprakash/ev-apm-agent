# Demo dry-run #1 — Week 2 Day 6

Run (not screen-captured — rehearsal of the mechanics; the recorded takes are
Week 3 with narration): full containerized stack + fixture fault injection,
following `docs/demo_script.md`.

## Runbook that worked (two sources, one dashboard)

1. `docker compose down -v`
2. `MSYS_NO_PATHCONV=1 DATA_DIR=/app/data/raw REPLAY_SPEED_MULTIPLIER=60 docker compose up`
   — real 90-day replay: populates the **drift panel** (658 scored sessions on
   demo connector 2009529, 11 flagged), live **telemetry-silence** and
   **real UnderVoltage** alerts, stats header.
3. In a second terminal, inject the fault story over the same dashboard:
   `DATA_DIR=tests/fixtures/demo_replay REPLAY_SPEED_MULTIPLIER=1 python replay/main.py | (cd detector && ALERT_SINK=http ALERT_URL=http://localhost:8000/alerts python main.py)`
   — the combined fixture fires **all 6 categories** with the full tier
   spread (err1051 P3-transient vs P2-candidate, err1024 P2, GroundFailure
   P1, WeakSignal burst P3→P2, OverVoltage 24h-repeat P1, silence P1).

Verified end-state: 274 alerts, 8 category buckets, drift panel populated,
stats header live.

## Watch-back notes → UI polish list

**Must-fix (Week 3):**
1. ~~Stats header empty on short streams~~ — fixed this commit (stats now
   refresh on every alert, not only every 100 events).
2. Feed sorts P1s first regardless of age: during a long replay the top of
   the table goes stale while new P3s appear below the fold. Add a
   "sort: tier | newest" toggle.
3. `telemetry_silence` dominates the buffer on raw replay (230 of 274
   alerts) and pushes the interesting P1s out of the 200-alert window —
   add a per-category filter chip (click a coverage chip to filter).

**Acceptable for final:**
- Drift panel doesn't auto-select the demo connector (one manual click,
  narratable).
- Timestamps are ISO strings; relative times would read better but are not
  worth the risk this close to recording.
- Silence alerts from cap truncation are honest replay behavior; the
  narration explains them in one line.

## Demo-script changes folded into v2

- Added the two-source runbook above (compose + injection) — replaces the
  single-stream assumption.
- **New line for the proof beat:** "UnderVoltage you're seeing is real fleet
  data — 18 events in this 90-day window, all 18 caught" (audit flag 18).
- The "categories detected" counter line updated: 6 categories on screen
  (fixture-verified) with UnderVoltage + silence real-verified.
