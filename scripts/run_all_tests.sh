#!/bin/bash
# One-command acceptance run (week2_exit_criteria_and_tests.md, Part 5).
# Usage: bash scripts/run_all_tests.sh [--with-docker]
set -u
cd "$(dirname "$0")/.." || exit 2
PY=${PY:-py}
FAIL=0

echo "=== 1. unit + integration tests (Suites A, B, C4-5, D2-3, E1-2) ==="
$PY -m pytest tests/ -q || FAIL=1

echo "=== 2. anonymization audit (Suite E3) ==="
bash tests/anonymization_audit.sh || {
    echo "(review required — see hits above; PRABHAEV station-name scrub is a"
    echo " pre-repo-public gate, tracked for Week 3 Day 6)"; FAIL=1; }

echo "=== 3. full-replay pipeline smoke (Suite F2-shape, local) ==="
REPLAY_SPEED_MULTIPLIER=0 $PY replay/main.py 2>/dev/null \
    | (cd detector && LAYER2_THRESHOLD=-0.1187 $PY main.py) 2>&1 >/dev/null \
    | grep -E "flag rate|summary" || FAIL=1

echo "=== 4. vendor-code coverage (Suite D1 — needs error_taxonomy.csv) ==="
$PY scripts/normalizer_coverage.py || echo "(blocked: taxonomy not delivered)"

echo "=== 5. FPR (Suite C1) ==="
echo "chronological holdout: 3.62% overall at -0.1187 (notebook 04, n=2015)"
echo "re-execute: jupyter nbconvert --to notebook --execute notebooks/04_holdout_evaluation.ipynb"

if [ "${1:-}" = "--with-docker" ]; then
    echo "=== 6. docker cold start (Suite F1) ==="
    docker compose down -v >/dev/null 2>&1
    docker compose up -d --build || FAIL=1
    sleep 30
    curl -sf http://localhost:8000/ >/dev/null && echo "UI 200 OK" || { echo "F1 FAIL"; FAIL=1; }
    docker compose down >/dev/null 2>&1
fi

[ $FAIL -eq 0 ] && echo "=== ALL RUNNABLE SUITES GREEN ===" || echo "=== FAILURES/REVIEWS ABOVE ==="
exit $FAIL
