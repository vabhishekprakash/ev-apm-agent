"""Raw OCPP-J log ingestion adapter (front-end stage, new).

Consumes native CMS WebSocket logs — semicolon-delimited rows whose `message`
column carries a raw OCPP-J array — and emits the SAME normalized event
records the CSV replay harness produces, so the detector, prioritizer, model,
and UI run unchanged. This is a presentation/ingestion stage only; it imports
nothing from the detector or prioritizer.

Input row (6 semicolon fields):
    idcms_logs ; messageId ; chargerId ; message ; messageType ; messageTime
The `message` column holds an OCPP-J frame with embedded quotes and, in the
wild, embedded semicolons — naive `split(';')` breaks on it. The parser peels
the three leading id fields, peels the two trailing (messageType, messageTime)
fields from the end, and treats everything between as the frame (handling the
CSV doubled-quote convention). OCPP-J frames:
    CALL       [2, uniqueId, action, payload]
    CALLRESULT [3, uniqueId, payload]
    CALLERROR  [4, uniqueId, errorCode, errorDescription, errorDetails]

Anonymization happens at ingestion, before any record leaves this module: the
chargerId is SHA-256 hashed (64-hex, the same convention as the CSV/SQL export
path), the connector key is a one-way hash of (charger-hash, connectorId), and
the raw correlation UUIDs and any customer card fields are never emitted. No
real charger identifier reaches the pipeline, the UI, or the logs.
"""

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# --- OCPP-J / measurand vocabulary -----------------------------------------

ACTION_STATUS = "StatusNotification"
ACTION_METER = "MeterValues"
ACTION_START = "StartTransaction"
ACTION_STOP = "StopTransaction"
ACTION_HEARTBEAT = "Heartbeat"
MODELED_ACTIONS = {ACTION_STATUS, ACTION_METER, ACTION_START, ACTION_STOP}

ENERGY_MEASURAND = "Energy.Active.Import.Register"
# sampledValue.measurand defaults to the energy register when omitted (OCPP 1.6)
DEFAULT_MEASURAND = ENERGY_MEASURAND

# The trailing two fields (messageType, messageTime) never contain a ';'; the
# frame in the middle may. Peel the tail from the end with non-';' classes so
# any embedded semicolons stay with the frame.
_TAIL = re.compile(r"^(?P<frame>.*);(?P<mtype>[^;]*);(?P<mtime>[^;]*)$", re.DOTALL)
# An OCPP-J frame opens with [2, [3, or [4 (whitespace-tolerant).
_FRAME_HEAD = re.compile(r"\[\s*[234]\s*,")


def hash_charge_box_id(charger_id: str) -> str:
    """SHA-256 hex of a raw charger identifier — the committed-data convention
    (64-char hex). One-way: the raw id cannot be recovered from the hash."""
    return hashlib.sha256(str(charger_id).strip().encode("utf-8")).hexdigest()


def connector_key(charger_hash: str, connector_id) -> int:
    """Stable, anonymized integer key for one physical connector, derived from
    the charger hash and the OCPP connectorId. Opaque by construction — it
    reveals nothing about the raw charger id."""
    digest = hashlib.sha256(f"{charger_hash}:{connector_id}".encode("utf-8"))
    return int(digest.hexdigest()[:12], 16)


def _clean_frame_text(raw: str) -> str:
    """Return the JSON text of the frame: unwrap a CSV-quoted field and undo
    the doubled-quote convention if present."""
    text = raw.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1].replace('""', '"')
    return text


def parse_line(line: str) -> dict | None:
    """Parse one raw log line into
    {charger_id, message_type, message_time, frame} or None when no OCPP-J
    frame is present (blank/garbage line). Robust to embedded semicolons and
    quotes in the frame."""
    line = line.rstrip("\r\n")
    if not line.strip():
        return None
    # three leading id fields, then the rest (frame + two trailing fields)
    head = line.split(";", 3)
    if len(head) < 4:
        return None
    _idcms, _message_id, charger_id, rest = head
    tail = _TAIL.match(rest)
    if not tail:
        return None
    frame_text = _clean_frame_text(tail.group("frame"))
    if not _FRAME_HEAD.match(frame_text.lstrip()):
        return None
    try:
        frame = json.loads(frame_text)
    except json.JSONDecodeError:
        # last-resort: a frame that was quoted without the outer wrapper
        try:
            frame = json.loads(frame_text.replace('""', '"'))
        except json.JSONDecodeError:
            return None
    if not isinstance(frame, list) or not frame:
        return None
    return {
        "charger_id": charger_id.strip().strip('"'),
        "message_type": tail.group("mtype").strip().strip('"'),
        "message_time": tail.group("mtime").strip().strip('"'),
        "frame": frame,
    }


