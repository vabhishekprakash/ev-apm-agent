# Claims → Evidence (two-tier: SOURCE SCALE vs DELIVERED/VALIDATED)

Every fleet/scale number that appears in the deck, video, or detailed document,
split into two tiers so a source-scale figure is never stated as if it were
reproducible from the delivered slice.

- **SOURCE SCALE** — the size of the originating production CMS. Evidenced by
  aggregate-count CSVs under `data/reference/` (public brand names + counts, no
  IDs/PII). **Not** reproducible from the delivered data slice; always label it
  "at source" and cite the evidence CSV.
- **DELIVERED / VALIDATED** — reproducible from the committed repo right now,
  each with a reproduction command. This is what the system was actually built
  and measured on.

All values below are read from the committed files (not from any prose). Where
a previously circulated figure did not match the committed evidence, the
committed value is used and the discrepancy is listed under "Human decisions".

## Tier 1 — SOURCE SCALE (evidenced, not reproducible from the delivered slice)

| Claim | Value | Evidence file |
|---|---|---|
| Chargers in source fleet | **655** | `data/reference/manufacturer_inventory.csv` (Σ `chargers`) |
| Manufacturer families | **131** (+ a NULL-manufacturer group of 132 chargers) | `data/reference/manufacturer_inventory.csv` (rows, excl. `NULL`) |
| Manufacturer-model configs | **209** | `data/reference/manufacturer_inventory.csv` (Σ `models`) |
| Distinct vendor error codes | **20,202** | `data/reference/source_vendor_code_counts.csv` |
| Total logged vendor-error occurrences | **1,744,075** (~1.74M) | `data/reference/source_vendor_code_counts.csv` |
| Total CMS events | **33,508,275** (~33.5M) | `data/reference/source_event_totals.csv` |
| — status-notification events | **3,434,764** (~3.4M) | `data/reference/source_event_totals.csv` |
| — telemetry-meter events | **30,073,511** (~30.1M) | `data/reference/source_event_totals.csv` |
| Total sessions in source CMS | **103,081** | `data/reference/source_session_count.csv` |

Reproduce any Tier-1 aggregate:
```bash
python - <<'PY'
import csv
for f in ("manufacturer_inventory","source_vendor_code_counts",
          "source_event_totals","source_session_count"):
    rows=list(csv.DictReader(open(f"data/reference/{f}.csv",encoding="utf-8-sig")))
    print(f, rows if len(rows)<=1 else
          {"rows":len(rows),"chargers":sum(int(r.get('chargers',0)) for r in rows),
           "models":sum(int(r.get('models',0)) for r in rows)})
PY
```

## Tier 2 — DELIVERED / VALIDATED (reproducible from the committed repo)

| Claim | Value | Reproduction |
|---|---|---|
| Stations | **39** | `wc -l data/reference/total_stations.csv` → 39 |
| Connectors | **80** | `wc -l data/reference/charger_stations.csv` → 80 |
| Delivered normal sessions | **10,090** | `wc -l data/reference/normal_sessions.csv` → 10,090 |
| Working taxonomy — canonical codes | **659** distinct, **100% resolved** | `python detector/vendor_code_normalizer.py --measure-coverage data/reference/error_taxonomy.csv --min-coverage 0.80` |
| Layer 2 false-positive rate | **3.62%** (n=2,015, threshold −0.1187) | `notebooks/04_holdout_evaluation.ipynb`; restated by `bash scripts/run_all_tests.sh` §5 |
| Fault categories detected | **6 of 19**, **all six real-event verified** | `docs/category_metrics.md`; `pytest tests/test_multicategory.py tests/test_layer1_err1051.py` |
| err1051 self-recovery | **80% (152/190) ≤15 s, median 10 s** | `docs/category_metrics.md:8`; `docs/data_audit_final.md` flag 23 |
| Mixed-fault self-clear | **~42% (n=2,041)** | `docs/data_audit_final.md` flag 12 |
| Real fault events | GroundFailure **79,480**, WeakSignal **150**, OverVoltage **51**, UnderVoltage **637**, err1024 **99/99** | `data/reference/missing_real_faults.csv`; `data/raw/err1024_err1051_status_sequences.csv` |
| Raw OCPP-J ingestion | demonstrated on real CMS log | `tests/test_ocpp_log_adapter.py` (11 tests); `data/raw/logs_sample.csv` (gitignored): 20/20 frames, unparsed=0 |

## Narration guidance (spoken numbers)

**Manufacturer count:** the committed 131 is the count of distinct
`manufacturer` strings in `manufacturer_inventory.csv` and **includes
spelling/series variants** (e.g. `ACS ENERGY` / `ACS-ENERGY` / `ACSENERGY`) —
it is **not a true distinct-brand count**, and no committed grouping rule can
produce one. The defensible spoken figure is **"130+ manufacturer families
across 209 models"** — never a precise brand number. All pitch docs use the
"130+" phrasing for this reason.

## How the two tiers map into the pitch

- **Scalability** leads with SOURCE SCALE: "a production CMS spanning 655
  chargers, 130+ manufacturer families, 209 models, 33.5M events, 103k
  sessions" — then narrows to the delivered slice the system was validated on
  (39 stations / 80 connectors / 10,090 sessions).
- **Vendor-agnostic normalization**: "20,202 distinct vendor error strings at
  source (1.74M occurrences); the delivered working taxonomy carries 659
  canonical codes, 100% resolved to OCPP categories."
- **Never** merge tiers into one unlabeled number (e.g. "we handle 20,202
  codes" — we *observed* that many at source and *resolve* 659 in the
  delivered taxonomy).

## Human decisions (committed evidence differs from previously circulated prose)

The values in this file are the committed-CSV values. Earlier prose circulated
slightly different figures; confirm which to speak in the video:

- **Manufacturer families: file = 131, earlier prose = "~119".** 131 is the
  distinct non-NULL `manufacturer` strings in `manufacturer_inventory.csv`;
  some are spelling/series variants (e.g. `ACS ENERGY` / `ACS-ENERGY` /
  `ACSENERGY`), so the true collapsed brand-family count is lower and not
  mechanically reproducible without a grouping rule. Recommend speaking
  "**130+ manufacturer families across 209 models**" (reproducible, still the
  strongest scalability line) rather than a precise 119.
- **Vendor codes: file = 20,202 / 1,744,075; earlier prose = 19,986 / 1.7M.**
  Used the file values.
- **Events: file = 33,508,275 (3,434,764 status + 30,073,511 telemetry);
  earlier prose = 33.2M.** Used the file values (~33.5M).
- **Sessions: file = 103,081; earlier prose = 102,264.** Used the file value.
- **`manufacturer_inventory.csv` was transformed before commit:** the raw
  per-model file carried un-aliased operator-name strings (owner clearance
  revoked; the `VENDOR-P*` alias family) and product model names carrying a
  card-reader token, both of which fail the anonymization audit. The committed
  file is an audit-safe manufacturer-level aggregate (operator names mapped to
  their `VENDOR-P*` aliases, raw model-name strings dropped, all counts
  preserved). The raw per-model file must not be committed.
