# Layer 1 Detector Set: ROI Prioritization

**Strategic Recommendation:** Promote the three **P1** categories into the Week 2 Layer 1 work stream. Expanding to a 6-category multi-fault detector creates a materially stronger pitch. Do not attempt P2 or SKIP categories within the current hackathon window.

### Prioritization Matrix
Ranked by ROI (volume × pattern-tractability × judge-clarity).

| Priority | Category | Rationale |
| :--- | :--- | :--- |
| **P0 (Keep)** | `system-err1051 state machine` | Already built, reproducible signature confirmed. |
| **P0 (Keep)** | `system-err1024 point event` | Already built. |
| **P0 (Keep)** | `telemetry-silence sub-detector` | Already built, orthogonal signal. |
| **P1 (New)** | `WeakSignal pattern` | 223k events, communication layer — likely has clear precursor pattern in heartbeat gaps. |
| **P1 (New)** | `GroundFailure pattern` | 217k events, electrical — likely correlates with voltage/current instability before firing. |
| **P1 (New)** | `UnderVoltage / OverVoltage` | ~190k combined, direct measurand signal — cleanest supervised story. |
| **P2 (Nice-to-have)** | `PowerSwitchFailure` | 14k events, moderate volume, tractable. |
| **P2 (Nice-to-have)** | `EVCommunicationError` | 8k events, connects to err1024's SLAC story thematically. |
| **SKIP** | `InternalError` | Too broad, 927k catch-all — will be all noise. |
| **SKIP** | `HighTemperature / ConnectorLockFailure` | Too thin — <500 events. |