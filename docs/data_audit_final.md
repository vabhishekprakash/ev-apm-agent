# Data Audit v0

Formalized from the Week 1 audit (source numbers: SPEC.md §3). Owner: Akhil.
Reproduce via `notebooks/01_data_audit.ipynb` once the reference CSVs are in
`data/reference/`.

## Source and constraints

- Production CMS MySQL, read-only, one-time export via Workbench (no live API).
- Anonymization at export: SHA-256 `charge_box_id`, geo rounded to 2 decimals
  (~1 km), customer/RFID/IP dropped.
- Transactional window: 90 days ending 2026-06-30 (UTC). Dimensional tables
  (`chargepoint`, firmware) pulled unfiltered.
- OCPP 1.6, no vendor mapping doc.

## Fleet inventory

- **39 charging stations**, 80 listed connectors, **~68 physical connectors**
  (12 stations list `connectorId=0`, which is charge-point-level, not a socket).
- Station shapes: 10 single-connector, 17 two-connector, 12 with `0,1,2`.
- **23,084 normal (fault-free) sessions across 46 active connectors.**
- Station-A dominates with ~4,439 normal sessions (~19% of fleet volume) —
  downsample or train strictly per-connector to avoid dominance.

## Session-volume tiers (Layer 2 viability)

| Tier | Sessions/connector | Connectors | Modeling approach |
|---|---|---|---|
| Heavy | ≥1000 | 7 | Per-connector baseline strong |
| Medium | 250–999 | 15 | Per-connector baseline solid |
| Light | 100–249 | 13 | Per-connector baseline thin but workable |
| Marginal | 30–99 | 5 | Pooled baseline preferred |
| Sparse | <30 | 6 | Pool only |

35/46 connectors have ≥100 sessions → per-connector baselines viable for the
majority; pooled cohort baseline for the other 11.

## Vendor / firmware diversity

Tucker 11, Siemens family (SIEMENS + CN.TH on Siemens firmware) 12, IONGRID 5,
ACS family 5, Exicom 3, operator self-named (VENDOR-P*) 2, unknown 1.
**11 distinct vendor strings, 19 distinct firmware versions** — the
vendor-agnostic pitch is evidenced, not aspirational.

## Fault labels

**Two labeled fault events total**, both on Station-A, 7 minutes apart,
different connectors:

- `system-err1051` (GQ_DIN_ERROR_INIT_SOCKET): reproducible 5-step sequence —
  Charging+err1051 → MeterValues drop to zero → Finishing+err1051 →
  StopTransaction(Other) → Available ~13 s later. Deterministic.
- `system-err1024` (GQ_SLAC_ERROR_PARAM_TIMEOUT): SLAC/ISO 15118 handshake
  failure, pre-charge point event, no state machine. Ordering investigation
  open (SPEC §7 item 1).

Both are "session never really started" failures → no pre-window in the
faulted session's own telemetry. **Telemetry silence during an active session
is itself the fault signature** (the reporting loop shares the failing control
path) — encoded as a Layer 1 sub-detector.

## Data-quality flags

1. One `chargepoint` row with NaN vendor/model/firmware (valid coords +
   registration). Week 1 decision: impute `"unknown"`; revisit if it affects
   Layer 2 cohorting.
2. Station-A has 1 normal session on `connectorId=0` — malformed
   StartTransaction; drop from training, flag to data owner.
3. 7 chargers registered after Feb 2026 — short history, likely sparse tier
   regardless of activity.
4. SoC field unreliable (0 when not transmitted) — use CC-CV power-curve shape
   as proxy.

### Export-mechanics flags (added 2026-07-01, see data/raw/EXPORT_NOTES.md)

5. Transactional exports came back capped at exactly 1000 rows. `heartbeat`
   covers ~18 h and `meter_values` ~3 h instead of the 90-day window —
   re-export in date-bounded batches.
6. The current `meter_values` export predates the measurand filter and mixes
   energy/power/voltage/current/SoC rows indistinguishably. Re-export with
   `measurand = 'Energy.Active.Import.Register' AND unit = 'Wh'`
   (already in `data/sql/meter_values.sql`).

### Reference-set flags (added 2026-07-02, on delivery of data/reference/*.csv)

