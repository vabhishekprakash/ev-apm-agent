"""Deck chart assets (issues #20, #21) -> docs/assets/.

- fpr_chart.png: per-tier FPR bars + held-out score distribution, recomputed
  with the exact notebook-04 chronological methodology.
- category_coverage.png: the 6 detected categories with verification status
  (real-event vs fixture) and alert volumes from docs/category_metrics.json.
  Regenerate when the fault-event export lands.
"""

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(exist_ok=True)

RANDOM_STATE, THRESHOLD = 42, -0.1187
FEATURES = ["duration_sec", "start_hour"]
INK, BLUE, RED, GREY = "#1a2233", "#2b6cb0", "#c0392b", "#98a3b3"


def chronological_holdout_scores():
    """Notebook-04 methodology, compact: per-connector chronological 80/20."""
    s = pd.read_csv(ROOT / "data/reference/normal_sessions.csv",
                    parse_dates=["start_timestamp", "stop_timestamp"])
    s["duration_sec"] = (s.stop_timestamp - s.start_timestamp).dt.total_seconds()
    s["start_hour"] = s.start_timestamp.dt.hour.astype(float)
    s = s[s.duration_sec > 0].sort_values("start_timestamp").reset_index(drop=True)

    stations = pd.read_csv(ROOT / "data/reference/charger_stations.csv")
    fam = {r.connector_pk: re.sub(r"[^a-z0-9]+", "_", str(r.vendor).lower()).strip("_")
           or "unknown" for r in stations.itertuples()}
    s["family"] = s.connector_pk.map(fam).fillna("unknown")

    test = np.zeros(len(s), dtype=bool)
    for pk, idx in s.groupby("connector_pk").indices.items():
        test[idx[-max(1, int(round(len(idx) * 0.2))):]] = True
    train, held = s[~test], s[test].copy()

    counts = train.groupby("connector_pk").size()
    per_pks = set(counts[counts >= 80].index)
    models = {pk: IsolationForest(contamination="auto", random_state=RANDOM_STATE)
              .fit(train.loc[train.connector_pk == pk, FEATURES].to_numpy())
              for pk in per_pks}
    pool = pd.concat(rows.sample(min(len(rows), 200), random_state=RANDOM_STATE)
                     for _, rows in
                     train[~train.connector_pk.isin(per_pks)].groupby("connector_pk"))
    global_model = IsolationForest(contamination="auto", random_state=RANDOM_STATE)\
        .fit(pool[FEATURES].to_numpy())
    fam_models = {f: IsolationForest(contamination="auto", random_state=RANDOM_STATE)
                  .fit(rows[FEATURES].to_numpy())
                  for f, rows in pool.groupby("family") if len(rows) >= 50}

    held["score"] = np.nan
    for (pk, family), rows in held.groupby(["connector_pk", "family"]):
        model = models.get(pk) or fam_models.get(family) or global_model
        held.loc[rows.index, "score"] = model.decision_function(rows[FEATURES].to_numpy())
    total = s.groupby("connector_pk").size()
    held["tier"] = held.connector_pk.map(
        lambda pk: "heavy" if total[pk] >= 1000 else "medium" if total[pk] >= 250
        else "light" if total[pk] >= 100 else "pooled")
    return held


def fpr_chart(held):
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.2), dpi=150,
                                      gridspec_kw={"width_ratios": [1, 1.5]})
    per_tier = held.groupby("tier").score.apply(lambda v: (v < THRESHOLD).mean())
    order = ["heavy", "medium", "light", "pooled"]
    values = [per_tier.get(t, 0) * 100 for t in order]
    bars = left.bar(order, values, color=[BLUE] * 3 + [GREY])
    left.axhline(5, color=RED, linestyle="--", linewidth=1.2, label="5% acceptance bar")
    overall = (held.score < THRESHOLD).mean()
    left.axhline(overall * 100, color=INK, linestyle=":", linewidth=1.2,
                 label=f"overall {overall:.2%}")
    for bar, value in zip(bars, values):
        left.text(bar.get_x() + bar.get_width() / 2, value + 0.12, f"{value:.1f}%",
                  ha="center", fontsize=9, color=INK)
    left.set_ylabel("false-positive rate (%)")
    left.set_title("FPR by connector tier — chronological holdout", fontsize=10)
    left.legend(fontsize=8)

    right.hist(held.score, bins=60, color=BLUE)
    right.axvline(THRESHOLD, color=RED, linestyle="--",
                  label=f"deployed threshold {THRESHOLD}")
    right.set_xlabel("IsolationForest decision_function (held-out normals)")
    right.set_ylabel("sessions")
    right.set_title(f"Held-out score distribution (n={len(held)}) — "
                    f"flags left of the line", fontsize=10)
    right.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ASSETS / "fpr_chart.png", facecolor="white", bbox_inches="tight")
    print(f"fpr_chart.png — overall {overall:.2%}")


def coverage_chart():
    metrics = json.loads((ROOT / "docs/category_metrics.json").read_text(encoding="utf-8"))
    volumes: dict[str, int] = {}
    for stream in metrics:
        for c in stream["categories"]:
            if c["category"] != "layer2_drift":
                volumes[c["category"]] = volumes.get(c["category"], 0) + c["alerts"]
    status = {  # verification provenance (audit flags 18, 22)
        "UnderVoltage": "real events (18/18)", "telemetry-silence": "real + unit tests",
        "err1051": "fixture + real recovery stats", "err1024": "fixture + crash signature",
        "WeakSignal": "real events (150/150)", "GroundFailure": "real events (79,480/79,480)",
        "OverVoltage": "real events (51/51)",
    }
    cats = sorted(volumes, key=volumes.get)
    colors = [BLUE if "real" in status.get(c, "") else GREY for c in cats]
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    bars = ax.barh(cats, [volumes[c] for c in cats], color=colors)
    for bar, cat in zip(bars, cats):
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                status.get(cat, ""), va="center", fontsize=8, color=INK)
    ax.set_xlabel("alerts across measured replay streams")
    ax.set_title("Detected fault categories — 6 of 19 OCPP buckets "
                 "(blue = real-event verified)", fontsize=10)
    ax.set_xlim(0, max(volumes.values()) * 1.7)
    fig.tight_layout()
    fig.savefig(ASSETS / "category_coverage.png", facecolor="white",
                bbox_inches="tight")
    print(f"category_coverage.png — {len(cats)} categories")


if __name__ == "__main__":
    fpr_chart(chronological_holdout_scores())
    coverage_chart()
