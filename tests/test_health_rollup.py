"""Hard gate B4: health-state transitions on synthetic drift sequences."""

from health_rollup import AT_RISK_FLAGGED_SESSIONS, STATES, health_state


def test_healthy_baseline():
    assert health_state() == "Healthy"


def test_degradation_transition_sequence():
    """A connector drifting session by session walks the ladder up."""
    states = [health_state(flagged_sessions=n) for n in range(0, 5)]
    assert states[0] == "Healthy"
    assert states[1] == "Degrading"          # first drift flag
    assert states[2] == "Degrading"
    assert states[AT_RISK_FLAGGED_SESSIONS] == "At-risk"   # >=3 flags
    assert states[4] == "At-risk"


def test_p2_recommendation_is_at_risk_even_without_drift():
    assert health_state(p2_alerts=1) == "At-risk"


def test_unresolved_p1_dominates_everything():
    assert health_state(p1_alerts=1) == "Faulted"
    assert health_state(p1_alerts=1, p2_alerts=5, drift_alerts=9,
                        flagged_sessions=9) == "Faulted"


def test_drift_alert_alone_is_degrading():
    assert health_state(drift_alerts=1) == "Degrading"


def test_all_states_reachable_and_named():
    reached = {
        health_state(),
        health_state(drift_alerts=1),
        health_state(p2_alerts=1),
        health_state(p1_alerts=1),
    }
    assert reached == set(STATES)
