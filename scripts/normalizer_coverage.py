"""Vendor-code normalizer coverage measurement.

Usage: py scripts/normalizer_coverage.py [taxonomy.csv]

Reads the error taxonomy (default: data/reference/error_taxonomy.csv, falling
back to data/raw/Errornotify.csv), loads the hex/family lookup tables from it,
then reports — overall and per rule family — what share of vendor codes (and
of total occurrences, if an occurrence-count column exists) route to a named
OCPP category via rules vs fall through to the error_code field vs remain
OtherError.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "detector"))

from vendor_code_normalizer import (  # noqa: E402
    STANDARD_CATEGORIES, load_taxonomy_table, normalize, rule_family,
)

CANDIDATES = [
    ROOT / "data" / "reference" / "error_taxonomy.csv",
    ROOT / "data" / "raw" / "Errornotify.csv",
]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else next(
        (p for p in CANDIDATES if p.exists()), None)
    if path is None or not path.exists():
        print("taxonomy file not found (expected data/reference/error_taxonomy.csv"
              " — Errornotify delivery pending); nothing to measure")
        return 1

    from vendor_code_normalizer import FAMILY_TABLE, HEX_TABLE
    load_taxonomy_table(path)

    by_family: Counter = Counter()
    rule_decided = labeled_fallback = default_other = 0
    seen: set = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            vendor = (row.get("vendor_error_code") or "").strip()
            error_code = (row.get("error_code") or "").strip()
            if vendor in seen:
                continue  # coverage is over DISTINCT vendor codes
            seen.add(vendor)
            family = rule_family(vendor)
            by_family[family] += 1
            category = normalize(vendor, error_code)
            # Which path decided? Shape rules and taxonomy-fed lookup tables
            # count as rule-routed; the error_code field is the labeled
            # fallback; OtherError with no label is the true residue.
            rule_hit = (
                family in ("prefix", "voltage-reading")
                or (family == "hex" and vendor.lower() in HEX_TABLE)
                or (family in ("er_num", "c_num", "num_num", "alarm_err")
                    and vendor.upper() in FAMILY_TABLE)
            )
            if rule_hit and category in STANDARD_CATEGORIES:
                rule_decided += 1
            elif category in STANDARD_CATEGORIES or (
                    category == error_code and error_code):
                labeled_fallback += 1
            else:
                default_other += 1

    total = rule_decided + labeled_fallback + default_other
    resolved = rule_decided + labeled_fallback
    print(f"taxonomy: {path} — {total} distinct vendor codes")
    print(f"rule-decided (shape rules + taxonomy tables): {rule_decided:6d} "
          f"({rule_decided / total:.1%})")
    print(f"labeled fallback (error_code field):          {labeled_fallback:6d} "
          f"({labeled_fallback / total:.1%})")
    print(f"unlabeled OtherError residue:                 {default_other:6d} "
          f"({default_other / total:.1%})")
    print(f"\nRESOLVED to a labeled category (gate metric): {resolved / total:.1%}")
    print("\nrule-family shape distribution:")
    for family, count in by_family.most_common():
        print(f"  {family:18s} {count}")
    return 0 if resolved / total >= 0.80 else 1


if __name__ == "__main__":
    raise SystemExit(main())
