"""Replay CLI contract tests — added after a silent-substitution incident
where a mistyped DATA_DIR replayed the demo fixture as if it were real data.

The contract: --help never replays; an explicitly requested folder with no
sources is a hard error (exit 2) naming the path; only the conventional
data/raw default falls back to the bundled fixture, and loudly; --input
overrides the DATA_DIR env var.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPLAY = [sys.executable, str(ROOT / "replay" / "main.py")]


def run(args, env_extra=None, timeout=60):
    env = {**os.environ, "REPLAY_SPEED_MULTIPLIER": "0", **(env_extra or {})}
    return subprocess.run(REPLAY + args, capture_output=True, text=True,
                          env=env, timeout=timeout, cwd=ROOT)


def test_help_exits_without_replaying():
    r = run(["--help"])
    assert r.returncode == 0
    assert "usage" in r.stdout.lower()
    assert '"event_type"' not in r.stdout, "--help must not emit replay events"


def test_unknown_flag_is_an_error_not_a_replay():
    r = run(["--definitely-not-a-flag"])
    assert r.returncode == 2
    assert '"event_type"' not in r.stdout


def test_explicit_missing_dir_fails_loudly(tmp_path):
    bogus = tmp_path / "no_such_export"
    r = run([], env_extra={"DATA_DIR": str(bogus)})
    assert r.returncode == 2, "explicit missing source must exit non-zero"
    assert str(bogus) in r.stderr, "error must name the path it looked for"
    assert '"event_type"' not in r.stdout, "nothing may be replayed"


def test_explicit_input_flag_missing_dir_fails_loudly(tmp_path):
    bogus = tmp_path / "typo_dir"
    r = run(["--input", str(bogus)])
    assert r.returncode == 2
    assert str(bogus) in r.stderr


def test_default_data_raw_falls_back_with_synthetic_banner(tmp_path):
    empty_default = tmp_path / "data" / "raw"   # conventional default shape
    empty_default.mkdir(parents=True)
    r = run([], env_extra={"DATA_DIR": str(empty_default)})
    assert r.returncode == 0
    assert "SYNTHETIC" in r.stderr, "fallback must announce synthetic data"
    assert '"event_type"' in r.stdout, "fixture events should replay"


def test_input_flag_overrides_data_dir_env(tmp_path):
    bogus = tmp_path / "ignored_env_dir"
    r = run(["--input", str(ROOT / "tests" / "fixtures" / "day5_replay")],
            env_extra={"DATA_DIR": str(bogus)})
    assert r.returncode == 0
    assert "4784325" in r.stdout, "day5 fixture events expected from --input"
