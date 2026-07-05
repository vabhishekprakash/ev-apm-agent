# EV APM Agent — Week 3, Days 1–6

**Context anchor:** Week 2 closed at tag `v0.2.0-week2`. Layer 1 detects 6 fault categories (err1051, err1024, WeakSignal, GroundFailure, Under/OverVoltage, telemetry-silence). Layer 2 per-connector IsoForest retrained on expanded normal set. Vendor code normalizer covers ~90% of 17,553 vendor strings. UI polished with priority feed, summary header, drift panel, category coverage. Deck outline v1 done. Demo script v2 timed. Architecture diagram v2 in proper tooling. Dry-run recorded and watched.

**Week 3 theme:** stop building, start shipping. Deliverables get built. Demo gets recorded. Repo goes public. Nothing new gets added unless it's on the missed-Week-2 debt list below.

**Week 2 debt carried into Week 3 (address first):**
1. UI fixes flagged in dry-run watch-back
2. Vendor code normalizer coverage — if <80%, decide reframe vs. invest
3. Lead-time analysis outcome — confirm which pitch framing is in play
4. Missing deck assets logged as Issues (FPR chart, category-coverage chart, polished diagram)

---

## Day 1 — Review, revise, confirm

- [ ] **Team standup: Week 2 retro walk-through** — read the Week 2 exit checklist together, confirm every box checked
- [ ] **Review dry-run recording as a team** — both engineers watch back, list every confusing moment
- [ ] **Rank UI fixes** — must-fix Week 3 vs. acceptable for final; assign to Abhishek
- [ ] **Confirm lead-time analysis result** — which of the two pitch framings is live ("Layer 2 flags at-risk connectors N sessions before Layer 1" vs. "orthogonal degradation signal")
- [ ] **Confirm vendor code normalizer coverage number** — lock the deck bullet
- [ ] **Read Errornotify.csv discovery back into the deck** — every slide claims "6 of 19 categories" and "2.77M fault events observed"
- [ ] **Confirm hackathon submission deadline exact date** — if organizer email still unanswered, escalate today
- [ ] **Confirm submission format** — video hosting (YouTube unlisted vs. direct file), document format, repo URL sharing method
- [ ] **Team timeline confirmation** — 6 working days remain; walk the calendar; both engineers commit hours per day
- [ ] **Assign owner per Week 3 deliverable** — slides, video, document, README, submission form
- [ ] **Open a GitHub milestone `v1.0-submission`** — all remaining Issues get attached to it
- [ ] **Freeze scope** — no new features from today onward; anything proposed goes to `docs/future_work.md`

**End of day acceptance:** Week 3 has a locked task list, owners, deadline, and scope-freeze commitment.

---

## Day 2 — UI final fixes + slide building starts

### Abhishek — 2 hrs, branch `feat/abhishek-ui-final`

- [ ] Apply must-fix UI items from Day 1 ranking
- [ ] Verify all 6 categories visibly fire during a full replay
- [ ] Verify deciding-signal text renders correctly for every priority tier
- [ ] Verify drift panel loads for the chosen demo connector without lag
- [ ] Confirm `docker compose up` still works clean from a fresh clone
- [ ] Tag the UI as demo-frozen: `git tag ui-demo-freeze`

### Akhil — 2 hrs, branch `feat/akhil-slides-day1`

- [ ] Create the slide deck (Google Slides recommended for collaboration)
- [ ] Build slides 1–3 from `docs/deck_outline.md`: Problem, Insight, What it is
- [ ] Embed the polished architecture diagram in slide 4 placeholder
- [ ] Apply consistent visual style — pick one color palette, one font, stick to both
- [ ] Speaker notes on every slide, drawn from the locked framing sentences

### Joint — 30 min

- [ ] Review slides 1–3 together
- [ ] Confirm slide 4 architecture diagram is embedded and legible
- [ ] Cross-check slide content against the demo script's numbers

---

## Day 3 — Slide building continues + demo asset creation

### Abhishek — 2 hrs, branch `feat/abhishek-demo-assets`

- [ ] Generate FPR chart (bar chart: overall + per-tier + per-vendor) — SVG or PNG, committed to `docs/assets/`
- [ ] Generate category-coverage chart (6 detected of 19 observed, with volume) — same format
- [ ] Generate a temp-asymmetry drift plot for the demo connector — this is the money-shot visual for the "degradation tracking" claim
- [ ] Commit all assets under `docs/assets/` with descriptive filenames

### Akhil — 2 hrs, branch `feat/akhil-slides-day2`

- [ ] Build slides 4–6: Architecture, Alert-fatigue solution, Proof
- [ ] Embed FPR chart, category-coverage chart, temp-asymmetry plot as they land from Abhishek
- [ ] Speaker notes reference every defensible number (39 stations, 23k sessions, 2.77M events, 6/19 categories, FPR value, vendor coverage %)

### Joint — 30 min

- [ ] Review slides 4–6 together
- [ ] Cross-check every number on every slide against `docs/data_audit_final.md` — one source of truth
- [ ] Read speaker notes aloud, time yourselves — should sit around 30–45 seconds per slide

---

## Day 4 — Slide finalization + first video take

### Abhishek — 2 hrs, branch `feat/abhishek-video-take1`

- [ ] Full demo recording, take 1 — screen + narration, following `docs/demo_script.md` v2
- [ ] Watch back solo, note every fumble, mistiming, or UI hiccup
- [ ] Record take 2 if take 1 has fixable issues
- [ ] Save raw takes to shared drive (NOT the repo — video files too large)