def _parse_ts(raw) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip().strip('"').replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _sample_location(sampled: dict):
    return sampled.get("location")


def flatten_meter_values(payload: dict, ts: datetime | None) -> tuple[float, list]:
    """Flatten an OCPP MeterValues payload into (meter_reading_wh,
    sampled_values). Each sampledValue becomes a Layer-2-shaped row
    {measurand, location, unit, value, timestamp}; the energy register drives
    meter_reading_wh."""
    meter_reading_wh = 0.0
    rows: list[dict] = []
    for entry in payload.get("meterValue", []) or []:
        entry_ts = _parse_ts(entry.get("timestamp")) or ts
        for sampled in entry.get("sampledValue", []) or []:
            measurand = sampled.get("measurand") or DEFAULT_MEASURAND
            raw_value = sampled.get("value")
            row = {
                "measurand": measurand,
                "location": _sample_location(sampled),
                "unit": sampled.get("unit"),
                "value": raw_value,
                "timestamp": entry_ts.isoformat() if entry_ts else None,
            }
            rows.append(row)
            if measurand == ENERGY_MEASURAND:
                try:
                    meter_reading_wh = float(raw_value)
                except (TypeError, ValueError):
                    pass
    return meter_reading_wh, rows


def load_events(path) -> list[dict]:
    """Parse a raw OCPP-J log file into the time-ordered event-record list the
    replay harness emits (same dict shape; `ts` is a datetime). Correlates
    StartTransaction CALL→CALLRESULT for the transaction id and anonymizes
    every identifier at the boundary. Prints frame/skip counts to stderr."""
    counts: Counter = Counter()
    events: list[dict] = []
    # correlation state
    pending_start: dict[str, dict] = {}   # uuid -> start context (pre-result)
    txn_connector: dict[int, int] = {}    # transaction id -> connector key

    with open(path, newline="", encoding="utf-8-sig") as handle:
        for line in handle:
            parsed = parse_line(line)
            if parsed is None:
                if line.strip():
                    counts["unparsed"] += 1
                continue
            counts["frames"] += 1
            frame = parsed["frame"]
            kind = frame[0]
            charger_hash = hash_charge_box_id(parsed["charger_id"])
            msg_ts = _parse_ts(parsed["message_time"])

            if kind == 2:  # CALL
                action = frame[2] if len(frame) > 2 else parsed["message_type"]
                payload = frame[3] if len(frame) > 3 and isinstance(frame[3], dict) else {}
                uuid = frame[1] if len(frame) > 1 else None
                _handle_call(action, payload, uuid, charger_hash, msg_ts,
                             events, pending_start, txn_connector, counts)
            elif kind == 3:  # CALLRESULT — only StartTransaction results matter
                uuid = frame[1] if len(frame) > 1 else None
                result = frame[2] if len(frame) > 2 and isinstance(frame[2], dict) else {}
                _handle_result(uuid, result, events, pending_start,
                               txn_connector, counts)
            else:  # kind == 4, CALLERROR
                counts["skipped_callerror"] += 1

    events.sort(key=lambda event: event["ts"])
    _report(counts, len(events))
    return events


