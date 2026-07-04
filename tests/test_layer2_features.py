"""Unit tests for Day 4 temperature features (SPEC Day 4, Akhil Tasks 1-3).

Real exports lack the measurand/location columns until the Workbench
re-export lands (audit flag 6), so per the SPEC Day 4 Joint fallback these
sessions are synthetic, shaped like OCPP 1.6 sampledValue rows and
calibrated to the documented PRABHAEV004N behaviour (~10°C steady outlet
asymmetry on normal sessions).
"""

from datetime import datetime, timedelta

from layer2 import _peak_temp_features, _temp_asymmetry_features

T0 = datetime(2026, 5, 15, 10, 0, 0)


def temp(offset_s: float, location: str, value: float) -> dict:
    return {
        "measurand": "Temperature",
        "location": location,
        "value": value,
        "timestamp": T0 + timedelta(seconds=offset_s),
    }


def energy(offset_s: float, wh: float) -> dict:
    return {
        "measurand": "Energy.Active.Import.Register",
        "location": "Outlet1",
        "value": wh,
        "timestamp": T0 + timedelta(seconds=offset_s),
    }


def dual_outlet_session() -> list:
    """Normal PRABHAEV004N-shaped session: body warms to mid-40s, outlet 1
    runs ~10°C hotter than outlet 2 throughout, plus non-temperature noise."""
    samples = []
    for i, offset in enumerate(range(0, 1800, 300)):  # 30 min, 5 min cadence
        samples.append(temp(offset, "Body", 34.0 + i * 1.8))
        samples.append(temp(offset, "Outlet1", 41.0 + i * 5.0))
        samples.append(temp(offset, "Outlet2", 31.5 + i * 4.9))
        samples.append(energy(offset, 20_500_000 + i * 6_000))
    return samples


def single_outlet_session() -> list:
    return [
        temp(0, "Body", 33.0),
        temp(300, "Outlet1", 48.0),
        temp(600, "Outlet1", 55.5),
        temp(600, "Body", 39.0),
    ]


def test_peak_temps_in_sane_ranges_on_dual_outlet_session():
    peaks = _peak_temp_features(dual_outlet_session())
    assert 20.0 <= peaks["peak_temp_body"] <= 60.0
    assert 20.0 <= peaks["peak_temp_c1"] <= 90.0
    assert 20.0 <= peaks["peak_temp_c2"] <= 90.0
    # Outlet sensors sit on the DC path and run hotter than the cabinet.
    assert peaks["peak_temp_c1"] > peaks["peak_temp_body"]


def test_peak_temps_none_for_missing_sensors():
    peaks = _peak_temp_features(single_outlet_session())
    assert peaks["peak_temp_body"] == 39.0
    assert peaks["peak_temp_c1"] == 55.5
    assert peaks["peak_temp_c2"] is None


def test_peak_temps_all_none_without_temperature_measurand():
    peaks = _peak_temp_features([energy(0, 100.0), energy(300, 600.0)])
    assert peaks == {
        "peak_temp_body": None,
        "peak_temp_c1": None,
        "peak_temp_c2": None,
    }


def test_asymmetry_matches_10c_calibration_target():
    features = _temp_asymmetry_features(dual_outlet_session())
    assert 0.0 <= features["temp_asymmetry_max"] <= 30.0
    # ~10°C observed on normal PRABHAEV004N sessions
    assert 8.0 <= features["temp_asymmetry_mean"] <= 12.0
    assert features["temp_asymmetry_final"] <= features["temp_asymmetry_max"]


def test_asymmetry_none_for_single_outlet_session():
    features = _temp_asymmetry_features(single_outlet_session())
    assert features == {
        "temp_asymmetry_max": None,
        "temp_asymmetry_mean": None,
        "temp_asymmetry_final": None,
    }


def test_rows_with_missing_or_bad_timestamps_are_skipped_not_fatal():
    """Review finding: a sample without a timestamp (or with garbage) must be
    skipped per the parsing contract, not crash the series sort."""
    session = [
        temp(0, "Outlet1", 40.0),
        {"measurand": "Temperature", "location": "Outlet1", "value": 99.0},  # no ts
        {"measurand": "Temperature", "location": "Outlet1", "value": 98.0,
         "timestamp": "not-a-date"},
        {"measurand": "Temperature", "location": "Outlet2", "value": 31.0,
         "timestamp": T0.isoformat()},  # ISO string per module contract
    ]
    peaks = _peak_temp_features(session)
    assert peaks["peak_temp_c1"] == 40.0  # bad rows skipped, not counted
    assert peaks["peak_temp_c2"] == 31.0  # ISO string coerced


def test_string_values_and_location_aliases_are_normalized():
    session = [
        {"measurand": "Temperature", "location": "outlet 1", "value": "44.5",
         "timestamp": T0},
        {"measurand": "Temperature", "location": "Connector2", "value": "35.0",
         "timestamp": T0},
        {"measurand": "Temperature", "location": "charger-body", "value": "31.0",
         "timestamp": T0},
        {"measurand": "Temperature", "location": "Inlet", "value": "99.0",
         "timestamp": T0},  # unknown location: skipped
    ]
    peaks = _peak_temp_features(session)
    assert peaks == {
        "peak_temp_body": 31.0,
        "peak_temp_c1": 44.5,
        "peak_temp_c2": 35.0,
    }
    features = _temp_asymmetry_features(session)
    assert features["temp_asymmetry_max"] == 9.5
