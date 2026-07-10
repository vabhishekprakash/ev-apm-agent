"""Decision-support field enrichment (week_3_recommended_plan Task 2)."""

from decision_support import enrich


def alert(**kw) -> dict:
    base = {"detector_source": "err1051", "priority_tier": "P1",
            "classification": "technician-dispatch"}
    base.update(kw)
    return enrich(base)


def test_layer1_confidence_is_deterministic_100():
    assert alert()["confidence"] == 100
    assert alert(detector_source="ground_failure",
                 fault_category="GroundFailure")["confidence"] == 100


def test_layer2_confidence_scales_with_depth_below_threshold():
    at_threshold = alert(detector_source="layer2_drift", priority_tier="P3",
                         anomaly_score=-0.1187, layer2_threshold=-0.1187)
    assert at_threshold["confidence"] == 50
    deep = alert(detector_source="layer2_drift", priority_tier="P3",
                 anomaly_score=-0.40, layer2_threshold=-0.1187)
    assert deep["confidence"] == 95  # capped — unsupervised is never certainty
    mid = alert(detector_source="layer2_drift", priority_tier="P3",
                anomaly_score=-0.1937, layer2_threshold=-0.1187)  # depth 0.075
    assert 50 < mid["confidence"] < 95


def test_root_cause_lookup_and_default():
    assert "SLAC" in alert(detector_source="err1024")["likely_root_cause"]
    assert "earth-leakage" in alert(
        fault_category="GroundFailure")["likely_root_cause"]
    assert "inspect raw vendor code" in alert(
        detector_source="some_new_detector")["likely_root_cause"]


def test_recommended_actions_by_tier_and_drift():
    assert alert(priority_tier="P1")["recommended_action"] == "Dispatch technician"
    assert alert(priority_tier="P2")["recommended_action"] == \
        "Schedule inspection within 7 days"
    assert alert(detector_source="layer2_drift",
                 priority_tier="P3")["recommended_action"] == "Monitor next 3 sessions"
    assert alert(priority_tier="P3",
                 classification="transient")["recommended_action"] == "Log and review"


def test_impact_classes():
    assert alert(fault_category="GroundFailure")["impact_class"] == "Safety-flagged"
    # safety wins even when transient-classified
    assert alert(fault_category="GroundFailure",
                 classification="transient")["impact_class"] == "Safety-flagged"
    assert alert(classification="transient")["impact_class"] == "Non-revenue transient"
    assert alert(detector_source="telemetry_silence",
                 classification="investigate")["impact_class"] == "Revenue-impacting"
    assert alert(detector_source="layer2_drift", priority_tier="P3",
                 classification="drift-anomaly")["impact_class"] == "Non-revenue transient"