### Akhil — 2 hrs, branch `feat/akhil-slides-final`

- [ ] Build slides 7–9: Demo (embed hook moment as GIF or short clip), Deployment, Future work
- [ ] Final pass on all 9 slides for visual consistency
- [ ] Print-preview / export-to-PDF check — ensure slides render correctly outside Google Slides
- [ ] Speaker notes final polish

### Joint — 30 min

- [ ] Watch Abhishek's take 1 (or 2) together
- [ ] Give one round of feedback each — narration pace, on-screen clarity, hook moment landing
- [ ] Decide: record take 3 tomorrow, or lock take 2

---

## Day 5 — Detailed document + final video

### Abhishek — 2 hrs, branch `feat/abhishek-video-final`

- [ ] If take 2 wasn't locked yesterday, record take 3 (final)
- [ ] Light edit: trim heads/tails, no fancy production
- [ ] Export final video as MP4, 1080p, under 4 minutes
- [ ] Upload to submission host (YouTube unlisted or wherever the organizer specified)
- [ ] Save master copy to shared drive
- [ ] Add video link to repo README

### Akhil — 2 hrs, branch `feat/akhil-detailed-doc`

- [ ] Write the "detailed document" deliverable at `docs/detailed_document.md`
- [ ] Structure (adapt to organizer format if specified): Problem statement, Approach, Architecture, Data, Methods, Results, Deployment, Future work, Team
- [ ] Content sourced from `SPEC.md`, `data_audit_final.md`, `layer2_scope.md`, `multicategory_audit.md`, `layer2_leadtime.md` — do not re-derive
- [ ] Include: 39-station fleet stats, 2.77M events / 19 categories / 6 detected, FPR number, temp-asymmetry finding, deployment topology
- [ ] Export to whatever format the organizer requires (PDF likely)

### Joint — 30 min

- [ ] Watch final video together
- [ ] Read detailed document together, cross-check numbers vs. slides vs. video
- [ ] Confirm every deliverable version is locked

---

## Day 6 — Repo public, submission, buffer

### Abhishek — 2 hrs, branch `chore/abhishek-repo-public`

- [ ] Final `git status` audit — no `data/raw/` files, no `.env`, no personal paths, no unresolved TODOs referencing sensitive info
- [ ] Verify anonymization: grep repo for any real charger IDs, IPs, phone numbers, RFID hashes → should be zero hits
- [ ] Final README pass — links to video, slides, detailed document, contributors
- [ ] Add MIT LICENSE if not already
- [ ] Switch repo visibility to public
- [ ] Tag `v1.0.0-submission` on `main`
- [ ] Verify a fresh clone from the public URL works end-to-end (`docker compose up` on a clean machine or in a container)

### Akhil — 2 hrs, branch `chore/akhil-submission`

- [ ] Assemble submission package: repo URL, video URL, detailed document
- [ ] Fill out hackathon submission form
- [ ] Attach team member details as required
- [ ] Screenshot the confirmation of successful submission
- [ ] Post-submission: draft a short LinkedIn / team recap for post-hackathon (optional, but useful for the record)

### Joint — 60 min (extended)

- [ ] **Final submission walkthrough together** — one clicks submit, the other watches
- [ ] Verify submission confirmation received
- [ ] Merge all remaining Week 3 branches
- [ ] Close out `v1.0-submission` GitHub milestone
- [ ] Write a brief `docs/postmortem.md` — what worked, what didn't, what would change next time (30 min)

---

## End-of-Week-3 checklist

- [ ] All Week 2 debt cleared
- [ ] UI demo-frozen at `ui-demo-freeze`
- [ ] 9-slide deck built with speaker notes, all numbers cross-checked
- [ ] All demo assets generated and committed (FPR chart, category-coverage chart, temp-asymmetry plot)
- [ ] Final video recorded, edited, uploaded, linked from README
- [ ] Detailed document written and exported
- [ ] Repo public with LICENSE, polished README, working `docker compose up`
- [ ] Submission form completed, confirmation received
- [ ] `v1.0.0-submission` tag pushed
- [ ] Postmortem drafted
- [ ] All branches merged, `main` clean

---

## Risks flagged for Week 3

1. **Slide-building consumes more time than expected.** 9 slides with speaker notes, cross-checked numbers, and visual consistency is a real 4–5 hour job, not 2. Budgeted across Days 2–4 accordingly.
2. **Video recording almost never works in one take.** Days 4 and 5 have take-2 and take-3 slots built in. Don't leave recording to Day 6.
3. **Repo-public gotchas:** anonymization audit MUST happen before flipping visibility. A single real charger ID in a notebook cell output is a data leak. Do the grep audit.
4. **Submission form time.** Some hackathon forms take an hour to fill out (team bios, project category, judging preferences). Don't discover this Day 6.
5. **Scope creep temptation.** Week 3 will surface "one more thing" impulses. Route them all to `docs/future_work.md`. The scope freeze from Day 1 is non-negotiable.
6. **The one thing not in the plan:** organizer feedback / Q&A prep if the hackathon has a live pitch round. If yes, add 60 min Day 6 for pitch rehearsal. Confirm on Day 1.

## Nothing deferred past Week 3

Week 3 is the terminal week. Anything not shipped by end of Day 6 is not shipped.