7. The delivered `normal_sessions.csv` has **10,090 sessions across 38
   connectors (28 stations)** — not the 23,084 sessions / 46 active connectors
   from the Week 1 audit. The window matches (2026-04-01 → 2026-06-30) and the
   stray `connectorId=0` session is present, but Station-A's ~4,439-session
   block is absent (max per-connector count in the file is 1,047). Either the
   audit counted differently or this export is partial — confirm with the data
   owner before treating the tier table above as reproducible. Tiers
   recomputed from the delivered file: heavy 1 / medium 11 / light 10 /
   marginal 10 / sparse 6.
8. `charger_stations.csv` matches inventory (80 connectors, 39 stations); it
   counts 12 vendor strings including a literal `NULL` pair — the NaN
   chargepoint from flag 1. `chargepoint.csv` likewise has 20 fw_version
   values including the null.

### New-delivery flags (added 2026-07-04: master_training_set.csv + recovered_station_a_sessions.csv)

9. **Station-A identity correction.** Station-A (alias; charge-box hash
   `0c70c6b0…`) — vendor **CN.TH**, connector_pks **2009529 (plug 1), 2009530
   (plug 2), 2013696 (plug 0 — the connectorId=0 anomaly, 799 status rows /
   145 fault episodes of its own)**. Earlier Week-1 docs, fixtures, and PR
   text mislabeled station `d4416bd8…` (vendor VENDOR-P1, pks 4784325/5802030)
   as Station-A. Reference files were always internally consistent; only
   our labels were wrong. Fixture data is synthetic and unaffected; per-connector
   IsoForest models for the real Station-A (`isoforest_0c70c6b0…_1/_2.pkl`)
   exist and were trained on its 861/880 delivered sessions.
10. **Fault-evidence windows (master_training_set.csv, 852 rows, 46 fault
    events, June 2026).** Six measurands per event (V/A/kW/Wh/Hz/°C). During
    faults **voltage never drops (179.9–241.6 V)**; only Current.Import and
    Power.Active.Import collapse to 0. The SPEC Day-4 meter-zero guard
    (`voltage AND current AND power == 0`) would **never fire** on this
    evidence — when the measurand-bearing re-export lands, the guard should be
    `current == 0 AND power == 0` (voltage nominal). Current stand-in
    (`meter_reading_wh == 0`) unchanged until then. `fault_ref` joins nothing
    in our exports (0/46 against transaction_pk) — semantics unknown, ask the
    data owner.
11. **Temperature field is dead in the fault evidence: all 142 Temperature
    rows are 0.0 °C.** Layer-2 temperature features (peak temps, outlet
    asymmetry) remain unvalidatable on real data, and would train as all-zero
    garbage if fed this export. Logged as a red-flag Issue per the Day-5
    joint checklist.
12. **Recovered Station-A status history (41,183 rows, 2025-10-03 →
    2026-07-04)** substantially fills flag 7's missing block: ~4,715 charging
    episodes ≈ the audited ~4,439 sessions (longer window). Fault reality on
    this station: **2,041 Faulted episodes** (946 + 950 + 145 per connector),
    recovery **median 33 s, p25 4 s, p75 ~245 s — only ~42% ≤ 15 s**. The
    "13-second transient" narrative describes the fast quartile, not the
    majority; alert-prioritization (Week 2 Day 1) should assume most faults
    are dispatch-relevant. No error codes in this file — err1051 vs err1024
    split still requires the data-owner reply (escalation still open).
13. **Silence-alert triage (capped export):** of 859 sessions with >90 s
    quiet tails, 858 have no meter rows at all in the capped export and 1
    ends at the meter-table cutoff (2026-05-02 09:18) — **0 real mid-session
    silences; the 229 telemetry_silence alerts on capped-export replay are
    100% export-truncation artifacts.** The detector logic is validated by
    unit tests and fixtures; artifact alerts will disappear with the
    date-bounded re-export (flag 5).

### Week 2 final refresh (2026-07-04, file renamed from data_audit_v0.md)

14. **Headline FPR locked:** 3.62% on the chronological per-connector 80/20
    holdout at the deployed threshold −0.1187 (notebook 04, n=2,015);
    per-tier heavy 3.3 / medium 3.5 / light 3.2 / pooled-tier 6.1%
    (n=148); `siemens` family 10.5% (n=76) on the watch list.
15. **Category coverage:** Layer 1 detects the 6 target categories (err1051,
    err1024, telemetry-silence, WeakSignal, GroundFailure, Under/OverVoltage)
    — fixture-verified end-to-end with prioritizer escalations
    (docs/category_metrics.md); real-event verification blocked on the
    fault-event export (data/sql/fault_events.sql, request pending).
