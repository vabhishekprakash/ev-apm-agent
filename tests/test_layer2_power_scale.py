"""Unit tests for Day 5 power-curve and session-scale features.

Same fallback as the Day 4 temperature tests: the capped export carries only
meter_reading_wh, so sessions here are synthetic sampledValue-shaped dicts
mirroring a healthy CC-CV charge (flat CC plateau, tapering CV tail).
"""

from datetime import datetime, timedelta

import pytest

from layer2 import _power_curve_features, _session_scale_features

T0 = datetime(2026, 5, 15, 10, 0, 0)


def sample(offset_s: float, measurand: str, value: float) -> dict:
    return {
        "measurand": measurand,
        "location": "Outlet1",
        "value": value,
        "timestamp": T0 + timedelta(seconds=offset_s),
    }


def cc_cv_session() -> list:
    """60 kW CC plateau for 10 min, then CV taper to ~6 kW over 20 min."""
    samples = []
    for offset in range(0, 600, 60):  # CC: flat at peak
        samples.append(sample(offset, "Power.Active.Import", 60_000.0))
    for i, offset in enumerate(range(600, 1800, 60)):  # CV: linear-ish decay
        samples.append(sample(offset, "Power.Active.Import", 60_000.0 - i * 2_700.0))
    # Energy register climbs monotonically through the same window.
    for i, offset in enumerate(range(0, 1800, 300)):
        samples.append(sample(offset, "Energy.Active.Import.Register", 20_500_000 + i * 4_000))
    return samples


def transaction(duration_s: float = 1800.0) -> dict:
    return {
        "transaction_pk": 910001,
        "connector_pk": 4784325,
        "start_timestamp": T0,
        "stop_timestamp": T0 + timedelta(seconds=duration_s),
    }


def test_power_curve_features_on_healthy_cc_cv_session():
    features = _power_curve_features(cc_cv_session())
    assert features["peak_power"] == 60_000.0
    assert features["cc_cv_taper_slope"] < 0  # power falls through the CV tail
    assert 0.0 < features["cc_cv_peak_frac_final"] < 0.25  # tapered near-full


def test_power_curve_features_none_without_power_samples():
    energy_only = [sample(0, "Energy.Active.Import.Register", 100.0)]
    assert _power_curve_features(energy_only) == {
        "peak_power": None,
        "cc_cv_taper_slope": None,
        "cc_cv_peak_frac_final": None,
    }


def test_taper_slope_none_with_single_post_peak_sample():
    features = _power_curve_features([sample(0, "Power.Active.Import", 50_000.0)])
    assert features["peak_power"] == 50_000.0
    assert features["cc_cv_taper_slope"] is None
    assert features["cc_cv_peak_frac_final"] == 1.0


def test_session_scale_features():
    features = _session_scale_features(transaction(1800.0), cc_cv_session())
    assert features["duration_sec"] == 1800.0
    assert features["energy_wh"] == 20_000  # 5 register steps of 4000
    assert features["energy_per_second"] == pytest.approx(20_000 / 1800.0)


def test_session_scale_handles_open_session_and_missing_energy():
    open_txn = {"start_timestamp": T0, "stop_timestamp": None}
    features = _session_scale_features(open_txn, [])
    assert features == {
        "duration_sec": None,
        "energy_wh": None,
        "energy_per_second": None,
    }


def test_no_infinity_from_zero_duration():
    features = _session_scale_features(transaction(0.0), cc_cv_session())
    assert features["duration_sec"] == 0.0
    assert features["energy_per_second"] is None
