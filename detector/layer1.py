"""Layer 1 — deterministic fault detectors.

Day 4: Err1051Detector transitions implemented per the SPEC Day 4 table.
Err1024Detector and TelemetrySilenceDetector remain Day 5 skeletons.

Three sub-detectors:
- Err1051Detector: 5-step state machine for system-err1051
  (GQ_DIN_ERROR_INIT_SOCKET — internal socket init failure)
- Err1024Detector: point-event handler for system-err1024
  (GQ_SLAC_ERROR_PARAM_TIMEOUT — SLAC handshake failure, pre-charge)
- TelemetrySilenceDetector: active session with no MeterValues for >N seconds
  (silence IS the fault signature — see SPEC §3.5)
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from ocpp_messages import MeterValues, StartTransaction, StatusNotification, StopTransaction

ERR_1051 = "system-err1051"
ERR_1024 = "system-err1024"

# err1051 self-clears in ~13s on the two labeled events; the classification
# boundary is 15s per the Day 4 spec (transient ≤15s, technician-dispatch >15s).
SELF_RECOVERY_SECONDS = 13.0
TRANSIENT_THRESHOLD_SECONDS = 15.0

# Any non-IDLE dwell longer than this means the sequence stalled; reset.
STUCK_STATE_TIMEOUT_SECONDS = 60.0

Event = StatusNotification | MeterValues | StartTransaction | StopTransaction


@dataclass
class FaultAlert:
    """Emitted by any Layer 1 sub-detector when a fault pattern completes."""

    detector: str
    connector_pk: int
    fired_at: datetime
    # "candidate" fires at StopTransaction(Other); "final" once recovery is
    # observed and recovery_seconds is computable.
    stage: str = "final"
    # None until recovery observed; used to classify transient vs dispatch.
    recovered_after_seconds: float | None = None

    @property
    def is_transient(self) -> bool:
        """Self-recovered within the ≤15s window — deprioritize."""
        return (
            self.recovered_after_seconds is not None
            and self.recovered_after_seconds <= TRANSIENT_THRESHOLD_SECONDS
        )

    @property
    def classification(self) -> str:
        if self.recovered_after_seconds is None:
            return "unclassified"
        return "transient" if self.is_transient else "technician-dispatch"

    def to_dict(self) -> dict:
        return {
            "detector_source": self.detector,
            "connector_pk": self.connector_pk,
            "fired_at": self.fired_at.isoformat(),
            "stage": self.stage,
            "recovery_seconds": self.recovered_after_seconds,
            "classification": self.classification,
        }


class Err1051State(Enum):
    """States of the reproducible err1051 sequence (SPEC Day 4 table)."""

    IDLE = auto()             # nothing observed
    ERR_FIRST_SEEN = auto()   # 1. StatusNotification carrying err1051
    METER_ZERO = auto()       # 2. MeterValues dropped to zero
    ERR_SECOND_SEEN = auto()  # 3. Finishing status, second err1051
    STOP_TXN = auto()         # 4. StopTransaction with reason "Other" (candidate alert)
    # 5. Available again → final alert, machine returns to IDLE


class Err1051Detector:
    """Per-connector state machine matching the 5-step err1051 sequence.

    One instance tracks one connector. Feed it every event for that connector
    in timestamp order via consume(); it emits a candidate FaultAlert when the
    StopTransaction lands and a final one (with recovery_seconds) when the
    connector comes back Available.
    """

    DETECTOR_NAME = "err1051"

    def __init__(self, connector_pk: int) -> None:
        self.connector_pk = connector_pk
        self.state = Err1051State.IDLE
        # Timestamp of the event that caused the last transition; drives the
        # stuck-state timeout. Event time, not wall clock, so replay speed
        # doesn't matter.
        self.entered_state_at: datetime | None = None
        self.first_seen_at: datetime | None = None
        self.stopped_at: datetime | None = None

    def consume(self, event: Event) -> FaultAlert | None:
        if self.state is not Err1051State.IDLE and self._stuck(event):
            print(
                f"warning: err1051 machine for connector {self.connector_pk} "
                f"stuck in {self.state.name} >{STUCK_STATE_TIMEOUT_SECONDS:.0f}s, resetting",
                file=sys.stderr,
            )
            self.reset()

        if isinstance(event, StatusNotification):
            return self._on_status(event)
        if isinstance(event, MeterValues):
            return self._on_meter_values(event)
        if isinstance(event, StopTransaction):
            return self._on_stop_transaction(event)
        return None  # StartTransaction plays no role in this sequence

    def reset(self) -> None:
        """Return to IDLE (sequence broken, stalled, or completed)."""
        self.state = Err1051State.IDLE
        self.entered_state_at = None
        self.first_seen_at = None
        self.stopped_at = None

    # -- internals -----------------------------------------------------------

    def _stuck(self, event: Event) -> bool:
        ts = _event_ts(event)
        return (
            self.entered_state_at is not None
            and (ts - self.entered_state_at).total_seconds() > STUCK_STATE_TIMEOUT_SECONDS
        )

    def _transition(self, state: Err1051State, at: datetime) -> None:
        self.state = state
        self.entered_state_at = at

    def _on_status(self, msg: StatusNotification) -> FaultAlert | None:
        if self.state is Err1051State.IDLE and msg.error_code == ERR_1051:
            self.first_seen_at = msg.timestamp
            self._transition(Err1051State.ERR_FIRST_SEEN, msg.timestamp)
        elif (
            self.state is Err1051State.METER_ZERO
            and msg.error_code == ERR_1051
            and msg.status.value == "Finishing"
        ):
            self._transition(Err1051State.ERR_SECOND_SEEN, msg.timestamp)
        elif self.state is Err1051State.STOP_TXN and msg.status.value == "Available":
            recovery = (msg.timestamp - self.stopped_at).total_seconds()
            alert = FaultAlert(
                detector=self.DETECTOR_NAME,
                connector_pk=self.connector_pk,
                fired_at=msg.timestamp,
                stage="final",
                recovered_after_seconds=recovery,
            )
            self.reset()
            return alert
        return None

    def _on_meter_values(self, msg: MeterValues) -> FaultAlert | None:
        # Spec guard is voltage AND current AND power == 0; the current export
        # only carries meter_reading_wh (measurand column lands with the
        # re-export — data_audit_v0.md flag 6), so a zero reading stands in.
        if self.state is Err1051State.ERR_FIRST_SEEN and msg.meter_reading_wh == 0:
            self._transition(Err1051State.METER_ZERO, msg.timestamp)
        return None

    def _on_stop_transaction(self, msg: StopTransaction) -> FaultAlert | None:
        if self.state is Err1051State.ERR_SECOND_SEEN and msg.stop_reason == "Other":
            self.stopped_at = msg.stop_timestamp
            self._transition(Err1051State.STOP_TXN, msg.stop_timestamp)
            return FaultAlert(
                detector=self.DETECTOR_NAME,
                connector_pk=self.connector_pk,
                fired_at=msg.stop_timestamp,
                stage="candidate",
            )
        return None


def _event_ts(event: Event) -> datetime:
    if isinstance(event, StartTransaction):
        return event.start_timestamp
    if isinstance(event, StopTransaction):
        return event.stop_timestamp
    return event.timestamp


class Err1024Detector:
    """Point-event handler for err1024 — no state machine, fires on sight.

    SLAC handshake failure happens pre-charge, so there may be no transaction
    open. Sequencing questions (StartTransaction ordering, retry bursts,
    recovery signal) are still under investigation — SPEC §7 item 1.
    """

    def __init__(self, connector_pk: int) -> None:
        self.connector_pk = connector_pk

    def on_status(self, msg: StatusNotification) -> FaultAlert | None:
        raise NotImplementedError

class TelemetrySilenceDetector:
    """Flags an active session that has gone >threshold with no MeterValues.

    Driven by a clock tick rather than events alone, since silence is the
    absence of events.
    """

    def __init__(self, connector_pk: int, threshold_seconds: float) -> None:
        self.connector_pk = connector_pk
        self.threshold_seconds = threshold_seconds
        self.session_open = False
        self.last_meter_at: datetime | None = None

    def on_start_transaction(self, msg: StartTransaction) -> None:
        raise NotImplementedError

    def on_meter_values(self, msg: MeterValues) -> None:
        raise NotImplementedError

    def on_stop_transaction(self, msg: StopTransaction) -> None:
        raise NotImplementedError

    def on_tick(self, now: datetime) -> FaultAlert | None:
        """Check silence duration against threshold at the current clock."""
        raise NotImplementedError
