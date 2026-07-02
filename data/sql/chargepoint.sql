-- Export: data/raw/chargepoint.csv
-- Charge point inventory: one row per physical charger, coordinates masked for privacy.
-- Column names/schema inferred from the export header; reconcile against the real
-- CSMS schema (source table name unknown) before reuse.
SELECT
    hashed_charge_box_id,
    vendor,
    model,
    fw_version,
    masked_latitude,
    masked_longitude,
    registration_time
FROM chargepoint
ORDER BY registration_time;
