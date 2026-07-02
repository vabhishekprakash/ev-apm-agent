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
- PRABHAEV004N dominates with ~4,439 normal sessions (~19% of fleet volume) —
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
ACS family 5, Exicom 3, PRABHAEV self-named 2, unknown 1.
**11 distinct vendor strings, 19 distinct firmware versions** — the
vendor-agnostic pitch is evidenced, not aspirational.

## Fault labels

**Two labeled fault events total**, both on PRABHAEV004N, 7 minutes apart,
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
2. PRABHAEV004N has 1 normal session on `connectorId=0` — malformed
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
   stray `connectorId=0` session is present, but PRABHAEV004N's ~4,439-session
   block is absent (max per-connector count in the file is 1,047). Either the
   audit counted differently or this export is partial — confirm with the data
   owner before treating the tier table above as reproducible. Tiers
   recomputed from the delivered file: heavy 1 / medium 11 / light 10 /
   marginal 10 / sparse 6.
8. `charger_stations.csv` matches inventory (80 connectors, 39 stations); it
   counts 12 vendor strings including a literal `NULL` pair — the NaN
   chargepoint from flag 1. `chargepoint.csv` likewise has 20 fw_version
   values including the null.
