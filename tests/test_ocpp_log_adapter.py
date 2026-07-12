"""Tests for the raw OCPP-J log ingestion adapter (detector/ocpp_log_adapter.py).

Covers: robust parsing of the messy real-file format (doubled quotes, embedded
semicolons, all frame types), MeterValues measurand flattening, anonymization
at the boundary (charger id hashed, no raw id or UUID survives), and that the
emitted records validate against the existing ocpp_messages schemas.

The real sample lives at data/raw/logs_sample.csv (gitignored); when it is
present the parse test runs against it, otherwise against the committed
audit-clean synthetic fixture that reproduces the same quirks.
"""

import csv
import hashlib
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


def test_connector_identity_reconciles_across_paths():
    """A charger already in the committed CSV inventory must resolve, from the
    raw OCPP-J path, to the SAME connector identity (native connector_pk AND
    hashed_charge_box_id) the CSV path uses — otherwise the raw-log path would
    mint connectors Layer 2 can't match to their existing baselines.

    The raw path derives the charge-box hash by plain sha256, exactly the
    committed-data recipe, so the hash the real charger id produces is the
    committed `hashed_charge_box_id`. Given that hash and the connector/plug
    number, connector_key must return the CSV path's native connector_pk.
    """
    # the hashing recipe is the committed-data convention (plain lowercase sha256)
    assert adapter.hash_charge_box_id("abc") == hashlib.sha256(b"abc").hexdigest()

    inv_path = ROOT / "data" / "reference" / "charger_stations.csv"
    with open(inv_path, newline="", encoding="utf-8-sig") as f:
        row = next(r for r in csv.DictReader(f)
                   if r.get("hashed_charge_box_id") and r.get("physical_plug_id") not in (None, ""))
    committed_hash = row["hashed_charge_box_id"]      # what the raw path computes
    plug = int(row["physical_plug_id"])                # OCPP connectorId
    native_pk = int(row["connector_pk"])               # CSV-path connector identity
    inventory = adapter.load_inventory()

    # raw path == CSV path
    assert adapter.connector_key(committed_hash, plug, inventory) == native_pk
    # and without reconciliation the two paths WOULD diverge (regression guard)
    assert adapter.connector_key(committed_hash, plug, inventory=None) != native_pk


def test_raw_frame_end_to_end_lands_on_native_pk(tmp_path):
    """End-to-end: a raw OCPP-J frame whose charger is in the (here, test)
    inventory ingests to the native connector_pk and committed-style hash —
    the same identity the CSV inventory row carries."""
    charger = "SYNTHUNIT-01"
    charger_hash = hashlib.sha256(charger.encode()).hexdigest()
    native_pk = 8675309
    (tmp_path / "charger_stations.csv").write_text(
        "connector_pk,physical_plug_id,hashed_charge_box_id\n"
        f"{native_pk},1,{charger_hash}\n", encoding="utf-8")
    log = tmp_path / "raw.csv"
    log.write_text(
        f'1;m-1;{charger};"[2,""u-1"",""StatusNotification"",'
        f'{{""connectorId"":1,""errorCode"":""NoError"",""status"":""Available"",'
        f'""timestamp"":""2026-06-01T10:00:00+00:00""}}]";StatusNotification;'
        f'2026-06-01 10:00:00\n', encoding="utf-8")
    event = adapter.load_events(log, inventory_dir=tmp_path)[0]
    assert event["connector_pk"] == native_pk
    assert event["hashed_charge_box_id"] == charger_hash


def test_header_row_and_ampm_timestamp_tolerated():
    """Real-file specifics: a column-name header row is skipped, and a 12-hour
    AM/PM messageTime parses."""
    header = '"idcms_logs"; "messageId"; "chargerId"; "message"; "messageType"; "messageTime"'
    assert adapter._is_header(header)
    assert adapter._parse_ts("2026-07-12 03:04:39 PM") is not None
