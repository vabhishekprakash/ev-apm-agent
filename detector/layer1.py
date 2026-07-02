"""Layer 1 — deterministic fault detectors.

Day 3 skeleton: interfaces and state enums only, no transition logic yet.
Transition logic lands Day 4-5 (see docs/SPEC.md §8, Week 1 targets).

Three sub-detectors:
- Err1051Detector: 5-step state machine for system-err1051
  (GQ_DIN_ERROR_INIT_SOCKET — internal socket init failure)
- Err1024Detector: point-event handler for system-err1024
  (GQ_SLAC_ERROR_PARAM_TIMEOUT — SLAC handshake failure, pre-charge)
- TelemetrySilenceDetector: active session with no MeterValues for >N seconds
  (silence IS the fault signature — see SPEC §3.5)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from ocpp_messages import MeterValues, StartTransaction, StatusNotification, StopTransaction

ERR_1051 = "system-err1051"
ERR_1024 = "system-err1024"

# err1051 self-clears in ~13s; recovery slower than this suggests a real outage.
SELF_RECOVERY_SECONDS = 13.0


@dataclass
class FaultAlert:
    """Emitted by any Layer 1 sub-detector when a fault pattern completes."""

    detector: str
    connector_pk: int
    fired_at: datetime
    # None until recovery observed; used to classify transient vs dispatch.
    recovered_after_seconds: float | None = None

    @property
    def is_transient(self) -> bool:
        """Self-recovered within the known ~13s window — deprioritize."""
        raise NotImplementedError


class Err1051State(Enum):
    """States of the reproducible err1051 sequence (SPEC §3.4)."""

    IDLE = auto()                  # nothing observed
    ERROR_WHILE_CHARGING = auto()  # 1. Charging status carrying err1051
    METERS_DROPPED = auto()        # 2. MeterValues fell to zero simultaneously
    ERROR_WHILE_FINISHING = auto() # 3. Finishing status, second err1051
    STOPPED_OTHER = auto()         # 4. StopTransaction with reason "Other"
    RECOVERED = auto()             # 5. Available again (~13s later)


class Err1051Detector:
    """Per-connector state machine matching the 5-step err1051 sequence.

    One instance tracks one connector. Feed it every event for that connector
    in timestamp order; it emits a FaultAlert when the sequence completes.
    """

    def __init__(self, connector_pk: int) -> None:
        self.connector_pk = connector_pk
        self.state = Err1051State.IDLE

    def on_status(self, msg: StatusNotification) -> FaultAlert | None:
        raise NotImplementedError

    def on_meter_values(self, msg: MeterValues) -> FaultAlert | None:
        raise NotImplementedError

    def on_stop_transaction(self, msg: StopTransaction) -> FaultAlert | None:
        raise NotImplementedError

    def reset(self) -> None:
        """Return to IDLE (sequence broken or completed)."""
        raise NotImplementedError


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
