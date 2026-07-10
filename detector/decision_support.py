"""Decision-support enrichment (week_3_recommended_plan, Task 2).

Every alert payload gains four fields before it reaches a sink:

- confidence          — Layer 1 detections are deterministic (100); Layer 2
                        drift confidence is the normalized depth below the
                        IsolationForest threshold (50 at the threshold,
                        capped at 95 — an unsupervised score is never
                        presented as certainty).
- likely_root_cause   — static lookup by fault category.
- recommended_action  — static lookup by tier + classification.
- impact_class        — Revenue-impacting / Safety-flagged /
                        Non-revenue transient.

All lookups are rule tables, not models — deliberately: they must be
explainable to an operator in one sentence.
"""

# Full-scale drift (score threshold−0.15 and below) reads as max confidence.
LAYER2_CONFIDENCE_SPAN = 0.15
LAYER2_CONFIDENCE_FLOOR = 50
LAYER2_CONFIDENCE_CAP = 95

ROOT_CAUSES = {
    "err1051": "internal socket-controller initialization failure",
    "err1024": "SLAC handshake timeout — vehicle/charger pre-charge communication",
    "telemetry_silence": "connector controller hang or backhaul communication dropout",
    "WeakSignal": "cellular modem signal degradation (antenna, SIM, or carrier)",
    "GroundFailure": "earth-leakage / protective-earth wiring fault",
    "UnderVoltage": "supply undervoltage — grid sag or site wiring",
    "OverVoltage": "supply overvoltage — grid surge or site wiring",
    "layer2_drift": "session-profile deviation from this connector's learned baseline",
}
DEFAULT_ROOT_CAUSE = "uncategorized fault — inspect raw vendor code"

# recommended_action by tier, refined by classification where it matters.
ACTIONS_BY_TIER = {
    "P1": "Dispatch technician",
    "P2": "Schedule inspection within 7 days",
    "P3": "Log and review",
}
DRIFT_ACTION = "Monitor next 3 sessions"

SAFETY_CATEGORIES = {"GroundFailure"}
# Faults that take a connector out of revenue service until resolved.
REVENUE_CATEGORIES = {"err1051", "err1024", "telemetry_silence",
                      "UnderVoltage", "OverVoltage"}


def _category(alert: dict) -> str:
    return alert.get("fault_category") or alert.get("detector_source") or ""


def _confidence(alert: dict) -> int:
    if alert.get("detector_source") != "layer2_drift":
        return 100  # deterministic Layer 1 signature
    score = alert.get("anomaly_score")
    threshold = alert.get("layer2_threshold")
    if score is None or threshold is None:
        return LAYER2_CONFIDENCE_FLOOR
    depth = max(0.0, threshold - score) / LAYER2_CONFIDENCE_SPAN
    return min(LAYER2_CONFIDENCE_CAP,
               round(LAYER2_CONFIDENCE_FLOOR
                     + (LAYER2_CONFIDENCE_CAP - LAYER2_CONFIDENCE_FLOOR)
                     * min(1.0, depth)))


def _impact_class(alert: dict, category: str) -> str:
    if category in SAFETY_CATEGORIES:
        return "Safety-flagged"
    if alert.get("classification") == "transient":
        return "Non-revenue transient"
    if category in REVENUE_CATEGORIES:
        return "Revenue-impacting"
    return "Non-revenue transient" if alert.get("priority_tier") == "P3" \
        else "Revenue-impacting"


def _recommended_action(alert: dict, category: str) -> str:
    if category == "layer2_drift" and alert.get("priority_tier") == "P3":
        return DRIFT_ACTION
    return ACTIONS_BY_TIER.get(alert.get("priority_tier"), ACTIONS_BY_TIER["P2"])


def enrich(alert: dict) -> dict:
    """Add the four decision-support fields. Runs after the prioritizer (it
    reads priority_tier/classification). Mutates and returns the same dict."""
    category = _category(alert)
    alert["confidence"] = _confidence(alert)
    alert["likely_root_cause"] = ROOT_CAUSES.get(category, DEFAULT_ROOT_CAUSE)
    alert["recommended_action"] = _recommended_action(alert, category)
    alert["impact_class"] = _impact_class(alert, category)
    return alert
