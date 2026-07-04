"""Unit tests for the Layer2Anomaly inference wrapper (SPEC Day 6, Akhil Task 2)."""

import pickle

import pytest
from sklearn.ensemble import IsolationForest

from layer2 import Layer2Anomaly

STATION = "d4416bd8" + "0" * 56
FEATURES = ["duration_sec", "start_hour"]


@pytest.fixture
def models_dir(tmp_path):
    """Tiny artifact set: one per-connector model, one pooled model, index."""
    normal = [[1800.0 + i * 10, 10.0 + (i % 8)] for i in range(120)]
    per_connector = IsolationForest(contamination="auto", random_state=42).fit(normal)
    pooled = IsolationForest(contamination="auto", random_state=42).fit(normal)
    with (tmp_path / "isoforest_x_1.pkl").open("wb") as f:
        pickle.dump(per_connector, f)
    with (tmp_path / "isoforest_pooled_tucker.pkl").open("wb") as f:
        pickle.dump(pooled, f)
    index = {
        "features": FEATURES,
        "threshold_default": -0.1,
        "connector_models": {
            4784325: {"file": "isoforest_x_1.pkl",
                      "hashed_charge_box_id": STATION, "physical_plug_id": 1},
        },
        "pooled_models": {"tucker": {"file": "isoforest_pooled_tucker.pkl"}},
        "connectors": {
            4784325: {"hashed_charge_box_id": STATION, "physical_plug_id": 1,
                      "vendor_family": "tucker"},
            5802030: {"hashed_charge_box_id": STATION, "physical_plug_id": 2,
                      "vendor_family": "tucker"},
            999: {"hashed_charge_box_id": "f" * 64, "physical_plug_id": 1,
                  "vendor_family": "unpooled_family"},
        },
    }
    with (tmp_path / "isoforest_index.pkl").open("wb") as f:
        pickle.dump(index, f)
    return tmp_path


def test_normal_session_scores_above_threshold(models_dir):
    layer2 = Layer2Anomaly(models_dir, threshold=-0.1)
    result = layer2.score({"duration_sec": 2100.0, "start_hour": 12.0}, STATION, 1)
    assert result is not None
    score, flagged = result
    assert score > -0.1 and not flagged


def test_extreme_session_is_flagged(models_dir):
    layer2 = Layer2Anomaly(models_dir, threshold=-0.1)
    score, flagged = layer2.score(
        {"duration_sec": 900000.0, "start_hour": 3.0}, STATION, 1)
    assert score < -0.1 and flagged


def test_pooled_fallback_serves_connector_without_own_model(models_dir):
    layer2 = Layer2Anomaly(models_dir, threshold=-0.1)
    # plug 2 has no per-connector model; vendor family "tucker" pools it
    result = layer2.score({"duration_sec": 2000.0, "start_hour": 11.0}, STATION, 2)
    assert result is not None


def test_none_for_unknown_station_or_unpooled_family(models_dir):
    layer2 = Layer2Anomaly(models_dir, threshold=-0.1)
    assert layer2.score({"duration_sec": 100.0, "start_hour": 1.0}, "e" * 64, 1) is None
    assert layer2.score_by_connector_pk(
        {"duration_sec": 100.0, "start_hour": 1.0}, 999) is None


def test_unpooled_family_routes_to_global_pool_when_present(models_dir):
    import pickle as _pickle
    with (models_dir / "isoforest_index.pkl").open("rb") as f:
        index = _pickle.load(f)
    index["pooled_models"]["_global"] = {"file": "isoforest_pooled_tucker.pkl"}
    with (models_dir / "isoforest_index.pkl").open("wb") as f:
        _pickle.dump(index, f)
    layer2 = Layer2Anomaly(models_dir, threshold=-0.1)
    # connector 999's family has no cohort model; _global now serves it
    assert layer2.score_by_connector_pk(
        {"duration_sec": 2000.0, "start_hour": 11.0}, 999) is not None


def test_none_for_missing_feature(models_dir):
    layer2 = Layer2Anomaly(models_dir, threshold=-0.1)
    assert layer2.score({"duration_sec": 100.0}, STATION, 1) is None


def test_threshold_env_override(models_dir, monkeypatch):
    monkeypatch.setenv("LAYER2_THRESHOLD", "-0.25")
    assert Layer2Anomaly(models_dir).threshold == -0.25


def test_unavailable_without_artifacts(tmp_path):
    layer2 = Layer2Anomaly(tmp_path / "empty")
    assert not layer2.available
    assert layer2.score({"duration_sec": 100.0, "start_hour": 1.0}, STATION, 1) is None
