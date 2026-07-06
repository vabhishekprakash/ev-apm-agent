"""Layer 2 — unsupervised per-connector drift detection.

Owner: Akhil. Day 4: temperature features (_peak_temp_features,
_temp_asymmetry_features). Feature logic and Isolation Forest training land
Week 1-2 (see docs/SPEC.md §4.1, §8). Tier cutoffs live in docs/layer2_scope.md.

Input shape note: the current capped export carries only meter_reading_wh —
the measurand/location columns land with the Workbench re-export (audit
flag 6). Per SPEC Day 4 Joint fallback, these functions are scaffolded
against OCPP 1.6 sampledValue-shaped dicts:
    {"measurand": "Temperature", "location": "Outlet1",
     "value": 62.5, "timestamp": <datetime|ISO str>}
so they slot in unchanged once the re-export arrives.
"""

import os
import pickle
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ocpp_messages import MeterValues, StartTransaction, StopTransaction

# SPEC Day 6 default; the deployed value is calibrated on held-out normals
# (see notebooks/03_isoforest_training.ipynb) and passed via env.
DEFAULT_LAYER2_THRESHOLD = -0.1

TEMPERATURE_MEASURAND = "Temperature"
POWER_MEASURAND = "Power.Active.Import"
ENERGY_MEASURAND = "Energy.Active.Import.Register"

# Sensor-location strings vary across vendor firmware (12 vendor strings in
# inventory, audit flag 8); normalize the plausible spellings to three slots.
_LOCATION_ALIASES = {
    "body": "body",
    "chargerbody": "body",
    "cabinet": "body",
    "outlet1": "outlet_1",
    "outlet_1": "outlet_1",
    "connector1": "outlet_1",
    "c1": "outlet_1",
    "outlet2": "outlet_2",
    "outlet_2": "outlet_2",
    "connector2": "outlet_2",
    "c2": "outlet_2",
}


def _normalize_location(raw: object) -> str | None:
    if raw is None:
        return None
    key = str(raw).strip().lower().replace(" ", "").replace("-", "")
    return _LOCATION_ALIASES.get(key)


def _sample_ts(sample: dict) -> datetime | None:
    """Timestamp of one sampledValue row, coerced per the module contract
    (datetime or ISO string); None when missing or unparseable — such rows
    are skipped rather than crashing the sort (review finding)."""
    raw = sample.get("timestamp")
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _temperature_series(session_meter_values: list) -> dict[str, list[tuple]]:
    """Group Temperature samples by normalized location, sorted by timestamp.

    Location-grouping over _measurand_series so the sample-parsing rules
    (value coercion, timestamp validation, skip-on-bad-row) live in exactly
    one place. Returns {"body"|"outlet_1"|"outlet_2": [(ts, value), ...]};
    locations with no samples are absent.
    """
    series: dict[str, list[tuple]] = {}
    for location_key in set(
        _normalize_location(s.get("location")) for s in session_meter_values
    ) - {None}:
        rows = [s for s in session_meter_values
                if _normalize_location(s.get("location")) == location_key]
        samples = _measurand_series(rows, TEMPERATURE_MEASURAND)
        if samples:
            series[location_key] = samples
    return series


def _peak_temp_features(session_meter_values: list) -> dict:
    """Max temperature per sensor location over one session (SPEC Day 4 Task 1).

    Returns peak_temp_body, peak_temp_c1, peak_temp_c2 — None for sensors
    not present in the session.
    """
    series = _temperature_series(session_meter_values)

    def peak(location: str) -> float | None:
        samples = series.get(location)
        return max(value for _, value in samples) if samples else None

    return {
        "peak_temp_body": peak("body"),
        "peak_temp_c1": peak("outlet_1"),
        "peak_temp_c2": peak("outlet_2"),
    }


def _temp_asymmetry_features(session_meter_values: list) -> dict:
    """Outlet temperature asymmetry over one session (SPEC Day 4 Task 2).

    asymmetry = abs(outlet_1 - outlet_2) at each timestamp where both outlets
    report. Returns temp_asymmetry_max / _mean / _final; all None for
    single-outlet sessions (no pairable timestamps). Calibration target:
    ~10°C on normal Station-A sessions.
    """
    series = _temperature_series(session_meter_values)
    outlet_1 = {ts: value for ts, value in series.get("outlet_1", [])}
    outlet_2 = {ts: value for ts, value in series.get("outlet_2", [])}
    shared_ts = sorted(outlet_1.keys() & outlet_2.keys())
    if not shared_ts:
        return {
            "temp_asymmetry_max": None,
            "temp_asymmetry_mean": None,
            "temp_asymmetry_final": None,
        }
    asymmetry = [abs(outlet_1[ts] - outlet_2[ts]) for ts in shared_ts]
    return {
        "temp_asymmetry_max": max(asymmetry),
        "temp_asymmetry_mean": sum(asymmetry) / len(asymmetry),
        "temp_asymmetry_final": asymmetry[-1],
    }


