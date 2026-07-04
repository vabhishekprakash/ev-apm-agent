"""Detector service: consume the replay event stream on stdin, feed Layer 1.

Reads one JSON event per line (the replay harness's output format), parses it
into the typed OCPP messages, and routes it to the per-connector Layer 1
detectors — Err1051, Err1024, and TelemetrySilence run in parallel (SPEC
Day 5 Task 3); alerts carry detector_source to distinguish them. Every stream
event's timestamp (including Heartbeats and other connectors' traffic)
advances the event clock that drives silence detection.

Alert sink (SPEC Day 6 Task 1): ALERT_SINK=stdout prints alerts as JSON
lines (default); ALERT_SINK=http POSTs each alert to ALERT_URL (default
http://ui:8000/alerts — the compose service name). Alerts are enriched with
hashed_charge_box_id / physical_plug_id from the reference inventory when
data/reference/charger_stations.csv is readable.

Usage:
    python replay/main.py | python detector/main.py
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from ocpp_messages import MeterValues, StartTransaction, StatusNotification, StopTransaction
from layer1 import (
    DEFAULT_SILENCE_THRESHOLD_SECONDS,
    Err1024Detector,
    Err1051Detector,
    TelemetrySilenceDetector,
)
from layer2 import Layer2Anomaly

SILENCE_THRESHOLD_SECONDS = float(
    os.environ.get("SILENCE_THRESHOLD_SECONDS", DEFAULT_SILENCE_THRESHOLD_SECONDS)
)
ALERT_SINK = os.environ.get("ALERT_SINK", "stdout")
ALERT_URL = os.environ.get("ALERT_URL", "http://ui:8000/alerts")


def load_connector_inventory() -> dict[int, dict]:
    """connector_pk -> station identity, for alert enrichment. Empty if the
    reference export isn't mounted (alerts then carry connector_pk only)."""
    candidates = [
        Path(os.environ["REFERENCE_DIR"]) if "REFERENCE_DIR" in os.environ else None,
        Path("data/reference"),
        Path(__file__).resolve().parent.parent / "data" / "reference",
    ]
    for ref_dir in candidates:
        if ref_dir is None or not (ref_dir / "charger_stations.csv").exists():
            continue
        with (ref_dir / "charger_stations.csv").open(newline="", encoding="utf-8-sig") as f:
            return {
                int(row["connector_pk"]): {
                    "hashed_charge_box_id": row["hashed_charge_box_id"],
                    "physical_plug_id": int(row["physical_plug_id"]),
                }
                for row in csv.DictReader(f)
            }
    print("warning: charger_stations.csv not found, alerts unenriched", file=sys.stderr)
    return {}


CONNECTOR_INVENTORY = load_connector_inventory()


def load_layer2() -> Layer2Anomaly:
    """Layer 2 scorer over the committed artifacts; disabled when absent."""
    candidates = [
        os.environ.get("MODELS_DIR"),
        "models",
        Path(__file__).resolve().parent.parent / "models",
    ]
    for models_dir in candidates:
        if models_dir and (Path(models_dir) / "isoforest_index.pkl").exists():
            return Layer2Anomaly(models_dir)
    return Layer2Anomaly(candidates[1])  # reports itself unavailable


LAYER2 = load_layer2()


def sink_alert(payload: dict) -> None:
    if ALERT_SINK == "http":
        request = urllib.request.Request(
            ALERT_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=5)
            return
        except OSError as exc:
            print(f"warning: alert POST failed ({exc}), falling back to stdout",
                  file=sys.stderr)
    print(json.dumps(payload), flush=True)


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
    payload = alert.to_dict()
    payload.update(CONNECTOR_INVENTORY.get(payload.get("connector_pk"), {}))
    sink_alert(payload)


def score_session_close(event: StopTransaction, session: dict, counts: dict) -> None:
    """Layer 2 on session close (SPEC Day 6 Task 3): score sessions Layer 1
    did not flag; emit a layer2_drift alert when the score crosses the
    threshold."""
    duration = (event.stop_timestamp - session["started_at"]).total_seconds()
    if duration <= 0:
        return
    features = {
        "duration_sec": duration,
        "start_hour": float(session["started_at"].hour),
    }
    try:
        result = LAYER2.score_by_connector_pk(features, event.connector_pk)
    except Exception as exc:  # missing sklearn, corrupt artifact — disable
        LAYER2.available = False
        print(f"warning: Layer 2 scoring disabled: {exc}", file=sys.stderr)
        return
    if result is None:
        return
    raw_score, flagged = result
    counts["sessions_scored"] += 1
    if flagged:
        counts["layer2_flagged"] += 1
        payload = {
            "detector_source": "layer2_drift",
            "connector_pk": event.connector_pk,
            "fired_at": event.stop_timestamp.isoformat(),
            "stage": "final",
            "fault_code": None,
            "mechanism": "session profile deviates from connector baseline",
            "recovery_seconds": None,
            "classification": "drift-anomaly",
            "anomaly_score": round(raw_score, 4),
            "layer2_threshold": LAYER2.threshold,
        }
        payload.update(CONNECTOR_INVENTORY.get(event.connector_pk, {}))
        counts["alerts"] += 1
        sink_alert(payload)


def flag_connector_sessions(open_sessions: dict, connector_pk: int) -> None:
    """A Layer 1 fault on a connector marks its open sessions; Layer 2 only
    scores fault-free sessions (SPEC Day 6 Task 3)."""
    for session in open_sessions.values():
        if session["connector_pk"] == connector_pk:
            session["layer1_flagged"] = True


def main() -> None:
    detectors: dict[int, list] = {}
    open_sessions: dict[int, dict] = {}  # transaction_pk -> session state
    counts = {
        "events": 0, "routed": 0, "skipped": 0, "parse_errors": 0, "alerts": 0,
        "sessions_closed": 0, "sessions_scored": 0, "layer2_flagged": 0,
    }

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
            if isinstance(event, StartTransaction):
                open_sessions[event.transaction_pk] = {
                    "connector_pk": event.connector_pk,
                    "started_at": event.start_timestamp,
                    "layer1_flagged": False,
                }
            for detector in detectors.setdefault(
                event.connector_pk, make_detectors(event.connector_pk)
            ):
                alert = detector.consume(event)
                if alert is not None:
                    emit(alert, counts)
                    flag_connector_sessions(open_sessions, event.connector_pk)
            if isinstance(event, StopTransaction):
                session = open_sessions.pop(event.transaction_pk, None)
                if session is not None:
                    counts["sessions_closed"] += 1
                    if not session["layer1_flagged"]:
                        score_session_close(event, session, counts)

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
                            flag_connector_sessions(
                                open_sessions, alert.connector_pk
                            )

    if counts["sessions_scored"]:
        rate = counts["layer2_flagged"] / counts["sessions_scored"]
        print(
            f"layer2 flag rate: {counts['layer2_flagged']}/{counts['sessions_scored']} "
            f"sessions = {rate:.3%} (threshold {LAYER2.threshold})",
            file=sys.stderr,
        )
    print(f"detector summary: {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
