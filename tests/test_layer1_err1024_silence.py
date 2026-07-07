"""Unit tests for the Day 5 detectors: err1024 point-event and telemetry silence."""

from datetime import datetime, timedelta

from layer1 import (
    ERR_1024,
    Err1024Detector,
    TelemetrySilenceDetector,
)
from ocpp_messages import MeterValues, StartTransaction, StatusNotification, StopTransaction

T0 = datetime(2026, 5, 15, 10, 0, 0)
CONN = 5802030


def at(offset_s: float) -> datetime:
    return T0 + timedelta(seconds=offset_s)


def status(offset_s: float, status: str, error_code: str) -> StatusNotification:
    return StatusNotification(
        connector_pk=CONN, status=status, error_code=error_code, timestamp=at(offset_s)
    )


def meter(offset_s: float, wh: float = 4200) -> MeterValues:
    return MeterValues(
        transaction_pk=910002, connector_pk=CONN, meter_reading_wh=wh, timestamp=at(offset_s)
    )


def start(offset_s: float) -> StartTransaction:
    return StartTransaction(
        transaction_pk=910002, connector_pk=CONN, start_timestamp=at(offset_s)
    )


def stop(offset_s: float, reason: str = "Remote") -> StopTransaction:
    return StopTransaction(
        transaction_pk=910002, connector_pk=CONN, stop_timestamp=at(offset_s),
        stop_reason=reason,
    )


# -- err1024 ------------------------------------------------------------------

def test_err1024_fires_on_sight_with_mechanism_and_classification():
    det = Err1024Detector(CONN)
    alert = det.consume(status(0, "Preparing", ERR_1024))
    assert alert is not None
    assert alert.to_dict() == {
        "detector_source": "err1024",
        "connector_pk": CONN,
        "fired_at": at(0).isoformat(),
        "stage": "final",
        "fault_code": "err1024",
        "fault_category": None,
        "mechanism": "SLAC handshake timeout",
        "recovery_seconds": None,
        "classification": "technician-dispatch-likely",
    }


def test_err1024_ignores_other_codes_and_event_types():
    det = Err1024Detector(CONN)
    assert det.consume(status(0, "Charging", "NoError")) is None
    assert det.consume(status(1, "Charging", "system-err1051")) is None
    assert det.consume(meter(2)) is None
    assert det.consume(start(3)) is None


def test_err_codes_match_in_vendor_column_real_schema():
    """Audit flag 23: real streams carry system-err* in vendor_error_code
    with error_code=OtherError; both detectors must match either column."""
    from layer1 import ERR_1051, Err1051Detector, Err1051State
    det1024 = Err1024Detector(CONN)
    real_row = StatusNotification(connector_pk=CONN, status="Preparing",
                                  error_code="OtherError",
                                  vendor_error_code="system-err1024",
                                  timestamp=at(0))
    alert = det1024.consume(real_row)
    assert alert is not None and alert.fault_code == "err1024"

    det1051 = Err1051Detector(CONN)
    det1051.consume(StatusNotification(connector_pk=CONN, status="Charging",
                                       error_code="OtherError",
                                       vendor_error_code=ERR_1051,
                                       timestamp=at(10)))
    assert det1051.state is Err1051State.ERR_FIRST_SEEN


def test_err1024_fires_on_every_sighting():
    # Confirmed final: the crash-signature reply carries no retry/recovery
    # sequencing, so every sighting fires (prioritizer handles escalation).
    det = Err1024Detector(CONN)
    assert det.consume(status(0, "Preparing", ERR_1024)) is not None
    assert det.consume(status(5, "Preparing", ERR_1024)) is not None


# -- telemetry silence ---------------------------------------------------------

def test_silence_fires_once_past_threshold_during_active_session():
    det = TelemetrySilenceDetector(CONN, threshold_seconds=90.0)
    det.consume(start(0))
    det.consume(meter(30))
    assert det.on_tick(at(60)) is None            # 30s quiet — fine
    assert det.on_tick(at(120)) is None           # 90s quiet — at threshold, not past
    alert = det.on_tick(at(121))                  # 91s quiet — fires
    assert alert is not None
    assert alert.detector == "telemetry_silence"
    assert alert.silence_seconds == 91.0
    assert alert.classification == "investigate"
    assert det.on_tick(at(200)) is None           # one alert per silent stretch


def test_silence_rearms_after_telemetry_resumes():
    det = TelemetrySilenceDetector(CONN, threshold_seconds=90.0)
    det.consume(start(0))
    assert det.on_tick(at(100)) is not None       # quiet since session open
    det.consume(meter(110))                       # telemetry resumes — re-arm
    assert det.on_tick(at(150)) is None
    assert det.on_tick(at(210)) is not None       # quiet again for 100s


def test_silence_never_fires_without_open_session():
    det = TelemetrySilenceDetector(CONN, threshold_seconds=90.0)
    assert det.on_tick(at(1000)) is None
    det.consume(start(1000))
    det.consume(stop(1100))
    assert det.on_tick(at(9999)) is None          # closed session: no silence


def test_silence_resets_on_stop_transaction():
    det = TelemetrySilenceDetector(CONN, threshold_seconds=90.0)
    det.consume(start(0))
    det.consume(meter(30))
    det.consume(stop(60))
    assert det.on_tick(at(500)) is None
