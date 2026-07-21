# The Plain-Language Guide to This Project

*Read this first if you're new here. No engineering background needed.
When you want the deep version of anything, the last section tells you
where it lives.*

---

## 1. What is this project, in one paragraph?

EV charging stations break, and today the operator usually finds out when an
angry customer calls. But every charger already sends a constant stream of
little status messages to the operator's management software — "I'm
charging", "I stopped", "here's my meter reading", "something's wrong".
Nobody reads that stream. **We built a program that reads it** — live — and
turns it into a short, prioritized to-do list for the maintenance team:
*this charger needs a technician today, that one just hiccuped and fixed
itself, this third one is slowly going bad — book an inspection.*

We call it **AI Maintenance Decision Support for EV Charging
Infrastructure**. It needs no new hardware, no sensors, no changes to the
chargers — just the data the operator already has.

## 2. Why did we build it?

Three reasons:

1. **Faults hide in plain sight.** Our real fleet data (39 stations, 80
   charging plugs) contains *tens of thousands* of fault messages that no
   human ever looked at. One station segment logged **79,480** ground-fault
   messages in 14 months — pure noise from a chattering sensor, but nobody
   knew that, because nobody was reading.
2. **Not every fault deserves a truck.** We measured 190 real occurrences
   of the most famous fault in this fleet (a socket error called
   *err1051*): **80% of them fixed themselves within 15 seconds**. Sending
   a technician to those is wasted money. But across *all* fault types,
   only ~42% self-heal — the rest genuinely need a human. Telling these two
   groups apart automatically is the whole business case.
3. **Chargers age quietly.** Before a charger fails hard, its behavior often
   drifts — sessions get weird. A system that knows each plug's "normal"
   can wave a flag early.

## 3. How does it work? (The key logic, no math)

Think of it as **three people working an assembly line**:

**Person 1 — the Inspector (we call it "Layer 1").**
A rule-follower with a checklist. They know the exact fingerprints of six
known fault types. Example fingerprint, for err1051: *error message appears →
the electricity meter drops to zero → error appears again while finishing →
the session dies with reason "Other" → the plug comes back*. When the
Inspector sees a whole fingerprint, that's a fault — no guessing involved.
They also notice **silence**: a charging session that suddenly stops sending
meter readings is itself a bad sign, like a heart monitor going flat.
Because every charger brand writes error codes differently (we counted
~17,900 different spellings!), a **translator** sits in front of the
Inspector and converts all of them into 19 standard categories first.

**Person 2 — the Doctor (we call it "Layer 2").**
The Doctor doesn't use a checklist — they know each plug's *history*. For
every plug with enough past sessions, the machine has learned what a normal
charging session looks like *for that specific plug* (how long, at what
time of day). After every session ends, the Doctor compares it to that
plug's own normal. Sessions that look strange get flagged as "drift" — the
early hints of a plug going bad. We tested the Doctor honestly: shown
~2,000 perfectly normal sessions it had never seen, it wrongly raised its
hand only **3.62%** of the time. That's our headline accuracy number.

**Person 3 — the Triage Nurse (we call it the "prioritizer").**
Everything the Inspector and Doctor find lands on the Nurse's desk, and the
Nurse decides how loud to shout:
- **P1 (red)** — send a technician. E.g. a fault that never recovered, an
  electrical-safety fault, or *both plugs of one station failing within a
  minute of each other* (in our real data, 88% of fault episodes hit both
  plugs at once — that means the *station* is sick, not the plug).
- **P2 (amber)** — book an inspection this week. E.g. a fault that repeats,
  or the same plug drifting three sessions in a row.
- **P3 (grey)** — just log it. E.g. that err1051 that healed itself in 13
  seconds.

Every recommendation comes with the *reason in plain English* ("self-recovered
in 13s"), a *likely root cause*, a *recommended action*, and whether it's
*revenue-impacting, safety-flagged, or harmless*. That's the "decision
support" part — the screen tells you what to do, not just what happened.

## 4. How do I run it? (10 minutes, copy-paste)

You need **Docker Desktop** installed and running (green whale icon). Then,
in a terminal, from the project folder:

```bash
cp .env.example .env
docker compose up -d --build
```

Wait about 30 seconds, then open **http://localhost:8000** in your browser.
You'll see the dashboard: a dark screen titled **"EV APM — Maintenance
Decision Support"** with counters on top and an (initially quiet) table.

To make it come alive, feed it our built-in demo data. Stop and restart
with the demo dataset:

```bash
docker compose down -v
MSYS_NO_PATHCONV=1 DATA_DIR=/app/tests/fixtures/demo_replay \
  REPLAY_SPEED_MULTIPLIER=60 docker compose up
```

(`REPLAY_SPEED_MULTIPLIER=60` means "play history 60× faster than real
time". Use `0` to dump everything instantly.)

**What you should see within a minute:**
- Rows appearing in the table with **red P1 / amber P2 / grey P3 badges** —
  that's the Nurse at work.
- One grey err1051 row saying *"self-recovered in 13s"* and a red row
  saying a session went dark — the two faces of the same fault type.
- The **"Connector health"** strip: little chips saying Healthy / Degrading /
  At-risk / Faulted per plug.
- Pick a connector in the **drift dropdown** to see the Doctor's chart —
  a line of session scores with red dots where sessions looked strange.

When done: `docker compose down -v`.

## 5. How do I test it with data?

**Option A — the built-in test data (easiest).** Three demo datasets live in
`tests/fixtures/`: `demo_replay` (all six fault types at once — use this
one), `day5_replay` (the classic err1051 story), `day4_multicategory` (the
newer fault types). Swap the folder name in the command above.

**Option B — real or captured data (yours).** The system eats simple CSV
spreadsheet files — one for status messages, one for meter readings, one for
charging sessions. Put them in a folder, point `DATA_DIR` at it, run the
same command. The exact column names each file needs are in
**`docs/RUNBOOK.md`, section 3½ ("Bring your own data")** — it also shows a
one-line check that tells you if your file's format is wrong (look for
`parse_errors: 0`).

⚠️ **One iron rule:** never put company or customer data into a git commit.
Raw data folders are ignored by design; before committing anything
data-related, run `bash tests/anonymization_audit.sh` and make sure it says
`PASS`. This project once caught 16,000+ customer card IDs hiding in a
delivered file — the rule exists for a reason.

**Option C — the full self-check (one command).**
```bash
bash scripts/run_all_tests.sh
```
Green output = the 98 automated tests, the privacy audit, the pipeline, and
the accuracy gates all pass.

## 6. What this project is NOT (say this correctly to others)

- It does **not** measure battery health — it reads charger *behavior*.
- It does **not** predict failures days ahead — we tested that idea honestly
  and the data said no. It *detects* faults instantly and *tracks*
  degradation; that's what we claim.
- Layer 1 is **rules, not AI** — and we say so plainly. The learned part is
  Layer 2's per-plug "normal".

## 7. Where the deep versions live

| Want more on… | Read |
|---|---|
| The full technical write-up | `docs/detailed_document.md` |
| Every command + troubleshooting | `docs/RUNBOOK.md` |
| Where every number comes from | `docs/data_audit_final.md` (numbered "flags") |
| The picture of how it all connects | `docs/architecture_v2.svg` |
| What we'd build next | `docs/future_work.md` |
