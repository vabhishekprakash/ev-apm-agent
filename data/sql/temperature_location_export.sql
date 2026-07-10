-- ONE-SHOT export request (2026-07-10): temperature with sensor location +
-- an err1051-bearing wide-matrix window. Same pipeline/format that produced
-- final_ai_training_matrix.csv - THAT export path delivers real values
-- (flag 26); the meter_values path delivered zeros (flags 11/20). Use this
-- path.
--
-- PRE-FLIGHT (run first; if either returns 0, STOP and tell us - do not
-- burn the export attempt):
--   1) SELECT COUNT(*) FROM <sampled_value_table>
--      WHERE measurand = 'Temperature' AND value > 0
--        AND location IS NOT NULL;          -- do temp samples carry a sensor location?
--   2) SELECT COUNT(*) FROM <sampled_value_table> sv
--      JOIN <connector_status> cs USING (connector_pk)
--      WHERE cs.vendor_error_code = 'system-err1051'
--        AND sv.timestamp BETWEEN '2026-01-01' AND '2026-06-30';
--
-- EXPORT A - temperature with location (the asymmetry prerequisite):
SELECT connector_pk, timestamp, measurand, location, unit, value
FROM <sampled_value_table>
WHERE measurand = 'Temperature'
  AND timestamp >= :window_start        -- 90 days preferred
  AND timestamp <  :window_end
ORDER BY connector_pk, timestamp;
-- All connectors if feasible; at minimum: 2009529, 2009530, 1679593,
-- 1679594, 1880097, 1880098, 1989806, 1989807.
--
-- EXPORT B - the same wide matrix as final_ai_training_matrix.csv
-- (status, error_code, vendor_error_code, all measurands, stop_reason,
-- is_active_session, minutes_since_tx_start) for ONE err1051-active
-- connector-month: connector 1679593, any month with system-err1051
-- activity (Aug 2025 - Jul 2026 all qualify per the sequence export).
-- This single pull closes err1051 full-evidence corroboration.
--
-- Delivery hygiene (every past failure encoded here): NO row caps; UTF-8;
-- full-precision 'YYYY-MM-DD HH:MM:SS.ffffff' timestamps; numeric-only
-- values (no embedded idTag/phone strings); complete final line.
