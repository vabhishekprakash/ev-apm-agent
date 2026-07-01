-- Export: data/raw/status_notification.csv (source table: connector_status)
-- One row per OCPP StatusNotification.req (connector status + error code changes).
-- Column names/schema inferred from the export header; reconcile against the real
-- CSMS schema before reuse.
-- No LIMIT — see data/raw/EXPORT_NOTES.md for the 1000-row cap caveat that applies
-- to the current export.csv.
SELECT
    connector_pk,
    status,
    error_code,
    timestamp
FROM connector_status
WHERE timestamp >= :window_start
  AND timestamp <  :window_end
ORDER BY connector_pk, timestamp;
