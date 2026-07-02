"""Replay harness v0: read anonymized CMS CSV exports, emit a single
time-ordered JSON event stream to stdout at a configurable cadence.

Each transaction row fans out into a StartTransaction and a StopTransaction
event so downstream detectors see session opens and closes as they happened.
Inter-event gaps are divided by REPLAY_SPEED_MULTIPLIER (1 = real time,
60 = one minute of history per second, 0 = no sleeping, dump as fast as
possible).

Usage:
    python main.py            # reads $DATA_DIR (default ./data/raw)
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

# filename -> (event_type, timestamp column)
SOURCES = {
    "status_notification.csv": ("StatusNotification", "timestamp"),
    "meter_values.csv": ("MeterValues", "timestamp"),
    "heartbeat.csv": ("Heartbeat", "timestamp"),
    "boot_notification.csv": ("BootNotification", "timestamp"),
}


def parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.strip('"'))


def load_events() -> list[dict]:
    events = []
    for filename, (event_type, ts_col) in SOURCES.items():
        path = DATA_DIR / filename
        if not path.exists():
            print(f"warning: {path} missing, skipping", file=sys.stderr)
            continue
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                events.append(
                    {"event_type": event_type, "ts": parse_ts(row[ts_col]), **row}
                )

    # Transactions fan out into start/stop events.
    tx_path = DATA_DIR / "transaction.csv"
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


if __name__ == "__main__":
    all_events = load_events()
    print(f"replaying {len(all_events)} events at {SPEED}x", file=sys.stderr)
    replay(all_events)
