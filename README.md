# EV APM Agent

![Decision trace for a real err1051 socket fault that recovered on its own, replayed from the fleet's sequence export](docs/assets/hook_selfrecovery.gif)

EV APM Agent reads the OCPP messages that charging stations already send to their management system and raises an alert when a connector faults or starts behaving differently from its own history. It runs as a container next to the existing system, so it needs no new sensors or hardware. It reads charging-station telemetry only and is not a battery health tool.

It has three parts. Layer 1 uses rules and state machines to catch known fault patterns as events arrive. Layer 2 trains an Isolation Forest for each connector on its normal sessions and flags sessions that drift from that baseline. A prioritizer then ranks every alert P1, P2 or P3 and attaches the signal that decided it, so faults that clear on their own don't compete with ones that need a technician.

I built and tested it on anonymized telemetry from a production fleet of 655 chargers across 130+ manufacturer families, and validated it on a 39-station, 80-connector slice of that fleet.

## Results

- **6 of the 19 OCPP fault categories** detected, each checked against real events from the fleet exports ([`docs/category_metrics.md`](docs/category_metrics.md)).
- **3.62% false-positive rate** for Layer 2 on a chronological holdout of 2,015 normal sessions ([notebook 04](notebooks/04_holdout_evaluation.ipynb)).
- **152 of 190 real err1051 faults (80%)** recovered within 15 seconds and were downgraded to P3 automatically. Across all fault types only about 42% clear on their own (n=2,041), which is why the other categories stay at P1 or P2.
- **659 vendor error codes** in the working taxonomy, all resolved to OCPP categories. The normalizer's own rules decide 152 of them; the rest come from the OCPP error code already present in each record.
- **95 tests** pass on a fresh clone.

Every number above has a reproduction command in [`docs/claims_evidence.md`](docs/claims_evidence.md).

## What it gets wrong

- **The detectors only report what stations report.** Layer 1 fires on fault events in the telemetry, so its 100% detection rate means every logged fault raised an alert. It does not find faults that a station never reported.
- **Chattering sensors flood the alert feed.** One fleet segment produced 79,480 GroundFailure events in 14 months, and each one becomes a P1 alert. Repeated faults need to be collapsed into episodes before alerting ([`docs/future_work.md`](docs/future_work.md)).
- **Layer 2 gives no early warning.** Across 3,484 sessions from one station, sessions right before a fault were flagged less often than other sessions (2.83% vs 4.99%). Layer 2 only sees session duration and start hour, which probably can't capture electrical warning signs ([`docs/layer2_leadtime.md`](docs/layer2_leadtime.md)).
- **13 of 19 fault categories have no detector yet.**

## Project Structure

| Folder | Purpose |
|--------|---------|
| `data/` | Raw and processed datasets (gitignored, never committed), plus committed `sql/` export queries and `reference/` inventory CSVs |
| `detector/` | Detection service: `layer1.py` (rules-based fault detection), `layer2.py` (drift detection) |
| `replay/` | Historical replay and simulation tools |
| `models/` | Trained Layer 2 model artifacts |
| `ui/` | Operator dashboard and alert interface |
| `notebooks/` | Exploration, EDA, and prototyping |
| `docs/` | Architecture, methodology, and runbooks |
| `tests/` | Unit and integration tests |

## Where to find things

| You want | Path |
|-----------|------|
| A plain-language guide (what, why, how) | [`docs/GUIDE_FOR_HUMANS.md`](docs/GUIDE_FOR_HUMANS.md) |
| The full write-up (problem, methods, results, deployment) | [`docs/detailed_document.md`](docs/detailed_document.md) |
| How to run and test it by hand | [`docs/RUNBOOK.md`](docs/RUNBOOK.md) |
| Architecture diagram | [`docs/architecture_v2.svg`](docs/architecture_v2.svg) ([source](docs/architecture_v2.mmd)) |
| Data audit and provenance (numbered flags) | [`docs/data_audit_final.md`](docs/data_audit_final.md) |
| Layer 2 modeling and pooling decisions | [`docs/layer2_scope.md`](docs/layer2_scope.md) |
| Multi-category detection audit | [`docs/multicategory_audit.md`](docs/multicategory_audit.md) |
| Lead-time analysis (negative result) | [`docs/layer2_leadtime.md`](docs/layer2_leadtime.md) |
| Per-category detection metrics | [`docs/category_metrics.md`](docs/category_metrics.md) |
| False-positive and coverage charts | [`docs/assets/`](docs/assets/) |
| Future work | [`docs/future_work.md`](docs/future_work.md) |

## Architecture

![Architecture v2](docs/architecture_v2.svg)

Layer 1 combines state machines for fault sequences (err1051), point-event detectors (err1024, WeakSignal, GroundFailure, Under/OverVoltage) and a telemetry-silence detector, all fed through a vendor-code normalizer. Layer 2 is a per-connector Isolation Forest, with a pooled model for connectors that have too little data, and it scores every closed session. The prioritizer assigns P1, P2 or P3 and attaches the deciding signal before an alert reaches the dashboard.

## Quickstart

```bash
docker compose up            # replay -> detector -> ui on localhost:8000
```

Demo replay of the synthetic fault fixtures at 60x:

```bash
docker compose down -v
MSYS_NO_PATHCONV=1 DATA_DIR=/app/tests/fixtures/day5_replay \
  REPLAY_SPEED_MULTIPLIER=60 docker compose up
# browser -> http://localhost:8000  (P1/P2/P3 feed + drift panel)
```

Local pipeline without Docker:

```bash
REPLAY_SPEED_MULTIPLIER=0 python replay/main.py | python detector/main.py
python -m pytest tests/    # 95 pass on a fresh clone; 3 more need the raw exports, which aren't committed
```

Full step-by-step run and manual-test instructions: [`docs/RUNBOOK.md`](docs/RUNBOOK.md). Alert thresholds are set in `.env.example`.

## Attribution

Built for the **ET AI Hackathon 2026** by a team of three. V. Abhishek Prakash wrote the code, models and data pipeline. Akhil Prasad handled manual testing and submission logistics, Hrishikesh did manual testing, and both edited this README.
