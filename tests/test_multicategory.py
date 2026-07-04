"""Week 2 Day 4: category point-detectors + prioritizer escalations."""

from datetime import datetime, timedelta

from layer1 import make_category_detectors
from ocpp_messages import StatusNotification
from prioritizer import AlertPrioritizer

T0 = datetime(2026, 5, 16, 9, 0, 0)
CONN = 1744735


def status(offset_s: float, error_code: str, connector: int = CONN) -> StatusNotification:
    return StatusNotification(connector_pk=connector, status="Faulted",
                              error_code=error_code,
                              timestamp=T0 + timedelta(seconds=offset_s))


def run(canonical: str, offset_s: float = 0, connector: int = CONN):
    alerts = []
    for det in make_category_detectors(connector):
        alert = det.consume(status(offset_s, canonical, connector), canonical)
        if alert is not None:
            alerts.append(alert)
    return alerts


def test_each_category_fires_exactly_one_detector():
    for canonical, expected_source in [
        ("WeakSignal", "weak_signal"),
        ("GroundFailure", "ground_failure"),
        ("UnderVoltage", "voltage"),
        ("OverVoltage", "voltage"),
    ]:
        alerts = run(canonical)
        assert len(alerts) == 1
        assert alerts[0].detector == expected_source
        assert alerts[0].fault_category == canonical
        assert alerts[0].to_dict()["fault_category"] == canonical


def test_unmatched_category_and_noerror_fire_nothing():
    assert run("HighTemperature") == []  # no dedicated detector yet
    for det in make_category_detectors(CONN):
        assert det.consume(status(0, "NoError"), None) is None


def test_prioritizer_end_to_end_tiers_for_new_categories():
    """One connector per scenario — the repeat-offender rule is cross-category
    by design and would otherwise promote everything after the first P1."""
    p = AlertPrioritizer()

    ground = run("GroundFailure", connector=CONN + 1)[0].to_dict()
    assert p.prioritize(ground)["priority_tier"] == "P1"

    first_uv = p.prioritize(run("UnderVoltage", 0, connector=CONN + 2)[0].to_dict())
    assert first_uv["priority_tier"] == "P2"
    second_ov = p.prioritize(run("OverVoltage", 3600, connector=CONN + 2)[0].to_dict())
    assert second_ov["priority_tier"] == "P1"  # repeat within 24h

    # weak-signal burst: 6 events in 5 minutes escalate to P2
    tiers = [p.prioritize(run("WeakSignal", i * 30, connector=CONN + 3)[0].to_dict())["priority_tier"]
             for i in range(6)]
    assert tiers[0] == "P3" and tiers[-1] == "P2"


def test_repeat_offender_applies_across_categories():
    """A P1 on the connector upgrades any later alert on the same connector
    within 24h — cross-category by design."""
    p = AlertPrioritizer()
    p.prioritize(run("GroundFailure")[0].to_dict())          # P1 recorded
    later = p.prioritize(run("UnderVoltage", 3600)[0].to_dict())
    assert later["priority_tier"] == "P1"
    assert "repeat offender" in later["deciding_signal"]
