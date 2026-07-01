-- Export: data/raw/transaction.csv
-- One row per charging session (start/stop timestamps + stop reason).
-- Column names/schema inferred from the export header; reconcile against the real
-- CSMS schema (source table name unknown) before reuse.
-- No LIMIT — the current export.csv is capped at exactly 1000 rows, which happens
-- to line up with the full 2026-04-01..2026-06-30 window here but should not be
-- assumed complete without confirming the true row count on the source table.
SELECT
    transaction_pk,
    connector_pk,
    start_timestamp,
    stop_timestamp,
    stop_reason
FROM `transaction`
WHERE start_timestamp >= :window_start
  AND start_timestamp <  :window_end
ORDER BY start_timestamp;
