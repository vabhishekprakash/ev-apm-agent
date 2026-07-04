"""Vendor-code normalizer coverage measurement (Week 2 Day 4, Akhil Task 2).

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

    load_taxonomy_table(path)

    by_family: Counter = Counter()
    routed_named = routed_fallback = other = 0
    weighted = Counter()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            vendor = (row.get("vendor_error_code") or "").strip()
            error_code = (row.get("error_code") or "").strip()
            occurrences = int(row.get("occurrence") or row.get("count") or 1)
            family = rule_family(vendor)
            by_family[family] += 1
            category = normalize(vendor, error_code)
            if category == "OtherError":
                other += 1
                weighted["other"] += occurrences
            elif category in STANDARD_CATEGORIES and category != error_code:
                routed_named += 1          # a rule decided, not the fallback
                weighted["rules"] += occurrences
            else:
                routed_fallback += 1       # fell through to the labeled field
                weighted["fallback"] += occurrences

    total = routed_named + routed_fallback + other
    print(f"taxonomy: {path} — {total} distinct vendor codes")
    print(f"routed by rules:        {routed_named:6d} ({routed_named / total:.1%})")
    print(f"fallback to error_code: {routed_fallback:6d} ({routed_fallback / total:.1%})")
    print(f"OtherError residue:     {other:6d} ({other / total:.1%})")
    if weighted:
        w_total = sum(weighted.values())
        print(f"occurrence-weighted: rules {weighted['rules'] / w_total:.1%}, "
              f"fallback {weighted['fallback'] / w_total:.1%}, "
              f"other {weighted['other'] / w_total:.1%}")
    print("\nrule-family shape distribution:")
    for family, count in by_family.most_common():
        print(f"  {family:18s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
