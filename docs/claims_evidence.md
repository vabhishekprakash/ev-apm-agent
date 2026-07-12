# Claims → Evidence table (submission honesty audit)

Every number that appears in the deck, video, or detailed document, traced to
the file or command that produces it. Built during the pre-submission
stabilization pass. **Status legend:**

- **BACKED** — reproducible right now from a committed file or command.
- **SOURCE-SCALE** — describes the full source CMS dataset, *not* reproducible
  from the committed (delivered/scrubbed) subset. Defensible only if framed
  explicitly as "at source / audited, not exported", never as a flat repo fact.
- **STALE** — conflicts with another surface or with the committed data; fix
  before submission.

| # | Claim (as it appears) | Value | Status | Evidence (file / command) |
|---|---|---|---|---|
| 1 | Layer 2 false-positive rate | **3.62%** | BACKED | `docs/layer2_scope.md:47`; `notebooks/04_holdout_evaluation.ipynb` (n=2,015, threshold −0.1187); restated by `bash scripts/run_all_tests.sh` §5 |
| 2 | Fault categories detected | **6 of 19** | BACKED (framing) | `docs/category_metrics.md` lists 7 firing *buckets* — voltage split into Under/OverVoltage; the pitch "6" counts voltage as one. Keep one framing everywhere. |
| 3 | Categories real-event verified | **all six** | BACKED | `docs/category_metrics.md`, flags 18/22/23/25/27; err1051 via status-spine (88/88) + transaction-linkage (2/2), meter-zero step still fixture-only |
| 4 | Stations | **39** | BACKED | `data/reference/total_stations.csv` (39 rows), `chargepoint.csv` (39) |
| 5 | Connectors | **80** | BACKED | `data/reference/charger_stations.csv` (80 rows). NB `FINALS_EXIT_CRITERIA.md` gate text still says "68" — stale. |
| 6 | Vendor brands | **12** | BACKED (loose) | `charger_stations.csv` vendor column = 12 distinct strings (incl. anonymized aliases + NULL + case-variants). Docs also say "11" and "5+" — pick one. |
| 7 | Firmware versions | **19** | BACKED | `data/reference/` inventory; `docs/data_audit_final.md:42` |
| 8 | Delivered normal sessions | **10,090** | BACKED | `data/reference/normal_sessions.csv` (10,090 rows) |
| 9 | Sessions audited at source | **23,084** | SOURCE-SCALE | `docs/data_audit_final.md` flag 7 — only 10,090 were delivered/committed; the balance "was never re-exported". Already hedged in prose; keep the hedge. |
| 10 | Total CMS events | **2.77M** | SOURCE-SCALE | `docs/data_audit_final.md:155` — explicitly "per the Week 2 spec"; **not** reproducible from any committed file. Frame as source-CMS scale or drop. |
| 11 | err1051 self-recovery | **80% (152/190) ≤15 s, median 10 s** | BACKED | `docs/category_metrics.md:8`; `docs/data_audit_final.md:226` (flag 23, n=190) |
| 12 | Mixed-fault self-clear | **~42% (n=2,041)** | BACKED | `docs/data_audit_final.md:129-130` (flag 12) |
| 13 | Vendor-code coverage | **100% resolved** | BACKED (metric) | `python detector/vendor_code_normalizer.py --measure-coverage data/reference/error_taxonomy.csv --min-coverage 0.80` → 100.0%. **Denominator is 659–660 distinct codes**, not 17,857 (see #14). |
| 14 | Distinct vendor codes | **17,857** | **STALE / SOURCE-SCALE** | Committed `error_taxonomy.csv` = 17,954 rows but only **659 distinct `vendor_error_code`** (758 distinct code↔category pairs). No interpretation yields 17,857; it is the source-CMS figure ("~17.5k per the Week 2 spec", `data_audit_final.md:155`). |
| 15 | Real fault events detected | GroundFailure **79,480**, WeakSignal **150**, OverVoltage **51**, UnderVoltage **637**, err1024 **99/99** | BACKED | `data/reference/missing_real_faults.csv` (79,681 total) + `data/raw/err1024_err1051_status_sequences.csv` |
| 16 | Raw OCPP-J ingestion | demonstrated on real log | BACKED | `data/raw/logs_sample.csv` (gitignored real CMS log): 20/20 frames parse, unparsed=0, connector reconciles to native pk 6253760; `tests/test_ocpp_log_adapter.py` (11 tests) |

## Flags requiring a human decision

**A — "17,857 distinct vendor codes" and "100% of 17,857 distinct codes
resolve" (rows #13, #14). HIGHEST PRIORITY.** The committed
`error_taxonomy.csv` carries **659** distinct vendor codes, not 17,857. A judge
who opens the file and counts gets 659. The coverage metric (100% resolved) is
real but its denominator is 659–660. **Decision:** either (a) reframe to
"~17.9k vendor strings observed at source; the delivered taxonomy carries 659
distinct codes, all 100% resolved to a labeled OCPP category" — honest and
still strong — or (b) replace 17,857 with the committed 659 everywhere
(detailed_document.md:97,159; deck_outline.md:51,87; slides_speaker_pack.md:80;
data_audit_final.md:201). Do **not** leave the flat "17,857 distinct" claim.

**B — "2.77M events" (row #10).** Spec-scale, not reproducible from committed
data. Frame explicitly as source-CMS scale or omit from the defended-numbers
list.

**C — "23,084 sessions" (row #9).** Source-scale; 10,090 committed. Prose
already hedges it — keep the hedge, never state 23,084 as a flat repo fact.

**D — "5 vs 6 real-event verified."** `slides_speaker_pack.md:83` still says
"5 real-event verified"; deck and detailed_document say "all six" (correct
after flags 25/27). Align the slides.

**E — "68 vs 80 connectors."** `FINALS_EXIT_CRITERIA.md` S1 gate text and §11
checklist say 68; the committed inventory and all other docs say 80. The 80 is
correct; annotate the gate doc's status column rather than editing the
criteria.

**F — "12 vs 11 vs 5+ vendor brands."** Minor; pick one count (12 is the
literal distinct-string count) and use it consistently.
