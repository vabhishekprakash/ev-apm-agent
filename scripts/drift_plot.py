"""Deck asset: the demo connector's per-session drift trend with fault
annotations (docs/assets/drift_<pk>.png).

Drives the REAL pipeline (data/raw -> detector -> UI) and renders the exact
session-score series and Layer 1 fault events the UI drift panel shows, as a
static matplotlib figure for the deck. Not part of the runtime; regenerate
when the real session history changes.

Usage: py scripts/drift_plot.py [connector_pk]   (default 2009529)
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
PORT = 8099
PK = int(sys.argv[1]) if len(sys.argv) > 1 else 2009529
BLUE, RED, AMBER, GREEN = "#2b6cb0", "#e53e3e", "#dd9b1e", "#2f855a"


def _get(path):
    with urllib.request.urlopen(f"http://localhost:{PORT}{path}") as r:
        return json.load(r)


def collect():
    env = {**os.environ}
    ui = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(PORT),
         "--log-level", "warning"], cwd=ROOT / "ui", env=env)
    try:
        time.sleep(4)
        replay = subprocess.Popen(
            [sys.executable, str(ROOT / "replay" / "main.py")], stdout=subprocess.PIPE,
            env={**env, "DATA_DIR": str(ROOT / "data" / "raw"),
                 "REPLAY_SPEED_MULTIPLIER": "0"}, stderr=subprocess.DEVNULL)
        det = subprocess.Popen(
            [sys.executable, "main.py"], stdin=replay.stdout, cwd=ROOT / "detector",
            env={**env, "ALERT_SINK": "http", "ALERT_URL": f"http://localhost:{PORT}/alerts"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        det.wait(timeout=600)
        time.sleep(2)
        return _get(f"/drift/{PK}"), _get("/alerts?limit=200")
    finally:
        ui.terminate()


def plot(records, alerts):
    n = len(records)
    if not n:
        print(f"no session history for connector {PK}", file=sys.stderr)
        return
    # invert so higher = more unusual (display convention, matches the UI)
    abn = [-(r.get("anomaly_score") or 0) for r in records]
    thr = records[-1].get("layer2_threshold")
    thr_disp = -thr if thr is not None else None
    flagged_x = [i for i, r in enumerate(records) if r.get("flagged")]
    flagged_y = [abn[i] for i in flagged_x]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(range(n), abn, color=BLUE, lw=1.3, label="session anomaly score")
    if thr_disp is not None:
        ax.axhline(thr_disp, color=RED, lw=1, ls="--",
                   label=f"flag threshold (above = flagged)")
    ax.scatter(flagged_x, flagged_y, color=RED, s=26, zorder=5,
               label=f"flagged sessions ({len(flagged_x)})")

    # Layer 1 fault events for this connector, placed at their session position
    first, last = records[0].get("closed_at", ""), records[-1].get("closed_at", "~")
    faults = [a for a in alerts if str(a.get("connector_pk")) == str(PK)
              and a.get("detector_source") != "layer2_drift"
              and a.get("stage") != "candidate" and a.get("fired_at")]
    drawable = [f for f in faults if first <= f["fired_at"] <= last]
    seen_label = False
    for f in drawable:
        idx = min(n - 1, sum(1 for r in records if (r.get("closed_at") or "") <= f["fired_at"]))
        ax.axvline(idx, color=AMBER, lw=0.8, alpha=0.5,
                   label="Layer 1 fault event" if not seen_label else None)
        seen_label = True

    ax.set_title(f"Per-connector drift — connector {PK}: "
                 f"{n} sessions, {len(flagged_x)} flagged, "
                 f"{len(drawable)} fault events in view", fontsize=11)
    ax.set_xlabel("session sequence (oldest → newest)")
    ax.set_ylabel("anomaly score (higher = more unusual)")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.margins(x=0.01)
    fig.tight_layout()
    out = ASSETS / f"drift_{PK}.png"
    fig.savefig(out, facecolor="white", dpi=130, bbox_inches="tight")
    print(f"drift_{PK}.png — {n} sessions, {len(flagged_x)} flagged, "
          f"{len(drawable)}/{len(faults)} faults in view")


if __name__ == "__main__":
    plot(*collect())
