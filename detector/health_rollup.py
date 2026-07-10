"""Per-connector health rollup — canonical rule table (hard gate B4).

Health is derived from recent Layer 2 drift trajectory plus unresolved
Layer 1 recommendations. Rule-based, not learned; the UI's client-side chips
mirror exactly this table, and this module is the source of truth the tests
assert against.

    Faulted    — any unresolved P1 recommendation
    At-risk    — any P2 recommendation, or >=3 drift-flagged sessions
    Degrading  — any drift flag (alert or flagged session)
    Healthy    — none of the above
"""

AT_RISK_FLAGGED_SESSIONS = 3

STATES = ("Healthy", "Degrading", "At-risk", "Faulted")


def health_state(p1_alerts: int = 0, p2_alerts: int = 0,
                 drift_alerts: int = 0, flagged_sessions: int = 0) -> str:
    """Health label for one connector from its recent activity counts."""
    if p1_alerts > 0:
        return "Faulted"
    if p2_alerts > 0 or flagged_sessions >= AT_RISK_FLAGGED_SESSIONS:
        return "At-risk"
    if drift_alerts > 0 or flagged_sessions > 0:
        return "Degrading"
    return "Healthy"
