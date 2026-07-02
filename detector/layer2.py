"""Layer 2 — unsupervised per-connector drift detection.

Day 3 skeleton: class shells with method signatures and docstrings, no logic.
Owner: Akhil. Feature logic and Isolation Forest training land Week 1-2
(see docs/SPEC.md §4.1, §8). Tier cutoffs live in docs/layer2_scope.md.
"""

from dataclasses import dataclass
from datetime import datetime

from ocpp_messages import MeterValues, StartTransaction, StopTransaction


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
