-- Export: data/raw/boot_notification.csv
-- One row per OCPP BootNotification.req (charge point reboot/reconnect events).
-- Column names/schema inferred from the export header; reconcile against the real
-- CSMS schema (source table name unknown) before reuse.
-- No LIMIT — see data/raw/EXPORT_NOTES.md for the 1000-row cap caveat that applies
-- to the current export.csv.
SELECT
    log_sequence_id,
    hashed_charge_box_id,
    timestamp,
    registration_status
FROM boot_notification
WHERE timestamp >= :window_start
  AND timestamp <  :window_end
ORDER BY hashed_charge_box_id, timestamp;
