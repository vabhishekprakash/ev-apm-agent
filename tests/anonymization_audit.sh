#!/bin/bash
# Anonymization audit (week2_exit_criteria_and_tests.md, Suite E3).
# Scans COMMITTED files only (git ls-files) — data/raw is gitignored by design.
# Exit 1 on any hit that could identify real infrastructure or people.
cd "$(dirname "$0")/.." || exit 2
FILES=$(git ls-files '*.csv' '*.md' '*.ipynb' '*.py' '*.yml' '*.mmd' '*.svg')
FAIL=0

echo "— raw charger IDs (PRABHAEV*) in committed files —"
# 'PRABHAEV1'/'PRABHAEV251' as vendor strings in reference CSVs are vendor
# names from the inventory, not charger ids; flag everything and let the
# reviewer decide — a public repo should justify each hit.
HITS=$(grep -l -E "PRABHAEV[0-9]{3,}[A-Z]?" $FILES 2>/dev/null)
if [ -n "$HITS" ]; then
    echo "$HITS"
    echo "^ REVIEW REQUIRED: station-name references in committed files"
    FAIL=1
else
    echo "none"
fi

echo "— IPv4 addresses (excluding bind-all/localhost) —"
# chargepoint.csv's dotted strings are firmware versions (0.0.2.12,
# 1.06.25.x) and 2-decimal masked coordinates — manually reviewed 2026-07-05,
# not IPs; the fw_version exclusion below reflects that review.
HITS=$(grep -n -E "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" $FILES 2>/dev/null \
    | grep -v -E "0\.0\.0\.0|127\.0\.0\.1|version|Version|\.svg:" \
    | grep -v -E "chargepoint\.csv|Beta[0-9]|_Siemens_" )
if [ -n "$HITS" ]; then echo "$HITS"; FAIL=1; else echo "none"; fi

echo "— phone-number-shaped strings —"
HITS=$(grep -n -E "\+91[0-9]{10}|\b[6-9][0-9]{9}\b" $FILES 2>/dev/null | grep -v -E "\.svg:|\.ipynb:")
if [ -n "$HITS" ]; then echo "$HITS"; FAIL=1; else echo "none"; fi

echo "— RFID/idTag-shaped fields —"
HITS=$(grep -n -iE "id_tag|idtag|rfid" $FILES 2>/dev/null | grep -v -E "dropped|drop|anonymi|disclaimer|audit|pre-hashed")
if [ -n "$HITS" ]; then echo "$HITS"; FAIL=1; else echo "none"; fi

echo "— precise geo coordinates (>2 decimal places) —"
HITS=$(grep -n -E "\b[0-9]{1,3}\.[0-9]{3,}, ?-?[0-9]{1,3}\.[0-9]{3,}\b" $FILES 2>/dev/null)
if [ -n "$HITS" ]; then echo "$HITS"; FAIL=1; else echo "none"; fi

echo "— .env or secrets committed —"
HITS=$(git ls-files | grep -E "^\.env$|\.pem$|\.key$|credentials")
if [ -n "$HITS" ]; then echo "$HITS"; FAIL=1; else echo "none"; fi

if [ $FAIL -eq 0 ]; then echo "PASS"; else echo "AUDIT REQUIRES REVIEW"; fi
exit $FAIL