def _handle_call(action, payload, uuid, charger_hash, msg_ts, events,
                 pending_start, txn_connector, counts) -> None:
    if action == ACTION_HEARTBEAT:
        counts["skipped_heartbeat"] += 1
        return
    if action not in MODELED_ACTIONS:
        counts["skipped_other"] += 1
        return

    if action == ACTION_STATUS:
        connector_id = payload.get("connectorId", 0)
        ts = _parse_ts(payload.get("timestamp")) or msg_ts
        if ts is None:
            counts["skipped_no_timestamp"] += 1
            return
        events.append({
            "event_type": ACTION_STATUS,
            "ts": ts,
            "connector_pk": connector_key(charger_hash, connector_id),
            "hashed_charge_box_id": charger_hash,
            "status": payload.get("status"),
            "error_code": payload.get("errorCode") or "NoError",
            "vendor_error_code": payload.get("vendorErrorCode")
            or payload.get("vendorId") or None,
        })
        counts["StatusNotification"] += 1

    elif action == ACTION_METER:
        connector_id = payload.get("connectorId", 0)
        conn_pk = connector_key(charger_hash, connector_id)
        ts = msg_ts
        meter_reading_wh, sampled = flatten_meter_values(payload, ts)
        first_ts = None
        for row in sampled:
            first_ts = _parse_ts(row.get("timestamp"))
            if first_ts:
                break
        ts = first_ts or msg_ts
        if ts is None:
            counts["skipped_no_timestamp"] += 1
            return
        txn = payload.get("transactionId")
        if txn is not None:
            txn_connector[int(txn)] = conn_pk
        events.append({
            "event_type": ACTION_METER,
            "ts": ts,
            "transaction_pk": int(txn) if txn is not None else 0,
            "connector_pk": conn_pk,
            "hashed_charge_box_id": charger_hash,
            "meter_reading_wh": meter_reading_wh,
            "sampled_values": sampled,
        })
        counts["MeterValues"] += 1

    elif action == ACTION_START:
        # transaction id is assigned in the CALLRESULT — stash the context and
        # emit when the result arrives (correlated by uuid).
        connector_id = payload.get("connectorId", 0)
        ts = _parse_ts(payload.get("timestamp")) or msg_ts
        if uuid is None or ts is None:
            counts["skipped_start_uncorrelated"] += 1
            return
        pending_start[uuid] = {
            "connector_pk": connector_key(charger_hash, connector_id),
            "hashed_charge_box_id": charger_hash,
            "ts": ts,
        }

    elif action == ACTION_STOP:
        txn = payload.get("transactionId")
        ts = _parse_ts(payload.get("timestamp")) or msg_ts
        if txn is None or ts is None:
            counts["skipped_stop_uncorrelated"] += 1
            return
        conn_pk = txn_connector.get(int(txn))
        if conn_pk is None:
            counts["skipped_stop_uncorrelated"] += 1
            return
        events.append({
            "event_type": ACTION_STOP,
            "ts": ts,
            "transaction_pk": int(txn),
            "connector_pk": conn_pk,
            "hashed_charge_box_id": charger_hash,
            "stop_reason": payload.get("reason") or "Local",
        })
        counts["StopTransaction"] += 1


def _handle_result(uuid, result, events, pending_start, txn_connector,
                   counts) -> None:
    context = pending_start.pop(uuid, None) if uuid is not None else None
    if context is None:
        counts["skipped_result_ack"] += 1
        return
    txn = result.get("transactionId")
    if txn is None:
        counts["skipped_start_uncorrelated"] += 1
        return
    txn_connector[int(txn)] = context["connector_pk"]
    events.append({
        "event_type": ACTION_START,
        "ts": context["ts"],
        "transaction_pk": int(txn),
        "connector_pk": context["connector_pk"],
        "hashed_charge_box_id": context["hashed_charge_box_id"],
    })
    counts["StartTransaction"] += 1


def _report(counts: Counter, emitted: int) -> None:
    modeled = ", ".join(f"{a} {counts[a]}" for a in
                        (ACTION_STATUS, ACTION_METER, ACTION_START, ACTION_STOP))
    skipped = {k: v for k, v in counts.items() if k.startswith("skipped")}
    print(
        f"ocpp-log adapter: {counts['frames']} frames parsed, "
        f"{emitted} events emitted ({modeled}); "
        f"skipped {dict(skipped)}; unparsed lines {counts['unparsed']}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python ocpp_log_adapter.py <raw-ocpp-log.csv>", file=sys.stderr)
        raise SystemExit(2)
    loaded = load_events(Path(sys.argv[1]))
    # emit the same JSON-lines stream the replay harness prints
    for record in loaded:
        record = {**record, "ts": record["ts"].isoformat()}
        print(json.dumps(record))
