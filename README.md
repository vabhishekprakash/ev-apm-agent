# EV APM Agent

A watchful operator for EV charging stations that catches faults the instant they happen and spots chargers starting to go bad before they fully fail.

It plugs into the data the charging network already sends to its management system — no new sensors, no hardware changes.

It does two things: a fast rules-based catcher for known fault patterns, and a learning layer that tracks each connector's "normal" over time to flag drift.

It also sorts alerts — separating noisy self-recovering blips from real problems that need a technician — so operators stop drowning in noise.

We'll prove it on real data from 39 stations across 5+ vendors, deployed as a drop-in container next to an existing charging management system.

## Team

| Name | Role |
|------|------|
| Abhishek | Layer 1 + integration |
| Akhil | Layer 2 + data audit |

## Project Structure

| Folder | Purpose |
|--------|---------|
| `data/` | Raw and processed datasets (gitignored — never committed) |
| `layer1/` | Rules-based fault catcher |
| `layer2/` | Drift detection and learning layer |
| `replay/` | Historical replay and simulation tools |
| `ui/` | Operator dashboard and alert interface |
| `notebooks/` | Exploration, EDA, and prototyping |
| `docs/` | Architecture, methodology, and runbooks |
| `tests/` | Unit and integration tests |
