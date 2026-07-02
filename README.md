# EV APM Agent

A watchful operator for EV charging stations that catches faults the instant they happen and spots chargers starting to go bad before they fully fail.

It plugs into the data the charging network already sends to its management system — no new sensors, no hardware changes.

It does two things: a fast rules-based catcher for known fault patterns, and a learning layer that tracks each connector's "normal" over time to flag drift.

It also sorts alerts — separating noisy self-recovering blips from real problems that need a technician — so operators stop drowning in noise.

We'll prove it on real data from 39 stations across 5+ vendors, deployed as a drop-in container next to an existing charging management system.

## What this is (and isn't)

- **What it is:** Real-time fault detection and per-connector degradation tracking across an EV charging fleet.
- **What it isn't:** Not a battery health diagnostic — it analyzes charging-station telemetry to flag faults and connector-level degradation, vendor-agnostic.
- **Where it lives:** Deploys as a sidecar container next to an operator's existing CMS, scaling per fleet size.

## Team

| Name | Role |
|------|------|
| Abhishek | Layer 1 + integration |
| Akhil | Layer 2 + data audit |

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
