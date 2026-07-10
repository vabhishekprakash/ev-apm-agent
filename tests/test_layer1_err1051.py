"""Unit tests for the err1051 5-step state machine (SPEC Day 4 table)."""

from datetime import datetime, timedelta

from layer1 import ERR_1051, Err1051Detector, Err1051State
from ocpp_messages import MeterValues, StatusNotification, StopTransaction

T0 = datetime(2026, 5, 15, 10, 0, 0)
CONN = 4784325


def status(offset_s: float, status: str, error_code: str) -> StatusNotification:
    return StatusNotification(
        connector_pk=CONN,
        status=status,
        error_code=error_code,
        timestamp=T0 + timedelta(seconds=offset_s),
    )


def meter(offset_s: float, wh: float) -> MeterValues:
    return MeterValues(
        transaction_pk=900001,
        connector_pk=CONN,
        meter_reading_wh=wh,
        timestamp=T0 + timedelta(seconds=offset_s),
    )


def stop(offset_s: float, reason: str = "Other") -> StopTransaction:
    return StopTransaction(
        transaction_pk=900001,
        connector_pk=CONN,
        stop_timestamp=T0 + timedelta(seconds=offset_s),
        stop_reason=reason,
    )


def run_sequence(det: Err1051Detector, events: list) -> list:
    return [a for a in (det.consume(e) for e in events) if a is not None]


def test_full_sequence_emits_candidate_then_transient_final():
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Charging", ERR_1051),
        meter(2, 0),
        status(4, "Finishing", ERR_1051),
        stop(5, "Other"),
        status(18, "Available", "NoError"),  # 13s after stop
    ])
    assert [a.stage for a in alerts] == ["candidate", "final"]
    final = alerts[1]
    assert final.recovered_after_seconds == 13.0
    assert final.is_transient
    assert final.classification == "transient"
    assert det.state is Err1051State.IDLE  # machine reset after completion


def test_slow_recovery_classified_technician_dispatch():
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Charging", ERR_1051),
        meter(2, 0),
        status(4, "Finishing", ERR_1051),
        stop(5, "Other"),
        status(30, "Available", "NoError"),  # 25s after stop
    ])
    final = alerts[-1]
    assert final.recovered_after_seconds == 25.0
    assert not final.is_transient
    assert final.classification == "technician-dispatch"


def test_nonmatching_events_do_not_advance_or_fire():
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Charging", ERR_1051),
        meter(2, 4200),           # nonzero reading: no METER_ZERO transition
        stop(5, "Remote"),        # wrong reason and wrong state: no alert
    ])
    assert alerts == []
    assert det.state is Err1051State.ERR_FIRST_SEEN


def test_stuck_state_times_out_and_machine_restarts():
    det = Err1051Detector(CONN)
    det.consume(status(0, "Charging", ERR_1051))
    assert det.state is Err1051State.ERR_FIRST_SEEN

    # 120s later: past the 60s dwell limit, machine resets, then the incoming
    # err1051 starts a fresh sequence.
    det.consume(status(120, "Charging", ERR_1051))
    assert det.state is Err1051State.ERR_FIRST_SEEN
    assert det.first_seen_at == T0 + timedelta(seconds=120)


def test_slow_recovery_past_dwell_limit_still_emits_final_alert():
    """Recovery >60s: the Available event completes the sequence with the
    true recovery time instead of being swallowed by the stuck reset."""
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Charging", ERR_1051),
        meter(2, 0),
        status(4, "Finishing", ERR_1051),
        stop(5, "Other"),
        status(75, "Available", "NoError"),  # 70s after stop, past 60s dwell
    ])
    final = alerts[-1]
    assert final.stage == "final"
    assert final.recovered_after_seconds == 70.0
    assert final.classification == "technician-dispatch"
    assert det.state is Err1051State.IDLE


def test_unrecovered_stop_txn_times_out_with_dispatch_alert():
    """No recovery within the dwell limit: reset must emit a final
    technician-dispatch alert (recovery unobserved), not drop the sequence."""
    det = Err1051Detector(CONN)
    run_sequence(det, [
        status(0, "Charging", ERR_1051),
        meter(2, 0),
        status(4, "Finishing", ERR_1051),
        stop(5, "Other"),
    ])
    assert det.state is Err1051State.STOP_TXN
    # 90s later the connector is still not Available — any event trips the
    # timeout and surfaces the unrecovered fault.
    alert = det.consume(meter(95, 4200))
    assert alert is not None
    assert alert.stage == "final"
    assert alert.recovered_after_seconds is None
    assert alert.classification == "technician-dispatch"
    assert det.state is Err1051State.IDLE


def test_non_stop_txn_stuck_reset_still_emits_no_alert():
    det = Err1051Detector(CONN)
    det.consume(status(0, "Charging", ERR_1051))
    alert = det.consume(meter(120, 4200))  # stuck in ERR_FIRST_SEEN, no fault proven
    assert alert is None
    assert det.state is Err1051State.IDLE


def test_status_only_spine_completes_with_degraded_evidence():
    """Flag 25: real streams may carry only status rows. The machine
    completes on err1051@Charging -> err1051@Finishing -> Available and
    says so in the mechanism; recovery anchors on the second sighting
    (the flag-23 measurement anchor)."""
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Charging", ERR_1051),
        status(7, "Finishing", ERR_1051),   # no meter event in between
        status(17, "Available", "NoError"),  # 10s after second sighting
    ])
    assert len(alerts) == 1                  # no candidate without a stop event
    final = alerts[0]
    assert final.stage == "final"
    assert final.recovered_after_seconds == 10.0
    assert final.classification == "transient"
    assert "status-only" in final.mechanism
    assert det.state is Err1051State.IDLE


def test_full_sequence_keeps_full_evidence_mechanism():
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Charging", ERR_1051),
        meter(2, 0),
        status(4, "Finishing", ERR_1051),
        stop(5, "Other"),
        status(18, "Available", "NoError"),
    ])
    assert [a.stage for a in alerts] == ["candidate", "final"]
    assert "status-only" not in alerts[1].mechanism


def test_status_only_slow_recovery_past_dwell_still_finalizes():
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Charging", ERR_1051),
        status(7, "Finishing", ERR_1051),
        status(80, "Available", "NoError"),  # 73s later, past 60s dwell
    ])
    assert alerts[-1].recovered_after_seconds == 73.0
    assert alerts[-1].classification == "technician-dispatch"


def test_status_only_unrecovered_times_out_with_dispatch_alert():
    det = Err1051Detector(CONN)
    run_sequence(det, [
        status(0, "Charging", ERR_1051),
        status(7, "Finishing", ERR_1051),
    ])
    assert det.state is Err1051State.ERR_SECOND_SEEN
    alert = det.consume(status(90, "Charging", "NoError"))
    assert alert is not None and alert.stage == "final"
    assert alert.recovered_after_seconds is None
    assert alert.classification == "technician-dispatch"


def test_normal_traffic_stays_idle():
    det = Err1051Detector(CONN)
    alerts = run_sequence(det, [
        status(0, "Preparing", "NoError"),
        meter(10, 0),             # zero reading outside a fault sequence
        status(20, "Charging", "NoError"),
        stop(500, "Remote"),
        status(510, "Available", "NoError"),
    ])
    assert alerts == []
    assert det.state is Err1051State.IDLE
