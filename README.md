# EV APM Agent

![Live demo — the decision trace behind a real self-recovered err1051 socket fault, from the real fleet sequence export](docs/assets/hook_selfrecovery.gif)

A watchful operator for EV charging stations that catches faults the instant they happen and spots chargers starting to go bad before they fully fail.

It plugs into the data the charging network already sends to its management system — no new sensors, no hardware changes.

It does two things: a fast rules-based catcher for known fault patterns, and a learning layer that tracks each connector's "normal" over time to flag drift.

It also sorts alerts — separating noisy self-recovering blips from real problems that need a technician — so operators stop drowning in noise.

We'll prove it on real data from a production CMS — **655 chargers across 130+ manufacturer families** at source, validated on a delivered **39-station / 80-connector** slice — deployed as a drop-in container next to an existing charging management system.

## What this is (and isn't)

- **What it is:** Real-time fault detection and per-connector degradation tracking across an EV charging fleet.
- **What it isn't:** Not a battery health diagnostic — it analyzes charging-station telemetry to flag faults and connector-level degradation, vendor-agnostic.
- **Where it lives:** Deploys as a sidecar container next to an operator's existing CMS, scaling per fleet size.

## Team

| Name | Role |
|------|------|
| Abhishek | Layer 1 + integration + UI |
| Akhil | Layer 2 + data + evaluation |
| Hrishikesh | Testing + documentation |

## Project Structure

| Folder | Purpose |
|--------|---------|
| `data/` | Raw and processed datasets (gitignored — never committed); committed `sql/` export queries and `reference/` inventory CSVs |
| `detector/` | Detection service — `layer1.py` (rules-based fault catcher), `layer2.py` (drift detection and learning layer) |
| `replay/` | Historical replay and simulation tools |
| `models/` | Trained Layer 2 model artifacts |
| `ui/` | Operator dashboard and alert interface |
| `notebooks/` | Exploration, EDA, and prototyping |
| `docs/` | Architecture, methodology, and runbooks |
| `tests/` | Unit and integration tests |

## Where to find things

| You want… | Path |
|-----------|------|
| **New here? Plain-language guide** (what/why/how, no jargon) | [`docs/GUIDE_FOR_HUMANS.md`](docs/GUIDE_FOR_HUMANS.md) |
| **The full write-up** (problem, methods, results, deployment) | [`docs/detailed_document.md`](docs/detailed_document.md) |
| **How to run and manually test it** (step-by-step) | [`docs/RUNBOOK.md`](docs/RUNBOOK.md) |
| Architecture diagram | [`docs/architecture_v2.svg`](docs/architecture_v2.svg) ([source](docs/architecture_v2.mmd)) |
| Data audit & provenance (numbered flags) | [`docs/data_audit_final.md`](docs/data_audit_final.md) |
| Layer 2 modeling & tier/pooling decisions | [`docs/layer2_scope.md`](docs/layer2_scope.md) |
| Multi-category detection audit | [`docs/multicategory_audit.md`](docs/multicategory_audit.md) |
| Lead-time analysis (honest negative result) | [`docs/layer2_leadtime.md`](docs/layer2_leadtime.md) |
| Per-category detection metrics | [`docs/category_metrics.md`](docs/category_metrics.md) |
| FPR & coverage charts | [`docs/assets/`](docs/assets/) |
| Future work (scope-freeze ledger) | [`docs/future_work.md`](docs/future_work.md) |

## Architecture

![Architecture v2](docs/architecture_v2.svg)

Two-layer detection: **Layer 1** — deterministic fault-sequence state
machines (err1051), point-event category detectors (err1024, WeakSignal,
GroundFailure, Under/OverVoltage) and a telemetry-silence detector, fed
through a vendor-code normalizer; **Layer 2** — per-connector Isolation
Forests (pooled fallback for sparse connectors) scoring every closed
session. An alert prioritizer tiers everything (P1/P2/P3) with the deciding
signal attached before it reaches the dashboard.

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
python -m pytest tests/    # 98 tests (95 on a fresh clone)
```

Full step-by-step run + manual-test instructions: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

Headline metric: **3.62% false-positive rate** on a chronological held-out
split (notebook 04); alert thresholds documented in `.env.example`.

## Attribution

Built for the **ET AI Hackathon 2026** by V. Abhishek Prakash (Layer 1 +
integration), Akhil Prasad (Layer 2 + data audit), and Hrishikesh
(testing + documentation).

Data provenance: anonymized OCPP telemetry exports from a production
charging-management system (charge-box ids SHA-256-hashed, geo coordinates
rounded, customer/RFID/IP fields dropped at export). Raw exports are never
committed — see `.gitignore` and [`docs/data_audit_final.md`](docs/data_audit_final.md)
for the audit trail. MIT licensed.
