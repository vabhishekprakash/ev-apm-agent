# EV APM Agent Architecture v0

## Summary
The EV APM agent monitors OCPP-based charge point telemetry (transactions, meter values,
status notifications, heartbeats, boot notifications) to detect asset performance issues.
A `replay` service streams historical/simulated CSMS events at a configurable speed
(`REPLAY_SPEED_MULTIPLIER`) so the pipeline can be exercised without a live charge point fleet.
A `detector` service consumes that stream and runs a two-layer detection pipeline against it.
A `ui` service exposes the results as a dashboard. All three run as independent FastAPI
services wired together via `docker-compose.yml`.

## Two-Layer Design
* **Layer 1 (`detector/layer1.py`):** Deterministic, rule-based detectors for known-bad
  conditions — specific OCPP error codes (e.g. err1051, err1024) and telemetry-silence
  (a connector going quiet longer than expected between heartbeats/meter values).
* **Layer 2 (`detector/layer2.py`):** Statistical drift detection — compares each connector's
  behavior against its own recent baseline and against a pooled baseline across similar
  connectors, to catch gradual degradation that Layer 1's fixed rules would miss.

## System Diagram
[Placeholder for diagram]
