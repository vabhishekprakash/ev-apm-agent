#!/bin/bash
# Anonymization audit (week2_exit_criteria_and_tests.md, Suite E3).
# Scans ALL committed text files (git ls-files minus binary artifacts) —
# data/raw is gitignored by design and out of scope.
#
# Design notes (2026-07-05 security-review fixes):
# - Validates the stated policy directly: every charge-box reference in
#   committed data files must be a 64-char SHA-256 hex — instead of only
#   blocklisting one known name family.
# - Notebooks are IN scope for every check (embedded outputs are the
#   highest-risk leak vector).
# - IPv4 matching uses octet validation + hex/dotted-run boundaries, so
#   firmware strings like "…1.06.25.07.25.Beta1" fall out structurally,
#   not via file exclusions. 0.0.0.0/8 and loopback are non-routable.
# - Exclusion filters are line-context-narrow, not file-type-broad.
cd "$(dirname "$0")/.." || exit 2
export LC_ALL=C   # grep -P requires a unibyte/UTF-8 locale on Git Bash
FAIL=0

mapfile -t FILES < <(git ls-files | grep -v -E '\.(pkl|png|gif|jpg|ico|svg)$' |
    grep -v -E '^tests/anonymization_audit\.sh$')  # the detector itself

echo "— policy check: charge-box columns in committed CSVs are 64-hex only —"
if ! py - <<'PYEOF'
import csv, re, subprocess, sys
files = subprocess.run(["git", "ls-files", "*.csv"], capture_output=True,
                       text=True).stdout.split()
bad = []
for path in files:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = [c for c in (reader.fieldnames or []) if "charge_box" in c.lower()]
        for row in reader:
            for col in cols:
                value = (row.get(col) or "").strip()
                if value and not re.fullmatch(r"[0-9a-f]{64}", value):
                    bad.append(f"{path}: {col}={value[:40]}")
if bad:
    print("\n".join(bad[:10])); sys.exit(1)
print("all charge-box values hashed")
PYEOF
then FAIL=1; fi

echo "— known raw station-name family (PRABHAEV*) anywhere committed —"
HITS=$(grep -l -E "PRABHAEV[0-9A-Z]+" "${FILES[@]}" 2>/dev/null)
if [ -n "$HITS" ]; then
    echo "$HITS"
    echo "^ REVIEW REQUIRED before repo goes public (docs state the sha256 mapping)"
    FAIL=1
else echo "none"; fi

echo "— routable IPv4 + phone-shaped strings (python: no grep -P locale traps," \
     "notebooks INCLUDED, errors are loud) —"
if ! py - "${FILES[@]}" <<'PYEOF'
import re, sys
ip = re.compile(r"(?<![\w.])((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
                r"(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(?![\w.])")
phone = re.compile(r"(?<![0-9a-fA-F])(\+91)?[6-9][0-9]{9}(?![0-9a-fA-F])")
bad = []
for path in sys.argv[1:]:
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in ip.finditer(line):
            addr = m.group(0)
            # non-routable / known-safe: bind-all, loopback, 0.0.0.0/8
            # firmware-version shapes (manually reviewed 2026-07-05)
            if addr.startswith(("0.", "127.")):
                continue
            bad.append(f"{path}:{lineno}: IP {addr}")
        for m in phone.finditer(line):
            bad.append(f"{path}:{lineno}: phone {m.group(0)}")
if bad:
    print("\n".join(bad[:20])); sys.exit(1)
print("none")
PYEOF
then FAIL=1; fi

echo "— RFID/idTag-shaped fields (strip known-safe tokens, then retest the remainder —" \
     "a safe phrase on the line cannot mask a real identifier next to it) —"
if ! py - "${FILES[@]}" <<'PYEOF'
import re, sys
# Known-safe literals are REMOVED from the line, then the detector regex runs
# on what remains — closes the allowlist semantic escape (security review).
SAFE = [
    "idTag=REDACTED RFID", "idTag=REDACTED", "REDACTED-IDTAG", "RfidStop",
    "embedded RFID idTag value redacted",
    "customer/RFID/IP", "customer/RFID", "RFID hashes", "RFIDs, IPs",
    "RFID formats", "idTag value redacted", "dropped at export",
]
pattern = re.compile(r"id_tag|idtag|rfid", re.I)
anonymization_context = re.compile(r"anonymi[sz]", re.I)
bad = []
for path in sys.argv[1:]:
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    for lineno, line in enumerate(text.splitlines(), 1):
        if not pattern.search(line):
            continue
        stripped = line
        for token in SAFE:
            stripped = stripped.replace(token, "")
        # prose lines about the anonymization policy may name the field class;
        # only exempt them when no identifier-shaped remainder survives
        if pattern.search(stripped) and not (
                anonymization_context.search(line) and "=" not in stripped):
            bad.append(f"{path}:{lineno}: {line.strip()[:90]}")
if bad:
    print("\n".join(bad[:20])); sys.exit(1)
print("none")
PYEOF
then FAIL=1; fi

echo "— precise geo coordinates (>2 decimal places, paired) —"
HITS=$(grep -n -E "\b[0-9]{1,3}\.[0-9]{3,}, ?-?[0-9]{1,3}\.[0-9]{3,}\b" "${FILES[@]}" 2>/dev/null)
if [ -n "$HITS" ]; then echo "$HITS"; FAIL=1; else echo "none"; fi

echo "— secrets committed —"
HITS=$(git ls-files | grep -E "(^|/)\.env$|\.pem$|\.key$|credentials")
if [ -n "$HITS" ]; then echo "$HITS"; FAIL=1; else echo "none"; fi

if [ $FAIL -eq 0 ]; then echo "PASS"; else echo "AUDIT REQUIRES REVIEW"; fi
exit $FAIL
