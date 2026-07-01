-- Export: data/raw/heartbeat.csv
-- One row per OCPP Heartbeat.req.
-- Column names/schema inferred from the export header; reconcile against the real
-- CSMS schema (source table name unknown) before reuse.
--
-- KNOWN ISSUE: the current export.csv is capped at exactly 1000 rows and, because
-- heartbeats arrive roughly once a minute per charge point, that only covers about
-- 18 hours (2026-05-02 01:07 to 19:28) for a single charge point instead of the
-- intended multi-month window. Re-export in date-bounded batches (see
-- :window_start/:window_end below) rather than a single unbounded/limited pull.
SELECT
    log_sequence_id,
    hashed_charge_box_id,
    timestamp
FROM heartbeat
WHERE timestamp >= :window_start
  AND timestamp <  :window_end
ORDER BY hashed_charge_box_id, timestamp;
