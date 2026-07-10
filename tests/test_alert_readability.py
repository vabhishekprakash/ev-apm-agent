"""Hard gate U2: user-facing text is plain English — no raw variable names."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAKE = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")

# Narrative fields a judge reads. (Machine fields like detector_source and
# fault_code are identifiers by design and are rendered prettified by the UI.)
NARRATIVE_FIELDS = ("deciding_signal", "recommended_action",
                    "likely_root_cause", "impact_class", "classification")


def sample_alerts() -> list[dict]:
    env = {**os.environ, "DATA_DIR": str(ROOT / "tests/fixtures/demo_replay"),
           "REPLAY_SPEED_MULTIPLIER": "0"}
    replay = subprocess.run([sys.executable, str(ROOT / "replay/main.py")],
                            capture_output=True, text=True, env=env, cwd=ROOT)
    detect = subprocess.run([sys.executable, "main.py"], input=replay.stdout,
                            capture_output=True, text=True, env=env,
                            cwd=ROOT / "detector")
    return [json.loads(l) for l in detect.stdout.splitlines() if l.strip()]


def test_narrative_fields_contain_no_snake_case():
    alerts = sample_alerts()
    assert len(alerts) >= 10  # the manual-review sample size the gate names
    for alert in alerts:
        for field in NARRATIVE_FIELDS:
            value = alert.get(field)
            if value is None:
                continue
            leaked = SNAKE.findall(str(value))
            assert not leaked, f"{field} leaks raw identifiers {leaked}: {value!r}"


def test_decision_fields_always_populated():
    """Hard gate B1: priority, action, root cause, impact on EVERY alert."""
    for alert in sample_alerts():
        for field in ("priority_tier", "recommended_action",
                      "likely_root_cause", "impact_class", "confidence"):
            assert alert.get(field) not in (None, ""), \
                f"alert missing {field}: {alert.get('detector_source')}"
