"""Replay harness v0: read anonymized CMS CSV exports, emit a single
time-ordered JSON event stream to stdout at a configurable cadence.

Each transaction row fans out into a StartTransaction and a StopTransaction
event so downstream detectors see session opens and closes as they happened.
Inter-event gaps are divided by REPLAY_SPEED_MULTIPLIER (1 = real time,
60 = one minute of history per second, 0 = no sleeping, dump as fast as
possible).

Usage:
    python main.py                              # CSV exports from $DATA_DIR
    python main.py --input <dir>                # CSV exports, explicit folder
    python main.py --format raw-ocpp <file>     # native OCPP-J WebSocket log
    python main.py --format raw-ocpp --follow <file>   # tail a growing log

Both forms emit the identical time-ordered JSON event stream, so the detector
and UI are unaffected by the input format.

Source-resolution contract (fixed after a silent-substitution incident):
- An EXPLICITLY requested folder (--input, or DATA_DIR pointing anywhere
  other than the conventional data/raw) that has no replay sources is a HARD
  ERROR — exit 2, naming the path. Nothing else is substituted.
- Only the conventional default (…/data/raw, which is gitignored and thus
  empty on a fresh public clone) falls back to the bundled demo fixture, and
  that fallback prints an unmissable SYNTHETIC-DATA banner.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data/raw"))
SPEED = float(os.environ.get("REPLAY_SPEED_MULTIPLIER", "1"))
# Fresh-clone fallback candidates: local layout (repo/tests/fixtures) and the
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


def _is_conventional_default(directory: Path) -> bool:
    """True only for the conventional …/data/raw location (any prefix — host
    repo, container /app, or a relative ./data/raw)."""
    parts = [p.lower() for p in directory.parts[-2:]]
    return parts == ["data", "raw"]


def _effective_data_dir(requested: Path) -> Path:
    """Resolve the replay source folder.

    Explicitly requested folder missing => exit 2 (never substitute).
    Conventional default (data/raw) missing => bundled demo fixture, with an
    unmissable synthetic-data banner.
    """
    if _has_sources(requested):
        return requested
    if not _is_conventional_default(requested):
        print(
            f"error: no replay sources under {requested}\n"
            f"  looked for: {', '.join(list(SOURCES) + ['transaction.csv'])}\n"
            f"  Nothing was replayed. Check the path — common causes: running a\n"
            f"  container path (/app/...) on the host, or Git Bash rewriting\n"
            f"  /app/... (prefix the command with MSYS_NO_PATHCONV=1).",
            file=sys.stderr)
        sys.exit(2)
    for candidate in _FALLBACK_CANDIDATES:
        if candidate != requested and _has_sources(candidate):
            print(
                "#" * 70 + "\n"
                f"# SYNTHETIC FIXTURE DATA\n"
                f"# No replay sources under the default {requested} (empty on a\n"
                f"# fresh clone — real exports are gitignored). Replaying the\n"
                f"# bundled demo fixture instead: {candidate}\n"
                f"# Every row downstream is SYNTHETIC. Point --input or DATA_DIR\n"
                f"# at a real export folder to replay real data.\n"
                + "#" * 70,
                file=sys.stderr)
            return candidate
    print(f"error: no replay sources under {requested} and no bundled fixture "
          f"found — nothing to replay.", file=sys.stderr)
    sys.exit(2)


def parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.strip('"'))


def load_events(requested: Path = None) -> list[dict]:
    data_dir = _effective_data_dir(requested if requested is not None else DATA_DIR)
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


def follow_raw_ocpp(file_path: str) -> None:
    """Streaming raw OCPP-J ingestion: tail a growing log file and emit each
    frame's normalized event the moment it lands (arrival cadence). This
    simulates live ingestion by tailing a file — it is NOT a live CMS socket."""
    detector_dir = Path(__file__).resolve().parent.parent / "detector"
    sys.path.insert(0, str(detector_dir))
    from ocpp_log_adapter import stream_events

    print(f"streaming raw OCPP-J ingestion — tailing {file_path} for appended "
          f"frames (file tail, not a live CMS connection); Ctrl-C to stop",
          file=sys.stderr)
    for event in stream_events(file_path, follow=True):
        event = {**event, "ts": event["ts"].isoformat()}
        print(json.dumps(event), flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="replay/main.py",
        description="Replay anonymized CMS exports (or a raw OCPP-J log) as a "
                    "time-ordered JSON event stream on stdout.",
        epilog="Pacing via REPLAY_SPEED_MULTIPLIER env (0 = instant dump, "
               "1 = real time, 60 = 1 min of history per second).")
    parser.add_argument(
        "--input", metavar="DIR",
        help="folder of replay CSVs; overrides the DATA_DIR env var. An "
             "explicit folder with no replay sources is a hard error (exit 2).")
    parser.add_argument(
        "--format", choices=["csv", "raw-ocpp"], default="csv",
        help="csv (default): DATA_DIR/--input folder of exports; raw-ocpp: "
             "a native OCPP-J WebSocket log file (positional argument).")
    parser.add_argument(
        "--follow", action="store_true",
        help="raw-ocpp only: after the backlog, tail the file and stream "
             "appended frames as they land (file tail, not a live CMS socket).")
    parser.add_argument(
        "logfile", nargs="?",
        help="raw OCPP-J log file (required with --format raw-ocpp).")
    args = parser.parse_args()
    if args.format == "raw-ocpp" and not args.logfile:
        parser.error("--format raw-ocpp requires a log file argument")
    if args.format == "csv" and args.logfile:
        parser.error(f"unexpected positional argument {args.logfile!r} — CSV "
                     f"mode takes a folder via --input or the DATA_DIR env var")
    if args.follow and args.format != "raw-ocpp":
        parser.error("--follow is only valid with --format raw-ocpp")
    return args


if __name__ == "__main__":
    args = _parse_args()
    if args.format == "raw-ocpp":
        if args.follow:
            follow_raw_ocpp(args.logfile)
            raise SystemExit(0)
        all_events = load_raw_ocpp_events(args.logfile)
    else:
        requested = Path(args.input) if args.input else DATA_DIR
        all_events = load_events(requested)
    print(f"replaying {len(all_events)} events at {SPEED}x", file=sys.stderr)
    replay(all_events)
