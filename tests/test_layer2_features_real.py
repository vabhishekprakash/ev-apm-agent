"""Layer 2 feature validation on REAL fault-evidence windows.

Runs against data/raw/master_training_set.csv (delivered 2026-07-04: 46 fault
events x 6 measurands — audit flags 10/11). Raw exports are gitignored, so
these tests skip cleanly on checkouts without the data drop.

Closes the SPEC Day 4 acceptance gap for power/energy features ("sane numbers
on >=3 real sessions"). Temperature features stay synthetic-only: the real
export's Temperature field is dead (all 0.0 — flag 11), and no sensor-location
column exists yet.
"""

import csv
from datetime import datetime
from pathlib import Path

import pytest

from layer2 import _power_curve_features, _session_scale_features

DATA = Path(__file__).resolve().parent.parent / "data" / "raw" / "master_training_set.csv"

pytestmark = pytest.mark.skipif(
    not DATA.exists(), reason="raw fault-evidence export not present (gitignored)"
)


def fault_windows() -> dict[int, list]:
    """fault_ref -> list of sampledValue-shaped dicts, as the features expect."""
    windows: dict[int, list] = {}
    with DATA.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            windows.setdefault(int(row["fault_ref"]), []).append({
                "measurand": row["measurand"],
                "location": "Outlet1",  # no location column yet (flag 11)
                "value": row["value"],
                "timestamp": datetime.strptime(row["value_timestamp"], "%d-%m-%Y %H:%M"),
            })
    return windows


def test_power_features_sane_on_all_real_fault_windows():
    windows = fault_windows()
    assert len(windows) >= 3  # SPEC acceptance floor
    computable = 0
    for ref, samples in windows.items():
        features = _power_curve_features(samples)
        peak = features["peak_power"]
        assert peak is not None, f"fault {ref}: no power samples"
        # DC fast-charge power in kW (unit column says kW): 0..350 is sane
        assert 0.0 <= peak <= 350.0, f"fault {ref}: peak_power {peak}"
        frac = features["cc_cv_peak_frac_final"]
        if frac is not None:
            assert 0.0 <= frac <= 1.0, f"fault {ref}: peak_frac {frac}"
        if features["cc_cv_taper_slope"] is not None:
            computable += 1
    assert computable >= 3  # slope needs >=2 post-peak samples


def test_energy_scale_sane_on_real_fault_windows():
    windows = fault_windows()
    sane = 0
    for ref, samples in windows.items():
        ts = [s["timestamp"] for s in samples]
        txn = {"start_timestamp": min(ts), "stop_timestamp": max(ts)}
        features = _session_scale_features(txn, samples)
        if features["energy_wh"] is None:
            continue
        # register is monotonic: last - first must not be negative
        assert features["energy_wh"] >= 0.0, f"fault {ref}: energy {features['energy_wh']}"
        sane += 1
    assert sane >= 3


def test_real_export_confirms_voltage_stays_nominal_during_faults():
    """Audit flag 10: the SPEC guard (V AND A AND P == 0) never fires on real
    evidence — voltage stays energized while current/power collapse. This test
    pins that fact so a future guard change is driven by data, not assumption."""
    windows = fault_windows()
    voltages = [
        float(s["value"])
        for samples in windows.values()
        for s in samples
        if s["measurand"] == "Voltage"
    ]
    assert voltages and min(voltages) > 100.0  # never anywhere near zero
