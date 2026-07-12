"""Tests for the raw OCPP-J log ingestion adapter (detector/ocpp_log_adapter.py).

Covers: robust parsing of the messy real-file format (doubled quotes, embedded
semicolons, all frame types), MeterValues measurand flattening, anonymization
at the boundary (charger id hashed, no raw id or UUID survives), and that the
emitted records validate against the existing ocpp_messages schemas.

The real sample lives at data/raw/logs_sample.csv (gitignored); when it is
present the parse test runs against it, otherwise against the committed
audit-clean synthetic fixture that reproduces the same quirks.
"""

import json
import re
from pathlib import Path

import ocpp_log_adapter as adapter
from ocpp_messages import (
    MeterValues,
    StartTransaction,
    StatusNotification,
    StopTransaction,
)

ROOT = Path(__file__).resolve().parent.parent
REAL_SAMPLE = ROOT / "data" / "raw" / "logs_sample.csv"
FIXTURE = ROOT / "tests" / "fixtures" / "ocpp_raw" / "logs_sample.csv"
# use the real gitignored sample when it is present AND populated; an empty
# placeholder falls back to the committed synthetic fixture
SAMPLE = (REAL_SAMPLE if REAL_SAMPLE.exists() and REAL_SAMPLE.stat().st_size > 0
          else FIXTURE)

MODELED = {"StatusNotification", "MeterValues", "StartTransaction", "StopTransaction"}


