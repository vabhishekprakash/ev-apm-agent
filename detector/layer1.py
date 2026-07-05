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

# Observed meter cadence is ~30s; 3× that with no MeterValues during an
# active session is the silence-fault signature (SPEC Day 5, §3.5).
# Overridable via the SILENCE_THRESHOLD_SECONDS env var (see .env.example).
DEFAULT_SILENCE_THRESHOLD_SECONDS = 90.0

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
    fault_code: str | None = None
    # Canonical OCPP category (vendor_code_normalizer) — prioritizer rules
    # and the UI category rollups key on this.
    fault_category: str | None = None
    mechanism: str | None = None
    # Detectors without a recovery signal (err1024, silence) set this instead
    # of deriving the classification from recovered_after_seconds.
    classification_override: str | None = None
    # Silence detector only: how long the session had been quiet when fired.
    silence_seconds: float | None = None

    @property
    def is_transient(self) -> bool:
        """Self-recovered within the ≤15s window — deprioritize."""
        return (
            self.recovered_after_seconds is not None
            and self.recovered_after_seconds <= TRANSIENT_THRESHOLD_SECONDS
        )

    @property
    def classification(self) -> str:
        if self.classification_override is not None:
            return self.classification_override
        if self.recovered_after_seconds is None:
            return "unclassified"
        return "transient" if self.is_transient else "technician-dispatch"

    def to_dict(self) -> dict:
        payload = {
            "detector_source": self.detector,
            "connector_pk": self.connector_pk,
            "fired_at": self.fired_at.isoformat(),
            "stage": self.stage,
            "fault_code": self.fault_code,
            "fault_category": self.fault_category,
            "mechanism": self.mechanism,
            "recovery_seconds": self.recovered_after_seconds,
            "classification": self.classification,
        }
        if self.silence_seconds is not None:
            payload["silence_seconds"] = self.silence_seconds
        return payload


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
        stuck_alert = None
        if self.state is not Err1051State.IDLE and self._stuck(event):
            if self._completes_recovery(event):
                # Recovery observed, merely slower than the dwell limit — fall
                # through so _on_status computes the true recovery_seconds
                # (>15s, so it classifies technician-dispatch on its own).
                pass
            else:
                if self.state is Err1051State.STOP_TXN:
                    # The fault outlived the dwell limit with no recovery in
                    # sight: this is the most dispatch-worthy case, so emit
                    # the final alert (recovery unobserved) instead of
                    # silently dropping the sequence.
                    stuck_alert = FaultAlert(
                        detector=self.DETECTOR_NAME,
                        connector_pk=self.connector_pk,
                        fired_at=_event_ts(event),
                        stage="final",
                        fault_code="err1051",
                        mechanism="internal socket init failure",
                        classification_override="technician-dispatch",
                    )
                print(
                    f"warning: err1051 machine for connector {self.connector_pk} "
                    f"stuck in {self.state.name} >{STUCK_STATE_TIMEOUT_SECONDS:.0f}s, resetting",
                    file=sys.stderr,
                )
                self.reset()

        alert = None
        if isinstance(event, StatusNotification):
            alert = self._on_status(event)
        elif isinstance(event, MeterValues):
            alert = self._on_meter_values(event)
        elif isinstance(event, StopTransaction):
            alert = self._on_stop_transaction(event)
        # StartTransaction plays no role in this sequence.

        # Dispatch from IDLE never produces an alert, so the two can't clash.
        return alert if alert is not None else stuck_alert

    def _completes_recovery(self, event: Event) -> bool:
        """True when the incoming event is the Available status the STOP_TXN
        state is waiting for — a slow recovery, not a wedged machine."""
        return (
            self.state is Err1051State.STOP_TXN
            and isinstance(event, StatusNotification)
            and event.status.value == "Available"
        )

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
                fault_code="err1051",
                mechanism="internal socket init failure",
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
                fault_code="err1051",
                mechanism="internal socket init failure",
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

    CONFIRMED FINAL (2026-07-05): the data-owner reply arrived as an
    aggregate crash signature (data/raw/err1024_crash_signature.csv, 3 real
    events): supply stays nominal (227.4–227.9 V, ~49.9 Hz) while current
    and power sit at ~0 and the energy register never moves — "energized but
    never charging", consistent with the pre-charge SLAC handshake failure.
    No retry-sequence or recovery-time signal exists in the data, so the
    point-event design is final; every sighting fires, and burst/repeat
    escalation lives in AlertPrioritizer. The meter signature can gate false
    positives once measurand-bearing telemetry streams live (enhancement,
    not a blocker).
    """

    DETECTOR_NAME = "err1024"

    def __init__(self, connector_pk: int) -> None:
        self.connector_pk = connector_pk

    def consume(self, event: Event) -> FaultAlert | None:
        if isinstance(event, StatusNotification):
            return self.on_status(event)
        return None

    def on_status(self, msg: StatusNotification) -> FaultAlert | None:
        if msg.error_code != ERR_1024:
            return None
        return FaultAlert(
            detector=self.DETECTOR_NAME,
            connector_pk=self.connector_pk,
            fired_at=msg.timestamp,
            fault_code="err1024",
            mechanism="SLAC handshake timeout",
            classification_override="technician-dispatch-likely",
        )


class CategoryPointDetector:
    """Point-event handler for one canonical OCPP category (Week 2 Day 4).

    Fires a FaultAlert whenever a StatusNotification's canonical category
    (vendor_code_normalizer output, attached by main.py as
    msg_canonical_category) matches. Escalation logic — WeakSignal bursts,
    Under/OverVoltage 24h repeats, GroundFailure straight to P1 — lives in
    AlertPrioritizer's rules, keyed on the fault_category field this detector
    stamps; keeping the detectors stateless avoids duplicating that state.

    Real-event verification pending the fault-event export (audit: the capped
    status export carries no fault rows) — fixture-verified meanwhile.
    """

    def __init__(self, connector_pk: int, categories: tuple[str, ...],
                 detector_name: str, mechanism: str) -> None:
        self.connector_pk = connector_pk
        self.categories = categories
        self.detector_name = detector_name
        self.mechanism = mechanism

    def consume(self, event: Event, canonical_category: str | None = None) -> FaultAlert | None:
        if not isinstance(event, StatusNotification) or canonical_category is None:
            return None
        if canonical_category not in self.categories:
            return None
        return FaultAlert(
            detector=self.detector_name,
            connector_pk=self.connector_pk,
            fired_at=event.timestamp,
            fault_code=canonical_category,
            fault_category=canonical_category,
            mechanism=self.mechanism,
            classification_override="unclassified",
        )


def make_category_detectors(connector_pk: int) -> list:
    """The Day 4 category point-detectors: WeakSignal, GroundFailure,
    Under/OverVoltage (combined handler per SPEC)."""
    return [
        CategoryPointDetector(connector_pk, ("WeakSignal",),
                              "weak_signal", "modem signal degradation"),
        CategoryPointDetector(connector_pk, ("GroundFailure",),
                              "ground_failure", "ground fault — electrical safety"),
        CategoryPointDetector(connector_pk, ("UnderVoltage", "OverVoltage"),
                              "voltage", "supply voltage out of band"),
    ]


class TelemetrySilenceDetector:
    """Flags an active session that has gone >threshold with no MeterValues.

    Driven by a clock tick rather than events alone, since silence is the
    absence of events. The tick clock is event time supplied by the caller
    (main.py ticks with every stream event's timestamp, including Heartbeats
    and other connectors' traffic), so REPLAY_SPEED_MULTIPLIER=0 works.
    Fires once per silent stretch; a fresh MeterValues re-arms it.
    """

    DETECTOR_NAME = "telemetry_silence"

    def __init__(
        self,
        connector_pk: int,
        threshold_seconds: float = DEFAULT_SILENCE_THRESHOLD_SECONDS,
    ) -> None:
        self.connector_pk = connector_pk
        self.threshold_seconds = threshold_seconds
        self.session_open = False
        self.last_meter_at: datetime | None = None
        self.alerted = False

    def consume(self, event: Event) -> None:
        if isinstance(event, StartTransaction):
            self.on_start_transaction(event)
        elif isinstance(event, MeterValues):
            self.on_meter_values(event)
        elif isinstance(event, StopTransaction):
            self.on_stop_transaction(event)

    def on_start_transaction(self, msg: StartTransaction) -> None:
        self.session_open = True
        # No MeterValues yet; the session open is the baseline for silence.
        self.last_meter_at = msg.start_timestamp
        self.alerted = False

    def on_meter_values(self, msg: MeterValues) -> None:
        if self.session_open:
            self.last_meter_at = msg.timestamp
            self.alerted = False  # telemetry resumed — re-arm

    def on_stop_transaction(self, msg: StopTransaction) -> None:
        self.session_open = False
        self.last_meter_at = None
        self.alerted = False

    def on_tick(self, now: datetime) -> FaultAlert | None:
        """Check silence duration against threshold at the current clock."""
        if not self.session_open or self.alerted or self.last_meter_at is None:
            return None
        silent_for = (now - self.last_meter_at).total_seconds()
        if silent_for <= self.threshold_seconds:
            return None
        self.alerted = True
        return FaultAlert(
            detector=self.DETECTOR_NAME,
            connector_pk=self.connector_pk,
            fired_at=now,
            fault_code="telemetry_silence",
            mechanism=f"no MeterValues for >{self.threshold_seconds:.0f}s during active session",
            classification_override="investigate",
            silence_seconds=silent_for,
        )
