"""Hard gate T3: same input -> same output, models load deterministically."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_committed_model_scores_are_deterministic():
    from layer2 import Layer2Anomaly
    scorer_a = Layer2Anomaly(ROOT / "models", threshold=-0.1187)
    scorer_b = Layer2Anomaly(ROOT / "models", threshold=-0.1187)
    features = {"duration_sec": 1800.0, "start_hour": 10.0}
    for pk in (2009529, 2009530):
        assert scorer_a.score_by_connector_pk(features, pk) == \
            scorer_b.score_by_connector_pk(features, pk)


def test_full_pipeline_replay_is_byte_identical():
    """Two runs of the fixture replay produce identical alert streams —
    event-time-driven throughout, no wall-clock leakage."""
    import os
    env = {**os.environ, "DATA_DIR": str(ROOT / "tests/fixtures/demo_replay"),
           "REPLAY_SPEED_MULTIPLIER": "0"}

    def run() -> str:
        replay = subprocess.run([sys.executable, str(ROOT / "replay/main.py")],
                                capture_output=True, text=True, env=env, cwd=ROOT)
        detect = subprocess.run([sys.executable, "main.py"], input=replay.stdout,
                                capture_output=True, text=True, env=env,
                                cwd=ROOT / "detector")
        return detect.stdout

    first, second = run(), run()
    assert first == second
    assert len([l for l in first.splitlines() if l.strip()]) > 0
    json.loads(first.splitlines()[0])  # and it is valid JSON lines
