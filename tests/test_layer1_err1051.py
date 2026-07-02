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