def _measurand_series(session_meter_values: list, measurand: str) -> list[tuple]:
    """All samples of one measurand as [(timestamp, value), ...], time-sorted.

    Accepts the same sampledValue-shaped dicts as the temperature features.
    Rows with unparseable values are skipped.
    """
    series = []
    for sample in session_meter_values:
        if sample.get("measurand") != measurand:
            continue
        ts = _sample_ts(sample)
        if ts is None:
            continue
        try:
            value = float(sample["value"])
        except (KeyError, TypeError, ValueError):
            continue
        series.append((ts, value))
    series.sort(key=lambda pair: pair[0])
    return series


def _slope(points: list[tuple]) -> float | None:
    """Least-squares slope of value over elapsed seconds; None for <2 points."""
    if len(points) < 2:
        return None
    t0 = points[0][0]
    xs = [(ts - t0).total_seconds() for ts, _ in points]
    ys = [value for _, value in points]
    n = len(points)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:  # all samples at the same instant
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom


def _power_curve_features(session_meter_values: list) -> dict:
    """CC-CV power-curve shape features (SPEC Day 5 Task 1).

    peak_power           — max Power.Active.Import in the session
    cc_cv_taper_slope    — least-squares slope of power over time from the
                           peak onward (the CV tapering phase); expected
                           negative on a healthy full charge
    cc_cv_peak_frac_final — final power as a fraction of peak power (proxy
                           for how "full" the charge got — the SoC-proxy
                           strategy for sessions where SoC reports 0)
    All None when the session carries no power samples.
    """
    series = _measurand_series(session_meter_values, POWER_MEASURAND)
    if not series:
        return {
            "peak_power": None,
            "cc_cv_taper_slope": None,
            "cc_cv_peak_frac_final": None,
        }
    values = [value for _, value in series]
    peak = max(values)
    peak_index = values.index(peak)
    return {
        "peak_power": peak,
        "cc_cv_taper_slope": _slope(series[peak_index:]),
        "cc_cv_peak_frac_final": values[-1] / peak if peak > 0 else None,
    }


def _session_scale_features(session_transaction: dict, session_meter_values: list) -> dict:
    """Duration and energy scale of one session (SPEC Day 5 Task 2).

    duration_sec — from the transaction's start/stop timestamps
    energy_wh    — last minus first Energy.Active.Import.Register reading
    energy_per_second — energy_wh / duration_sec

    session_transaction needs start_timestamp / stop_timestamp keys
    (datetime). energy fields are None without energy samples; duration is
    None for still-open sessions.
    """
    start = session_transaction.get("start_timestamp")
    stop = session_transaction.get("stop_timestamp")
    duration = (stop - start).total_seconds() if start and stop else None

    series = _measurand_series(session_meter_values, ENERGY_MEASURAND)
    energy = series[-1][1] - series[0][1] if len(series) >= 2 else None

    per_second = None
    if energy is not None and duration is not None and duration > 0:
        per_second = energy / duration
    return {
        "duration_sec": duration,
        "energy_wh": energy,
        "energy_per_second": per_second,
    }


@dataclass
class SessionFeatures:
    """Feature vector for one completed charging session (SPEC §4.1)."""

    connector_pk: int
    started_at: datetime
    peak_temp_body: float | None
    peak_temp_outlet_1: float | None
    peak_temp_outlet_2: float | None
    max_outlet_asymmetry: float | None  # 10°C asymmetry = candidate leading indicator
    peak_power_w: float | None
    taper_slope: float | None           # CC-CV curve tail coefficient
    duration_seconds: float
    energy_delivered_wh: float
    soc_proxy_slope: float | None       # power/peak-power ratio slope; used when SoC field is 0


class SessionFeatureExtractor:
    """Accumulates one session's raw telemetry, emits a SessionFeatures row.

    One instance per open transaction. Feed MeterValues in timestamp order
    between start and stop; call finalize() after StopTransaction.
    """

    def __init__(self, start: StartTransaction) -> None:
        self.connector_pk = start.connector_pk
        self.started_at = start.start_timestamp

    def on_meter_values(self, msg: MeterValues) -> None:
        """Accumulate a telemetry sample into running aggregates."""
        raise NotImplementedError

    def finalize(self, stop: StopTransaction) -> SessionFeatures:
        """Close the session and compute the full feature vector."""
        raise NotImplementedError


