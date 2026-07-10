#!/bin/bash
# Hard gate S3: fresh clone -> cp .env -> docker compose up -> UI 200 in ~30s.
# Clones the CURRENT repo into a temp dir so the test never sees local state.
set -e
SRC="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'cd /; docker compose -p coldstart down -v >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT

git clone --quiet "$SRC" "$TMP/clone"
cd "$TMP/clone"
cp .env.example .env
docker compose -p coldstart up -d --build
sleep 30
code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
docker compose -p coldstart down -v >/dev/null 2>&1
if [ "$code" = "200" ]; then echo "S3 COLD START: PASS (UI $code)"; exit 0
else echo "S3 COLD START: FAIL (UI $code)"; exit 1; fi
