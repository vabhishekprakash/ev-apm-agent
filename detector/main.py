"""Detector service v0: consume the replay event stream on stdin, feed Layer 1.

Reads one JSON event per line (the replay harness's output format), parses it
into the typed OCPP messages, and routes it to a per-connector Err1051Detector.
Alerts are printed to stdout as JSON, one per line. HTTP alert sink and the
FastAPI surface land Day 6 (ALERT_SINK env toggle).

Usage:
    python replay/main.py | python detector/main.py
"""

import json
import sys

from ocpp_messages import MeterValues, StartTransaction, StatusNotification, StopTransaction
from layer1 import Err1051Detector


def parse_event(raw: dict):
    """Map a replay JSON line to a typed OCPP message, or None to skip."""
    kind = raw.get("event_type")
    if kind == "StatusNotification":
        return StatusNotification(
            connector_pk=raw["connector_pk"],
            status=raw["status"],
            error_code=raw["error_code"],
            timestamp=raw["ts"],
        )
    if kind == "MeterValues":
        return MeterValues(
            transaction_pk=raw["transaction_pk"],
            connector_pk=raw["connector_pk"],
            meter_reading_wh=raw["meter_reading_wh"],
            timestamp=raw["ts"],
        )
    if kind == "StartTransaction":
        return StartTransaction(
            transaction_pk=raw["transaction_pk"],
            connector_pk=raw["connector_pk"],
            start_timestamp=raw["ts"],
        )
    if kind == "StopTransaction":
        return StopTransaction(
            transaction_pk=raw["transaction_pk"],
            connector_pk=raw["connector_pk"],
            stop_timestamp=raw["ts"],
            stop_reason=raw["stop_reason"],
        )
    return None  # Heartbeat / BootNotification — no Layer 1 consumer yet


def main() -> None:
    detectors: dict[int, Err1051Detector] = {}
    counts = {"events": 0, "routed": 0, "skipped": 0, "parse_errors": 0, "alerts": 0}

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        counts["events"] += 1
        try:
            event = parse_event(json.loads(line))
        except Exception as exc:  # malformed row or unknown enum value
            counts["parse_errors"] += 1
            print(f"warning: unparseable event: {exc}", file=sys.stderr)
            continue
        if event is None:
            counts["skipped"] += 1
            continue

        counts["routed"] += 1
        detector = detectors.setdefault(
            event.connector_pk, Err1051Detector(event.connector_pk)
        )
        alert = detector.consume(event)
        if alert is not None:
            counts["alerts"] += 1
            print(json.dumps(alert.to_dict()), flush=True)

    print(f"detector summary: {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
