-- Export: data/raw/meter_values.csv (source table: connector_meter_value)
-- One row per OCPP MeterValues.req sampledValue entry.
-- Column names/schema inferred from the export header; reconcile against the real
-- CSMS schema before reuse.
--
-- KNOWN ISSUE: the current export.csv is capped at exactly 1000 rows and, because
-- this table is sampled every ~30s per active transaction, that only covers a few
-- hours of one transaction (2026-05-02 06:08 to 09:18) instead of the intended
-- window. Re-export in date-bounded batches (see :window_start/:window_end below)
-- rather than a single unbounded/limited pull.
--
-- The existing data/raw/meter_values.csv predates this filter and mixes
-- measurands (energy, power, voltage, current, SoC, ...) as separate rows
-- sharing the same (transaction_pk, connector_pk, timestamp) key. This query
-- filters to energy-only readings so future exports don't have that problem.
SELECT
    transaction_pk,
    connector_pk,
    meter_reading_wh,
    timestamp
FROM connector_meter_value
WHERE timestamp >= :window_start
  AND timestamp <  :window_end
  AND measurand = 'Energy.Active.Import.Register'
  AND unit = 'Wh'
ORDER BY transaction_pk, timestamp;
