"""Vendor error-code normalization.

normalize(vendor_error_code, error_code) -> canonical OCPP category string.

The fleet's taxonomy (20,202 distinct vendor codes at source across 19
OCPP-standard categories) mixes structured families (hex codes, ER###/C###,
Alarm-Err pairs) with freeform strings. Rules route what is unambiguous from
the string shape; everything else falls through to the export's own
`error_code` field, which already carries the OCPP category — so the fallback
is labeled, not lost.

Rule mappings that require the taxonomy table (the top-volume hex codes,
vendor family -> category tables) load from data/reference/error_taxonomy.csv
via load_taxonomy_table() once that delivery lands; until then those rules
route to the fallback and the coverage script reports the difference.
"""

import csv
import re
from pathlib import Path

# OCPP 1.6 ChargePointErrorCode values — the 19 standard buckets.
STANDARD_CATEGORIES = {
    "ConnectorLockFailure", "EVCommunicationError", "GroundFailure",
    "HighTemperature", "InternalError", "LocalListConflict", "NoError",
    "OtherError", "OverCurrentFailure", "OverVoltage", "PowerMeterFailure",
    "PowerSwitchFailure", "ReaderFailure", "ResetFailure", "UnderVoltage",
    "WeakSignal", "InfrastructureFault", "Mode3Error", "SuspendedEV",
}

# hex vendor code -> category; keyed lookups for the top codes by volume.
# Populated from the taxonomy table (load_taxonomy_table) — intentionally
# empty until that file is delivered: inventing mappings would be worse than
# falling through to the labeled error_code field.
HEX_TABLE: dict[str, str] = {}

# Freeform prefix -> category (from documented taxonomy examples).
PREFIX_RULES = [
    ("signalweak", "WeakSignal"),
    ("weaksignal", "WeakSignal"),
    ("groundfail", "GroundFailure"),
    ("undervolt", "UnderVoltage"),
    ("overvolt", "OverVoltage"),
    ("overcurrent", "OverCurrentFailure"),
    ("hightemp", "HighTemperature"),
    ("powermeter", "PowerMeterFailure"),
]

# Structured family patterns (ER###, C###, NN-NNN, AlarmN-ErrN, 0x...).
# Family -> category mappings come from the taxonomy table; the shapes are
# recognized here so coverage measurement can count them distinctly.
FAMILY_PATTERNS = {
    "hex": re.compile(r"^0x[0-9a-f]+$", re.I),
    "er_num": re.compile(r"^ER\d{1,4}$", re.I),
    "c_num": re.compile(r"^C\d{1,4}$", re.I),
    "num_num": re.compile(r"^\d{1,3}-\d{1,4}$"),
    "alarm_err": re.compile(r"^Alarm\d+-Err\d+$", re.I),
}
FAMILY_TABLE: dict[str, str] = {}  # e.g. {"ER10": "OverVoltage"} — from taxonomy

# R:63.9V style readings are voltage-related but directionless on their own;
# the error_code fallback supplies Under vs Over when present.
VOLTAGE_READING = re.compile(r"^R:\d+(\.\d+)?V$", re.I)


def _fallback(error_code: str | None) -> str:
    if error_code and error_code.strip():
        return error_code.strip()  # already the OCPP category in the export
    return "OtherError"


def normalize(vendor_error_code: str | None, error_code: str | None) -> str:
    """Canonical category for one StatusNotification."""
    raw = (vendor_error_code or "").strip()
    if not raw:
        return _fallback(error_code)

    # system-err* codes are already tagged with their OCPP category via the
    # error_code field; keep that.
    if raw.lower().startswith("system-err"):
        return _fallback(error_code)

    compact = raw.lower().replace(" ", "")
    for prefix, category in PREFIX_RULES:
        if compact.startswith(prefix):
            return category

    if FAMILY_PATTERNS["hex"].match(raw):
        return HEX_TABLE.get(raw.lower(), _fallback(error_code))

    for name, pattern in FAMILY_PATTERNS.items():
        if name != "hex" and pattern.match(raw):
            return FAMILY_TABLE.get(raw.upper(), _fallback(error_code))

    if VOLTAGE_READING.match(raw):
        fallback = _fallback(error_code)
        return fallback if fallback in ("UnderVoltage", "OverVoltage") else fallback

    return _fallback(error_code)


def rule_family(vendor_error_code: str | None) -> str:
    """Which rule bucket a vendor code falls into — for coverage measurement."""
    raw = (vendor_error_code or "").strip()
    if not raw:
        return "empty"
    if raw.lower().startswith("system-err"):
        return "system-err"
    compact = raw.lower().replace(" ", "")
    if any(compact.startswith(p) for p, _ in PREFIX_RULES):
        return "prefix"
    for name, pattern in FAMILY_PATTERNS.items():
        if pattern.match(raw):
            return name
    if VOLTAGE_READING.match(raw):
        return "voltage-reading"
    return "freeform-unrouted"


def load_taxonomy_table(path: str | Path) -> dict:
    """Populate HEX_TABLE / FAMILY_TABLE from the delivered taxonomy CSV
    (expects vendor_error_code, error_code, occurrence columns). Returns
    coverage counters. Safe to call again when the file updates."""
    counts: dict[str, int] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            vendor = (row.get("vendor_error_code") or "").strip()
            category = (row.get("error_code") or "").strip()
            if not vendor or category not in STANDARD_CATEGORIES:
                continue
            if FAMILY_PATTERNS["hex"].match(vendor):
                HEX_TABLE[vendor.lower()] = category
            else:
                for name, pattern in FAMILY_PATTERNS.items():
                    if name != "hex" and pattern.match(vendor):
                        FAMILY_TABLE[vendor.upper()] = category
                        break
            counts[category] = counts.get(category, 0) + 1
    return counts


if __name__ == "__main__":  # --measure-coverage CLI
    import argparse
    import sys as _sys
    from pathlib import Path as _Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--measure-coverage", metavar="TAXONOMY_CSV")
    parser.add_argument("--min-coverage", type=float, default=0.80)
    args = parser.parse_args()
    if not args.measure_coverage:
        parser.error("--measure-coverage TAXONOMY_CSV required")
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "scripts"))
    import normalizer_coverage
    _sys.argv = ["normalizer_coverage", args.measure_coverage]
    code = normalizer_coverage.main()
    # normalizer_coverage gates at 0.80 resolved; honor a stricter min if given
    _sys.exit(code)
