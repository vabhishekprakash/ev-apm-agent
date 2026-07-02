# Raw Export Notes

Log of what's currently in `data/raw/`: filename, row count, when it was pulled, what
time window it covers, and who ran the export. Update this whenever a file here is
replaced.

| File | Rows | Exported | Window covered | Operator |
|---|---|---|---|---|
| `chargepoint.csv` | 39 | 2026-07-01 | n/a (inventory snapshot, registration_time 2025-08-08 to 2026-02-09) | Abhishek |
| `transaction.csv` | 1000 | 2026-07-01 | 2026-04-01 19:13 to 2026-06-30 13:34 | Abhishek |
| `meter_values.csv` | 1000 | 2026-07-01 | 2026-05-02 06:08 to 2026-05-02 09:18 | Abhishek |
| `status_notification.csv` | 1000 | 2026-07-01 | 2026-04-01 21:05 to 2026-06-30 11:52 | Abhishek |
| `heartbeat.csv` | 1000 | 2026-07-01 | 2026-05-02 01:07 to 2026-05-02 19:28 | Abhishek |
| `boot_notification.csv` | 1000 | 2026-07-01 | 2026-05-02 02:15 to 2026-06-30 11:52 | Abhishek |

## Known issue: 1000-row export cap

Every file except `chargepoint.csv` came back at exactly 1000 rows. For the
low-frequency tables (`transaction`, `status_notification`, `boot_notification`)
that happens to roughly span the intended Apr-Jun 2026 window, but for the
high-frequency tables it doesn't:

- `heartbeat.csv` covers only ~18 hours (one charge point, ~1 heartbeat/minute)
  instead of the full window.
- `meter_values.csv` covers only ~3 hours of a single transaction instead of the
  full window.

This points to a `LIMIT 1000` (or equivalent) on the export query. Re-export
`heartbeat` and `meter_values` in date-bounded batches using the `:window_start`/
`:window_end` params in `data/sql/heartbeat.sql` and `data/sql/meter_values.sql`
rather than a single unbounded pull, and confirm whether `transaction`,
`status_notification`, and `boot_notification` are actually complete or just
coincidentally under the cap.

## Known issue: meter_values has no measurand column (current export.csv only)

`meter_reading_wh` in the current `meter_values.csv` mixes energy, power,
voltage, current, and SoC readings as separate rows sharing the same
`(transaction_pk, connector_pk, timestamp)` key, distinguishable only by row
position within the group — because this export predates filtering by
measurand. The source table does have `measurand`/`unit` columns; going
forward, `data/sql/meter_values.sql` filters to
`measurand = 'Energy.Active.Import.Register' AND unit = 'Wh'` so re-exports
will be clean energy-only readings. The existing `data/raw/meter_values.csv`
still needs to be re-pulled with this filter before Layer 2 uses it.
