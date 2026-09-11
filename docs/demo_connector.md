# Demo connector choice

**Chosen: connector_pk 2009529 — Station-A plug 1**
(station hash `0c70c6b0…`, vendor CN.TH — identity per audit flag 9)

## Rationale

- **Real fault history, at scale:** 946 Faulted episodes in the recovered
  status export (2025-10 → 2026-07), with the full recovery-time spread the
  pitch needs — fast self-recoveries alongside multi-minute dispatch cases
  (station-wide: median 33 s, ~42% ≤15 s, audit flag 12).
- **Session volume:** 861 delivered normal sessions (heaviest tier in the
  delivered set); 658 sessions scored during full-export replay.
- **Own Layer 2 model:** per-connector Isolation Forest
  (`isoforest_0c70c6b0…_1.pkl`), so the drift panel shows a genuine
  per-connector baseline, not the pooled fallback — 21 drift-flagged
  sessions in the last replay give the panel visible red markers.
- **Story coherence:** the same station carries the plug-0 anomaly
  (2013696) and the err1051 narrative, so the whole demo can stay on one
  charger a judge can hold in their head.

**Runner-up:** 2009530 (same station, plug 2 — near-identical profile;
switch if plug 1's replay looks unlucky on the day).

## Caveats for the narration

- The drift panel trends **anomaly score + session duration**. The spec's
  preferred temperature-asymmetry trend is impossible on current data — the
  export's temperature field is dead (all 0.0 °C, audit flag 11). Do not
  claim temperature tracking in the demo; say "session-profile drift".
- Fault episodes in the recovered export carry no error codes, so the demo
  labels them "Faulted (category pending err1024/err1051 split — data owner)".