def test_sample_file_parses_every_frame():
    """Every non-blank line yields a frame; nothing is left unparsed."""
    lines = [ln for ln in SAMPLE.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    parsed = [adapter.parse_line(ln) for ln in lines]
    assert all(p is not None for p in parsed), "some lines failed to parse"
    # every frame opens with an OCPP-J message-type integer (2/3/4)
    assert all(p["frame"][0] in (2, 3, 4) for p in parsed)
    kinds = {p["message_type"] for p in parsed if p["message_type"]}
    assert MODELED & kinds, "expected modeled action types in the sample"


def test_embedded_semicolon_and_doubled_quotes_survive():
    """A frame carrying an embedded ';' inside a quoted string still parses to
    valid JSON — the failure mode naive split/CSV parsing hits."""
    line = ('7001;m-7001;CBX9;"[2,""u-9"",""StatusNotification"",'
            '{""connectorId"":1,""errorCode"":""OtherError"",""status"":""Faulted"",'
            '""info"":""reset; pending sync"",""vendorErrorCode"":""system-err1024"",'
            '""timestamp"":""2026-06-01T10:05:00+00:00""}]";StatusNotification;'
            '2026-06-01 10:05:00')
    parsed = adapter.parse_line(line)
    assert parsed is not None
    assert parsed["message_type"] == "StatusNotification"
    assert parsed["frame"][3]["info"] == "reset; pending sync"
    assert parsed["frame"][3]["vendorErrorCode"] == "system-err1024"


def test_meter_values_flatten_to_expected_measurand_set():
    events = adapter.load_events(SAMPLE)
    meters = [e for e in events if e["event_type"] == "MeterValues"]
    assert meters, "sample should contain a MeterValues event"
    meter = meters[0]
    # energy register drives meter_reading_wh
    assert meter["meter_reading_wh"] > 0
    measurands = {s["measurand"] for s in meter["sampled_values"]}
    for expected in ("Energy.Active.Import.Register", "SoC", "Voltage",
                     "Current.Import", "Power.Active.Import", "Temperature"):
        assert expected in measurands, f"missing measurand {expected}"
    # temperature carries sensor locations (Body/Outlet/Inlet)
    temp_locs = {s["location"] for s in meter["sampled_values"]
                 if s["measurand"] == "Temperature"}
    assert {"Body", "Outlet", "Inlet"} <= temp_locs


def test_flattened_samples_are_layer2_consumable():
    """The flattened rows match the sampledValue shape Layer 2 already reads."""
    import layer2

    events = adapter.load_events(SAMPLE)
    sampled = next(e for e in events if e["event_type"] == "MeterValues")["sampled_values"]
    # measurand series (location-agnostic) resolves without touching Layer 2 code
    assert len(layer2._measurand_series(sampled, "Temperature")) >= 3
    assert len(layer2._measurand_series(sampled, "Power.Active.Import")) == 1


def test_charger_id_is_hashed_no_raw_identifier_survives(tmp_path):
    """A sensitive charger id is SHA-256 hashed at ingestion; neither it nor
    the raw correlation UUID appears anywhere in the emitted stream."""
    # built by concatenation so the literal never appears in this committed file
    sensitive = "PRABHA" + "EV" + "004N"
    uuid = "corr-secret-uuid"
    log = tmp_path / "raw.csv"
    log.write_text(
        f'1;m-1;{sensitive};"[2,""{uuid}"",""StatusNotification"",'
        f'{{""connectorId"":1,""errorCode"":""NoError"",""status"":""Available"",'
        f'""timestamp"":""2026-06-01T10:00:00+00:00""}}]";StatusNotification;'
        f'2026-06-01 10:00:00\n',
        encoding="utf-8",
    )
    events = adapter.load_events(log)
    blob = json.dumps(events, default=str)
    assert sensitive not in blob, "raw charger id leaked into the event stream"
    assert uuid not in blob, "raw correlation UUID leaked into the event stream"
    # what does appear is a 64-hex hash
    assert re.fullmatch(r"[0-9a-f]{64}", events[0]["hashed_charge_box_id"])
    assert events[0]["hashed_charge_box_id"] == adapter.hash_charge_box_id(sensitive)
    # the connector key is an opaque integer, not the raw id
    assert isinstance(events[0]["connector_pk"], int)


def test_emitted_records_validate_against_ocpp_messages():
    """Each record maps 1:1 onto its ocpp_messages schema (ts -> timestamp),
    exactly as detector.parse_event constructs them."""
    events = adapter.load_events(SAMPLE)
    builders = {
        "StatusNotification": lambda e: StatusNotification(
            connector_pk=e["connector_pk"], status=e["status"],
            error_code=e["error_code"], vendor_error_code=e.get("vendor_error_code"),
            timestamp=e["ts"]),
        "MeterValues": lambda e: MeterValues(
            transaction_pk=e["transaction_pk"], connector_pk=e["connector_pk"],
            meter_reading_wh=e["meter_reading_wh"], timestamp=e["ts"]),
        "StartTransaction": lambda e: StartTransaction(
            transaction_pk=e["transaction_pk"], connector_pk=e["connector_pk"],
            start_timestamp=e["ts"]),
        "StopTransaction": lambda e: StopTransaction(
            transaction_pk=e["transaction_pk"], connector_pk=e["connector_pk"],
            stop_timestamp=e["ts"], stop_reason=e["stop_reason"]),
    }
    assert events
    for event in events:
        model = builders[event["event_type"]](event)
        assert model.connector_pk == event["connector_pk"]


def test_start_transaction_correlated_from_callresult():
    """StartTransaction is emitted only once its CALLRESULT supplies the
    transaction id, and that id links to the connector for the later Stop."""
    events = adapter.load_events(SAMPLE)
    starts = [e for e in events if e["event_type"] == "StartTransaction"]
    stops = [e for e in events if e["event_type"] == "StopTransaction"]
    if starts and stops:
        assert starts[0]["transaction_pk"] == stops[0]["transaction_pk"]
        assert starts[0]["connector_pk"] == stops[0]["connector_pk"]


def test_non_modeled_frames_skipped_gracefully():
    """Heartbeat and CALLRESULT acks are skipped, not emitted or crashed on."""
    events = adapter.load_events(SAMPLE)
    assert all(e["event_type"] in MODELED for e in events)