16. **Taxonomy delivery still pending:** Errornotify.csv (19 OCPP categories,
    2.77M occurrences, ~17.5k vendor codes per the Week 2 spec) has not
    landed; the vendor-code normalizer's hex/family lookup tables and the
    coverage measurement (scripts/normalizer_coverage.py) await it.
17. **Lead-time analysis (docs/layer2_leadtime.md):** drift flags do NOT
    precede fault episodes on the current feature set (lift 0.57×, and
    pre-fault windows cover 73% of sessions on the test station) — Layer 2
    is framed as orthogonal degradation tracking. Expanded-normal retrain
    for 2009529/2009530 shipped after passing the FPR gate
    (1.74%→1.16% / 2.84%→2.84%).
18. **Correction (2026-07-04, found in the W2D6 dry-run):** the capped
    status export is NOT fault-free — it carries 344 non-NoError rows:
    UnderVoltage 18, PowerMeterFailure 22, EVCommunicationError 12,
    OtherError 102, plus vendor strings ("Available after Finishing
    Status" 106, "Transaction Stopped" 84). Earlier "zero fault rows"
    statements were true only of the err1051/err1024 sequences.
    Consequence: **UnderVoltage detection is verified on real events**
    (18/18 alerts on replay); the deck may claim one real-verified
    category beyond telemetry-silence today.
19. **fault_ref semantics pinned by analysis (2026-07-05):** temporal join of
    the 46 evidence windows against recovered Station-A fault episodes
    matches exactly one ref (5129) — to a **simultaneous both-plugs fault**
    (13:12:20/21 on 2026-06-04), with the meter window starting ~3 min after
    the fault. Conclusions: fault_refs are fleet-wide fault-table ids (45/46
    belong to other stations); the windows are **post-fault meter captures**,
    not pre-fault telemetry; no time-ordering (rank corr −0.47). Follow-on
    finding: **88% of Station-A fault episodes hit both plugs within 5 s**
    — the dominant fault mode is station-level (supply/controller), now
    encoded as the prioritizer's station-wide P1 escalation. The data-owner
    mapping table remains a nice-to-have; nothing in Week 3 depends on it.
20. **Temperature: formally out of scope (2026-07-05).** Third independent
    confirmation of the dead field — the err1024 crash signature reports
    Temperature 0.0 (min=max=mean) alongside the 142/142 zero rows in the
    evidence windows. Decision: temperature features (peak temps, outlet
    asymmetry) are excluded from the hackathon deliverable; code stays
    (tested against the sampledValue contract) for a future export that
    carries real values. No deck/demo claim references temperature.
21. **err1024 blocker closed (2026-07-05):** the data-owner reply arrived as
    data/raw/err1024_crash_signature.csv (3 events, aggregate stats):
    voltage 227.4–227.9 V and frequency ~49.9 Hz nominal throughout,
    current ≤0.3 A → 0.01 A, power ≤0.01 kW → 0, energy register flat
    (+0.2 Wh). "Energized but never charging" — corroborates the pre-charge
    SLAC mechanism. No retry/recovery sequencing exists, so the point-event
    handler is **confirmed final** (Week 1 exit criterion satisfied on both
    branches of its either/or).
22. **Taxonomy + fault-event exports delivered and committed (2026-07-06):**
    `data/reference/error_taxonomy.csv` (17,954 rows, 19 OCPP categories,
    17,857 distinct vendor codes — one embedded RFID idTag value redacted
    before commit per governance) and
    `data/reference/missing_real_faults.csv` (79,681 rows after dropping one
    truncated trailing line; GroundFailure 79,480 / WeakSignal 150 /
    OverVoltage 51 across 113 connectors in a separate pk namespace, no
    inventory overlap — enrichment lookups miss by design until the mapping
    arrives). Results: **normalizer coverage 100% resolved to labeled
    categories** (0% unlabeled residue; only 0.9% decided by shape rules —
    the fleet's vendor codes are 99% freeform, so the labeled error_code
    field carries the routing; pitch reframed accordingly per SPEC risk 2).
    **Real-event detection 100% per category**; WeakSignal bursts (6→P2)
    and OverVoltage 24h repeats (32→P1) escalated on real-world patterns.
    Real-verified categories now 5 of 6; the err1051/err1024 status
    sequences remain absent from every delivered export
    (fixture + crash-signature verified). Note: 79,480 GroundFailure P1s
    in 14 months on one fleet segment = chattering sensor cohort —
    dedup/rate-limiting is a documented future-work item, out of scope
    (Week 3 freeze).
