"""Unit tests for AlertPrioritizer (Week 2 Day 1 + Day 4 rules)."""

from datetime import datetime, timedelta

from prioritizer import AlertPrioritizer

T0 = datetime(2026, 5, 15, 10, 0, 0)
CONN = 2009529


def at(offset_s: float) -> str:
    return (T0 + timedelta(seconds=offset_s)).isoformat()


def alert(source: str, offset_s: float = 0, connector: int = CONN, **extra) -> dict:
    return {"detector_source": source, "connector_pk": connector,
            "fired_at": at(offset_s), "stage": "final", **extra}


def test_transient_err1051_downgrades_to_p3():
    p = AlertPrioritizer()
    out = p.prioritize(alert("err1051", recovery_seconds=13.0))
    assert out["priority_tier"] == "P3"
    assert "self-recovered in 13s" in out["deciding_signal"]


def test_slow_or_unrecovered_err1051_is_p1():
    p = AlertPrioritizer()
    slow = p.prioritize(alert("err1051", recovery_seconds=70.0))
    assert slow["priority_tier"] == "P1"
    unrecovered = p.prioritize(alert("err1051", offset_s=99999,
                                     connector=CONN + 1, recovery_seconds=None))
    assert unrecovered["priority_tier"] == "P1"
    assert "no recovery observed" in unrecovered["deciding_signal"]


def test_err1051_candidate_is_p2():
    p = AlertPrioritizer()
    out = p.prioritize(alert("err1051", stage="candidate", recovery_seconds=None))
    assert out["priority_tier"] == "P2"


def test_err1024_default_p2_and_silence_p1():
    p = AlertPrioritizer()
    assert p.prioritize(alert("err1024"))["priority_tier"] == "P2"
    out = p.prioritize(alert("telemetry_silence", connector=CONN + 2,
                             silence_seconds=120.0))
    assert out["priority_tier"] == "P1"
    assert "dark for 120s" in out["deciding_signal"]


def test_single_drift_p3_three_consecutive_escalate_p2():
    p = AlertPrioritizer()
    first = p.prioritize(alert("layer2_drift", 0, anomaly_score=-0.15))
    assert first["priority_tier"] == "P3"
    second = p.prioritize(alert("layer2_drift", 3600, anomaly_score=-0.16))
    assert second["priority_tier"] == "P3"
    third = p.prioritize(alert("layer2_drift", 7200, anomaly_score=-0.2))
    assert third["priority_tier"] == "P2"
    assert "3 consecutive drift sessions" in third["deciding_signal"]


def test_clean_session_breaks_drift_streak():
    p = AlertPrioritizer()
    p.prioritize(alert("layer2_drift", 0))
    p.prioritize(alert("layer2_drift", 3600))
    p.record_clean_session(CONN)
    third = p.prioritize(alert("layer2_drift", 7200))
    assert third["priority_tier"] == "P3"  # streak restarted at 1


def test_repeat_offender_upgrades_one_tier_within_24h():
    p = AlertPrioritizer()
    p.prioritize(alert("telemetry_silence", 0, silence_seconds=100.0))  # P1
    drift = p.prioritize(alert("layer2_drift", 3600))
    assert drift["priority_tier"] == "P2"  # P3 upgraded once
    assert "repeat offender" in drift["deciding_signal"]
    # 25h later the window has passed
    late = p.prioritize(alert("layer2_drift", 25 * 3600))
    assert late["priority_tier"] == "P3"


def test_day4_category_rules_ground_voltage_weaksignal():
    p = AlertPrioritizer()
    ground = p.prioritize(alert("ground_failure", fault_category="GroundFailure"))
    assert ground["priority_tier"] == "P1"

    v1 = p.prioritize(alert("voltage", 0, connector=CONN + 5,
                            fault_category="UnderVoltage"))
    assert v1["priority_tier"] == "P2"
    v2 = p.prioritize(alert("voltage", 3600, connector=CONN + 5,
                            fault_category="OverVoltage"))
    assert v2["priority_tier"] == "P1"  # repeated within 24h

    weak = p.prioritize(alert("weak_signal", 0, connector=CONN + 6,
                              fault_category="WeakSignal"))
    assert weak["priority_tier"] == "P3"
    for i in range(1, 6):
        burst = p.prioritize(alert("weak_signal", i * 30, connector=CONN + 6,
                                   fault_category="WeakSignal"))
    assert burst["priority_tier"] == "P2"
    assert "burst" in burst["deciding_signal"]


def test_unknown_alert_type_gets_p2_fallback():
    p = AlertPrioritizer()
    out = p.prioritize(alert("some_future_detector"))
    assert out["priority_tier"] == "P2"
    assert out["priority_score"] == 50
