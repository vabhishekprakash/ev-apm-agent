"""Replay harness v0: read anonymized CMS CSV exports, emit a single
time-ordered JSON event stream to stdout at a configurable cadence.

Each transaction row fans out into a StartTransaction and a StopTransaction
event so downstream detectors see session opens and closes as they happened.
Inter-event gaps are divided by REPLAY_SPEED_MULTIPLIER (1 = real time,
60 = one minute of history per second, 0 = no sleeping, dump as fast as
possible).

Usage:
    python main.py                              # CSV exports from $DATA_DIR
    python main.py --format raw-ocpp <file>     # native OCPP-J WebSocket log

Both forms emit the identical time-ordered JSON event stream, so the detector
and UI are unaffected by the input format.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data/raw"))
SPEED = float(os.environ.get("REPLAY_SPEED_MULTIPLIER", "1"))
# When DATA_DIR has no replay sources (e.g. a fresh public clone where the real
# exports under data/raw are gitignored), fall back to the bundled demo fixture
# so `docker compose up` shows a populated dashboard with no second terminal.
# Candidate locations cover both the local layout (repo/tests/fixtures) and the
# container layout (replay code at /app, fixtures mounted at /app/tests/fixtures).
_FALLBACK_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "demo_replay",
    Path("/app/tests/fixtures/demo_replay"),
    Path("tests/fixtures/demo_replay"),
]

# filename -> (event_type, timestamp column)
SOURCES = {
    "status_notification.csv": ("StatusNotification", "timestamp"),
    "meter_values.csv": ("MeterValues", "timestamp"),
    "heartbeat.csv": ("Heartbeat", "timestamp"),
    "boot_notification.csv": ("BootNotification", "timestamp"),
}


def _has_sources(directory: Path) -> bool:
    known = list(SOURCES) + ["transaction.csv"]
    return any((directory / name).exists() for name in known)


def _effective_data_dir() -> Path:
    """DATA_DIR if it holds any replay source, else the bundled demo fixture."""
    if _has_sources(DATA_DIR):
        return DATA_DIR
    for candidate in _FALLBACK_CANDIDATES:
        if candidate != DATA_DIR and _has_sources(candidate):
            print(f"note: no replay sources under {DATA_DIR}; using bundled demo "
                  f"fixture {candidate} (set DATA_DIR to override)", file=sys.stderr)
            return candidate
    return DATA_DIR


def parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.strip('"'))


def load_events() -> list[dict]:
    data_dir = _effective_data_dir()
    events = []
    for filename, (event_type, ts_col) in SOURCES.items():
        path = data_dir / filename
        if not path.exists():
            print(f"warning: {path} missing, skipping", file=sys.stderr)
            continue
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                events.append(
                    {"event_type": event_type, "ts": parse_ts(row[ts_col]), **row}
                )

    # Transactions fan out into start/stop events.
    tx_path = data_dir / "transaction.csv"
    if tx_path.exists():
        with tx_path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                base = {
                    "transaction_pk": row["transaction_pk"],
                    "connector_pk": row["connector_pk"],
                }
                events.append(
                    {
                        "event_type": "StartTransaction",
                        "ts": parse_ts(row["start_timestamp"]),
                        **base,
                    }
                )
                if row["stop_timestamp"]:
                    events.append(
                        {
                            "event_type": "StopTransaction",
                            "ts": parse_ts(row["stop_timestamp"]),
                            "stop_reason": row["stop_reason"],
                            **base,
                        }
                    )
    else:
        print(f"warning: {tx_path} missing, skipping", file=sys.stderr)

    events.sort(key=lambda e: e["ts"])
    return events


def replay(events: list[dict]) -> None:
    prev_ts = None
    for event in events:
        if SPEED > 0 and prev_ts is not None:
            gap = (event["ts"] - prev_ts).total_seconds() / SPEED
            if gap > 0:
                time.sleep(gap)
        prev_ts = event["ts"]
        event["ts"] = event["ts"].isoformat()
        print(json.dumps(event), flush=True)


def load_raw_ocpp_events(file_path: str) -> list[dict]:
    """Delegate to the OCPP-J log adapter (in detector/, stdlib-only). Kept
    behind the --format flag so the default CSV path has no extra imports."""
    detector_dir = Path(__file__).resolve().parent.parent / "detector"
    sys.path.insert(0, str(detector_dir))
    from ocpp_log_adapter import load_events as load_ocpp_events

    return load_ocpp_events(file_path)


if __name__ == "__main__":
    if "--format" in sys.argv:
        i = sys.argv.index("--format")
        fmt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        if fmt != "raw-ocpp":
            print(f"unknown --format {fmt!r}; expected 'raw-ocpp'", file=sys.stderr)
            raise SystemExit(2)
        if i + 2 >= len(sys.argv):
            print("usage: python main.py --format raw-ocpp <file>", file=sys.stderr)
            raise SystemExit(2)
        all_events = load_raw_ocpp_events(sys.argv[i + 2])
    else:
        all_events = load_events()
    print(f"replaying {len(all_events)} events at {SPEED}x", file=sys.stderr)
    replay(all_events)
