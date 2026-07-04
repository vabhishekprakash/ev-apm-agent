"""Per-category detection metrics (Week 2 Day 5, Abhishek Task 1).

Replays each available event stream through the detector, tallies alerts per
fault category, and writes docs/category_metrics.md + docs/category_metrics.json
(the JSON feeds deck charts; the UI's live coverage panel computes the same
rollup from its own buffer).

Ground truth per stream: fault rows in status_notification.csv (error_code !=
NoError, mapped through the normalizer). Detection rate is alerts/events for
the point-event categories; err1051 emits candidate+final per event and
telemetry-silence has no discrete source event (absence is the signal), so
their rows are annotated instead of rated.

Until the real fault-event export lands, the fixture streams are the only
sources containing category events — rows are labeled with their provenance.
"""

import csv
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "detector"))
from vendor_code_normalizer import normalize  # noqa: E402

STREAMS = [
    ("day5 fixture (err1051/err1024/silence)", "tests/fixtures/day5_replay", "synthetic fixture"),
    ("day4 fixture (WeakSignal/Ground/Voltage)", "tests/fixtures/day4_multicategory", "synthetic fixture"),
    ("capped 90-day export", "data/raw", "real export (fault rows absent — cap)"),
]

CATEGORY_OF_SOURCE = {
    "err1051": "err1051", "err1024": "err1024",
    "telemetry_silence": "telemetry-silence",
}


def replay(data_dir: str) -> list[dict]:
    replay_cmd = [sys.executable, str(ROOT / "replay" / "main.py")]
    detector_cmd = [sys.executable, "main.py"]
    env = {"DATA_DIR": str(ROOT / data_dir), "REPLAY_SPEED_MULTIPLIER": "0",
           "PATH": "", "SYSTEMROOT": ""}
    import os
    env = {**os.environ, "DATA_DIR": str(ROOT / data_dir), "REPLAY_SPEED_MULTIPLIER": "0"}
    r = subprocess.run(replay_cmd, capture_output=True, text=True, env=env, cwd=ROOT)
    d = subprocess.run(detector_cmd, input=r.stdout, capture_output=True,
                       text=True, env=env, cwd=ROOT / "detector")
    return [json.loads(line) for line in d.stdout.splitlines() if line.strip()]


def observed_events(data_dir: Path) -> Counter:
    """Fault rows per canonical category in the stream's status CSV."""
    path = data_dir / "status_notification.csv"
    events: Counter = Counter()
    if not path.exists():
        return events
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            code = (row.get("error_code") or "").strip()
            if code and code != "NoError":
                events[normalize(row.get("vendor_error_code"), code)] += 1
    return events


def main() -> None:
    summary = []
    for label, data_dir, provenance in STREAMS:
        alerts = replay(data_dir)
        events = observed_events(ROOT / data_dir)
        per_category: dict[str, dict] = defaultdict(
            lambda: {"alerts": 0, "tiers": Counter()})
        for alert in alerts:
            category = (alert.get("fault_category")
                        or CATEGORY_OF_SOURCE.get(alert["detector_source"])
                        or alert["detector_source"])
            per_category[category]["alerts"] += 1
            per_category[category]["tiers"][alert.get("priority_tier", "?")] += 1

        categories = []
        for category, data in sorted(per_category.items()):
            observed = events.get(category) or events.get(
                {"err1051": "system-err1051", "err1024": "system-err1024"}
                .get(category, ""), 0)
            point_event = category in ("WeakSignal", "GroundFailure",
                                       "UnderVoltage", "OverVoltage", "err1024")
            categories.append({
                "category": category,
                "events_observed": observed if observed else None,
                "alerts": data["alerts"],
                "detection_rate": (data["alerts"] / observed
                                   if point_event and observed else None),
                "priority_distribution": dict(data["tiers"]),
                "time_to_alert_s": 0 if point_event else None,
                "note": ("fires on the event itself" if point_event else
                         "stateful: candidate at StopTransaction + final at recovery"
                         if category == "err1051" else
                         "absence-of-telemetry signal; fires at threshold by design"
                         if category == "telemetry-silence" else
                         "session-close scoring"),
            })
        summary.append({"stream": label, "provenance": provenance,
                        "total_alerts": len(alerts), "categories": categories})

    (ROOT / "docs" / "category_metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Per-category detection metrics (Week 2 Day 5)\n",
        "Generated by `py scripts/category_metrics.py`. The capped real export",
        "contains no fault rows (audit flag 5/13), so category events exist only",
        "in the synthetic fixtures until the fault-event export lands — rows are",
        "labeled with provenance and the whole table re-generates on real data.\n",
    ]
    for stream in summary:
        lines.append(f"\n## {stream['stream']}  \n*{stream['provenance']}* — "
                     f"{stream['total_alerts']} alerts")
        lines.append("\n| category | events | alerts | detection | tiers | latency | note |")
        lines.append("|---|---|---|---|---|---|---|")
        for c in stream["categories"]:
            rate = f"{c['detection_rate']:.0%}" if c["detection_rate"] is not None else "—"
            events_str = c["events_observed"] if c["events_observed"] is not None else "—"
            latency = f"{c['time_to_alert_s']}s" if c["time_to_alert_s"] is not None else "—"
            tiers = ", ".join(f"{t}:{n}" for t, n in sorted(c["priority_distribution"].items()))
            lines.append(f"| {c['category']} | {events_str} | {c['alerts']} | {rate} "
                         f"| {tiers} | {latency} | {c['note']} |")
    coverage = {c["category"] for s in summary for c in s["categories"]
                if c["category"] != "layer2_drift"}
    lines.append(f"\n**Categories firing across streams: {len(coverage)}** "
                 f"(err1051, err1024, telemetry-silence, WeakSignal, GroundFailure, "
                 f"Under/OverVoltage counted as their OCPP buckets) of the 19 in the "
                 f"OCPP taxonomy.")
    (ROOT / "docs" / "category_metrics.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(f"streams: {len(summary)}; categories firing: {len(coverage)}")
    for s in summary:
        print(f"  {s['stream']}: {s['total_alerts']} alerts, "
              f"{len(s['categories'])} categories")


if __name__ == "__main__":
    main()
