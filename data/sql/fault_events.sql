-- Export request (Week 2 Day 1 Task 4): data/raw/fault_events.csv
-- Timestamped StatusNotification stream filtered to FAULT rows only —
-- unblocks Week 2 Days 4-5 (multi-category pattern audit + detection
-- metrics). 90-day window, full fleet, NO row cap (see EXPORT_NOTES.md for
-- the 1000-row cap that crippled the first export).
-- Anonymization: charge_box_id must ship as SHA-256 hash (house rule);
-- vendor_error_code is needed RAW — it is the input to the vendor-code
-- normalizer and contains no PII.
SELECT
    connector_pk,
    status,
    error_code,          -- OCPP standard category (19 values incl. NoError)
    vendor_error_code,   -- raw vendor string, input to normalization
    timestamp
FROM connector_status
WHERE error_code IS NOT NULL
  AND error_code <> 'NoError'
  AND timestamp >= :window_start   -- 90-day window
  AND timestamp <  :window_end
ORDER BY connector_pk, timestamp;