class ConnectorBaseline:
    """Rolling per-connector 'normal' statistics for drift scoring.

    Applies to heavy/medium/light tiers (≥100 sessions). Sparse/marginal
    connectors fall back to PooledBaseline.
    """

    def __init__(self, connector_pk: int) -> None:
        self.connector_pk = connector_pk

    def update(self, features: SessionFeatures) -> None:
        """Fold a new normal session into the rolling mean/std."""
        raise NotImplementedError

    def drift_score(self, features: SessionFeatures) -> float:
        """Z-score-style distance of this session from the connector's baseline."""
        raise NotImplementedError


class PooledBaseline:
    """Cross-fleet baseline cohorted by vendor/firmware, for sparse connectors."""

    def __init__(self, cohort_key: str) -> None:
        self.cohort_key = cohort_key

    def update(self, features: SessionFeatures) -> None:
        raise NotImplementedError

    def drift_score(self, features: SessionFeatures) -> float:
        raise NotImplementedError


class IsolationForestScorer:
    """Inference wrapper around the trained Isolation Forest artifact.

    Training happens offline on Akhil's machine; the .pkl artifact is committed
    to models/ and only loaded for inference here (SPEC §4.3, §5.2).
    """

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path

    def load(self) -> None:
        raise NotImplementedError

    def score(self, features: SessionFeatures) -> float:
        """Anomaly score for one session; higher = more anomalous."""
        raise NotImplementedError


class Layer2Anomaly:
    """Inference over the committed Isolation Forest artifacts (SPEC Day 6).

    Resolves (hashed_charge_box_id, connector_id) to the per-connector model
    when one exists, else to the vendor-family pooled model, and scores one
    session's feature vector. Flag = score < threshold; threshold comes from
    the LAYER2_THRESHOLD env var (default -0.1 per SPEC — the calibrated
    deployment value lives in the model index, see notebook 03).

    Models are lazy-loaded and cached; sklearn is imported only via the
    pickles, so Layer 1 keeps working on machines without it.
    """

    def __init__(self, models_dir: str | Path = "models",
                 threshold: float | None = None) -> None:
        self.models_dir = Path(models_dir)
        self.threshold = (
            float(os.environ.get("LAYER2_THRESHOLD", DEFAULT_LAYER2_THRESHOLD))
            if threshold is None else threshold
        )
        self._models: dict[str, object] = {}
        index_path = self.models_dir / "isoforest_index.pkl"
        self.available = index_path.exists()
        if not self.available:
            print(f"warning: {index_path} not found — Layer 2 scoring disabled",
                  file=sys.stderr)
            self.index = {}
            self._by_identity = {}
            return
        with index_path.open("rb") as f:
            self.index = pickle.load(f)
        # (hashed_charge_box_id, physical_plug_id) -> connector_pk
        self._by_identity = {
            (info["hashed_charge_box_id"], info["physical_plug_id"]): pk
            for pk, info in self.index.get("connectors", {}).items()
        }
        self.features = self.index["features"]

    def _load_model(self, filename: str):
        if filename not in self._models:
            with (self.models_dir / filename).open("rb") as f:
                self._models[filename] = pickle.load(f)
        return self._models[filename]

    def _model_file_for(self, connector_pk: int) -> str | None:
        entry = self.index.get("connector_models", {}).get(connector_pk)
        if entry is not None:
            return entry["file"]
        family = self.index.get("connectors", {}).get(connector_pk, {}).get(
            "vendor_family", "unknown")
        pooled_models = self.index.get("pooled_models", {})
        # Families without their own cohort (thin or unseen) route to the
        # global pooled model when the artifact set provides one.
        pooled = pooled_models.get(family) or pooled_models.get("_global")
        return pooled["file"] if pooled else None

    def score(self, session_features: dict, hashed_charge_box_id: str,
              connector_id: int) -> tuple[float, bool] | None:
        """Raw anomaly score + flag for one closed session.

        session_features maps feature name -> value and must cover the
        trained feature list. Returns None when no model serves this
        connector, a feature is missing, or artifacts are absent.
        """
        if not self.available:
            return None
        connector_pk = self._by_identity.get((hashed_charge_box_id, connector_id))
        if connector_pk is None:
            return None
        return self.score_by_connector_pk(session_features, connector_pk)

    def score_by_connector_pk(self, session_features: dict,
                              connector_pk: int) -> tuple[float, bool] | None:
        """Same as score(), keyed by connector_pk (what the event stream has)."""
        if not self.available:
            return None
        filename = self._model_file_for(connector_pk)
        if filename is None:
            return None
        try:
            vector = [[float(session_features[name]) for name in self.features]]
        except (KeyError, TypeError, ValueError):
            return None
        raw = float(self._load_model(filename).decision_function(vector)[0])
        return raw, raw < self.threshold
