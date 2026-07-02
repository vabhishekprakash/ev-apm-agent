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

from dataclasses import dataclass
from datetime import datetime

from ocpp_messages import MeterValues, StartTransaction, StopTransaction

TEMPERATURE_MEASURAND = "Temperature"

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


def _temperature_series(session_meter_values: list) -> dict[str, list[tuple]]:
    """Group Temperature samples by normalized location, sorted by timestamp.

    Returns {"body"|"outlet_1"|"outlet_2": [(timestamp, value), ...]};
    locations with no samples are absent. Non-Temperature rows, unknown
    locations, and unparseable values are skipped.
    """
    series: dict[str, list[tuple]] = {}
    for sample in session_meter_values:
        if sample.get("measurand") != TEMPERATURE_MEASURAND:
            continue
        location = _normalize_location(sample.get("location"))
        if location is None:
            continue
        try:
            value = float(sample["value"])
        except (KeyError, TypeError, ValueError):
            continue
        series.setdefault(location, []).append((sample.get("timestamp"), value))
    for samples in series.values():
        samples.sort(key=lambda pair: pair[0])
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
    ~10°C on normal PRABHAEV004N sessions.
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
