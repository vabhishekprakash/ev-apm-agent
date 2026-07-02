"""Detector service: consume the replay event stream on stdin, feed Layer 1.

Reads one JSON event per line (the replay harness's output format), parses it
into the typed OCPP messages, and routes it to the per-connector Layer 1
detectors — Err1051, Err1024, and TelemetrySilence run in parallel (SPEC
Day 5 Task 3); alerts carry detector_source to distinguish them. Every stream
event's timestamp (including Heartbeats and other connectors' traffic)
advances the event clock that drives silence detection. Alerts are printed to
stdout as JSON, one per line. HTTP alert sink and the FastAPI surface land
Day 6 (ALERT_SINK env toggle).

Usage:
    python replay/main.py | python detector/main.py
"""

import json
import os
import sys
from datetime import datetime

from ocpp_messages import MeterValues, StartTransaction, StatusNotification, StopTransaction
from layer1 import (
    DEFAULT_SILENCE_THRESHOLD_SECONDS,
    Err1024Detector,
    Err1051Detector,
    TelemetrySilenceDetector,
)

SILENCE_THRESHOLD_SECONDS = float(
    os.environ.get("SILENCE_THRESHOLD_SECONDS", DEFAULT_SILENCE_THRESHOLD_SECONDS)
)


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


def make_detectors(connector_pk: int) -> list:
    """All three Layer 1 sub-detectors, run in parallel per connector."""
    return [
        Err1051Detector(connector_pk),
        Err1024Detector(connector_pk),
        TelemetrySilenceDetector(connector_pk, SILENCE_THRESHOLD_SECONDS),
    ]


def emit(alert, counts: dict) -> None:
    counts["alerts"] += 1
    print(json.dumps(alert.to_dict()), flush=True)


def main() -> None:
    detectors: dict[int, list] = {}
    counts = {"events": 0, "routed": 0, "skipped": 0, "parse_errors": 0, "alerts": 0}

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        counts["events"] += 1
        try:
            raw = json.loads(line)
            event = parse_event(raw)
            clock = datetime.fromisoformat(raw["ts"]) if "ts" in raw else None
        except Exception as exc:  # malformed row or unknown enum value
            counts["parse_errors"] += 1
            print(f"warning: unparseable event: {exc}", file=sys.stderr)
            continue

        if event is None:
            counts["skipped"] += 1
        else:
            counts["routed"] += 1
            for detector in detectors.setdefault(
                event.connector_pk, make_detectors(event.connector_pk)
            ):
                alert = detector.consume(event)
                if alert is not None:
                    emit(alert, counts)

        # Silence is the absence of events on a connector, so every event in
        # the stream — Heartbeats included — advances the shared event clock
        # and sweeps all connectors' silence detectors.
        if clock is not None:
            for connector_detectors in detectors.values():
                for detector in connector_detectors:
                    if isinstance(detector, TelemetrySilenceDetector):
                        alert = detector.on_tick(clock)
                        if alert is not None:
                            emit(alert, counts)

    print(f"detector summary: {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
