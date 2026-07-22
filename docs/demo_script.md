# Demo script v2 — 3–4 min narrated walkthrough (revised after dry-run #1)

Setup before recording — run **docs/RUNBOOK.md §1a steps 0–4 verbatim**
(reset → stack up on `data/interim/sequences_replay` → VERIFY real
connectors → inject `demo_replay` once → VERIFY combined). Each step states
its expected output; do not proceed past a failed checkpoint. Never point a
camera at `demo_replay` at 60× (79-hour span ≈ 50 minutes to the first
alert), and never inject the same stream twice without a reset — it
duplicates every row and doubles the KPIs.

**REAL vs FIXTURE — what you may narrate as real:** rows on connectors
1679593 / 1679594 / 1880097 / 1880098 / 1989806 / 1989807 are **real fleet
data**. Rows on 4784325 / 5802030 / 1744735 (and the fixture's staged
OverVoltage/GroundFailure rows) are **synthetic**; the drift arc on 4784325
is demo sessions scored by the real committed model. If you point at it,
say so.

Then, for the live beat:
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

**0:40–1:30 — prioritization story** *(prefilled queue on screen; every row
in this beat is REAL fleet data. Click the err1051 chip to filter.)*
> "The queue behind these is a real fleet error-sequence export. Watch the
> err1051 socket fault — here's one that recovered by itself in four
> seconds. The agent files it as P3, log-only: *[point at a grey badge
> whose deciding signal reads 'self-recovered in Ns'; click the row — the
> decision trace shows every rule that fired]*. No technician truck rolls.
> Now the same fault on a connector that re-offended within twenty-four
> hours — the agent escalates it to P2, schedule an inspection *[point at
> an amber row whose signal ends 'repeat offender (P1 in last 24h)']*.
> And when something genuinely needs a human *[click the err1051 chip
> again to clear the filter; point at a red P1 UnderVoltage row reading
> 'repeated within 24h']* — straight to P1, dispatch. Across a hundred
> and ninety real occurrences of that socket fault, eighty percent
> self-recovered within fifteen seconds — that's the alert fatigue we
> delete, without hiding the real failures."

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
> false-alarm rate — that's the validated card on screen — is
> three-point-six-two percent on a chronological held-out split, at our
> calibrated threshold, comfortably under our five percent acceptance bar.
> We publish the untuned default too: five-point-two-six percent, just
> above the bar — which is exactly why we calibrated, and why we show both
> numbers. It deploys as a sidecar container next
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
| P3 "self-recovered in Ns" (REAL, sequences export) | deciding-signal column, grey badge; decision trace on click | ✅ live — ~76 such rows in the buffer |
| P2 "self-recovered; repeat offender (P1 in last 24h)" (REAL) | amber badge, same category — the escalation story | ✅ live |
| P1 dispatch tier (REAL) | red UnderVoltage row, "repeated within 24h" | ✅ live — **do not narrate a P1 err1051 "no recovery observed": no such row exists in this feed** |
| 80% of 190 real err1051 ≤15 s | narration (flag 23); the prefilled queue holds 67 real self-recovered P3s | ✅ documented |
| Degradation arc | drift panel, auto-selected 4784325 | ✅ live — **narrate as demo data through the real committed model** (real fleet reads noisier; lead-time doc) |
| Anomaly score + flagged dots + fault flag | drift panel SVG | ✅ live |
| False-alarm rate 3.62% (calibrated −0.1187, **under** the 5% bar); untuned default 5.26% (**above** the bar — never say "under" for this one) | narration matches the on-screen "FALSE-ALARM RATE (VALIDATED)" card; say "held-out" out loud | ✅ (layer2_scope.md:47) |
| Source 655 / 130+ / delivered 39 / 80 / 19 | narration only (two-tier per claims_evidence.md) | ✅ audited |
| 6 fault categories | coverage chips + feed — all six real-event verified (flags 18/22/23/25/27); the dashboard counter reads **7 of 19** on mixed streams because it counts Under- and OverVoltage separately | ✅ claimable |
| Temperature asymmetry | — | ❌ cut (absent from delivered exports; flags 11/20/26) |

## Task 3 — strongest 20-second clip (hook)

**The three-tier escalation at 0:40–1:00, on all-REAL rows** (consistent
with Task 2's table — there is **no** P1 err1051 "no recovery observed" row
in this feed, so the hook never shows one): a real err1051 self-recovers in
seconds and files itself **grey P3, log-only**; the same fault on a
connector that re-offended within 24 h turns **amber P2, schedule**; an
UnderVoltage repeat goes **red P1, dispatch**. Click the P3 row so the
decision trace expands — the exact rules that fired, ending in the
"nothing is generated" footer. It is the whole business case in one screen.
The committed hook GIF (`docs/assets/hook_selfrecovery.gif`) shows exactly
this: the trace of a real self-recovered err1051. (Runner-up: the drift
panel's degrade-then-fault arc — narrate the demo-data honesty line if
used.)
