"""UI service: minimal single-page alert dashboard (SPEC Day 6, Task 1).

- GET /        — single-file HTML page, vanilla JS, polls /alerts every 2s
- GET /alerts  — last N alerts from an in-memory ring buffer, newest first
- POST /alerts — accepts one alert (or a list) from the detector service

Judge-readable is the bar. In-memory only; restarting the container clears
the buffer. ALERT_BUFFER_SIZE caps the ring buffer (default 500).
"""

import os
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

BUFFER_SIZE = int(os.environ.get("ALERT_BUFFER_SIZE", "500"))

app = FastAPI(title="EV APM UI Service")
alerts: deque = deque(maxlen=BUFFER_SIZE)


@app.get("/health")
def health():
    return {"status": "healthy", "alerts_buffered": len(alerts)}


@app.post("/alerts")
async def receive_alerts(request: Request):
    payload = await request.json()
    batch = payload if isinstance(payload, list) else [payload]
    received_at = datetime.now(timezone.utc).isoformat()
    for alert in batch:
        alert["received_at"] = received_at
        alerts.append(alert)
    return {"accepted": len(batch), "buffered": len(alerts)}


@app.get("/alerts")
def list_alerts(limit: int = 100):
    return list(alerts)[-limit:][::-1]  # newest first


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>EV APM — live fault alerts</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 1.5rem; background: #111; color: #eee; }
  h1 { font-size: 1.2rem; } h1 small { color: #888; font-weight: normal; }
  #status { color: #888; font-size: 0.85rem; margin-bottom: 0.75rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  th, td { padding: 0.35rem 0.6rem; text-align: left; border-bottom: 1px solid #333; }
  th { color: #aaa; position: sticky; top: 0; background: #111; }
  tr.err1051 td.src { color: #ff9f43; } tr.err1024 td.src { color: #ff6b6b; }
  tr.telemetry_silence td.src { color: #74b9ff; } tr.layer2_drift td.src { color: #a29bfe; }
  .transient { color: #2ecc71; } .technician-dispatch, .technician-dispatch-likely { color: #ff6b6b; }
  .investigate, .unclassified { color: #fdcb6e; }
  td.mono { font-family: ui-monospace, monospace; color: #999; }
</style>
</head>
<body>
<h1>EV APM — live fault alerts <small>polling every 2s</small></h1>
<div id="status">waiting for first poll…</div>
<table>
  <thead><tr>
    <th>fired at</th><th>station</th><th>connector</th><th>source</th>
    <th>fault</th><th>classification</th><th>recovery (s)</th><th>detail</th>
  </tr></thead>
  <tbody id="rows"></tbody>
</table>
<script>
function cell(text, cls) {
  const td = document.createElement('td');
  td.textContent = text === null || text === undefined ? '—' : text;
  if (cls) td.className = cls;
  return td;
}
async function poll() {
  try {
    const res = await fetch('/alerts?limit=100');
    const alerts = await res.json();
    const rows = document.getElementById('rows');
    rows.replaceChildren();
    for (const a of alerts) {
      const tr = document.createElement('tr');
      tr.className = a.detector_source || '';
      const station = a.hashed_charge_box_id ? a.hashed_charge_box_id.slice(0, 10) + '…' : null;
      const connector = a.physical_plug_id != null
        ? `plug ${a.physical_plug_id} (pk ${a.connector_pk})` : a.connector_pk;
      tr.append(
        cell(a.fired_at), cell(station, 'mono'), cell(connector),
        cell(a.detector_source, 'src'), cell(a.fault_code),
        cell(a.classification, a.classification), cell(a.recovery_seconds),
        cell(a.silence_seconds != null ? `silent ${a.silence_seconds}s`
             : a.anomaly_score != null ? `score ${a.anomaly_score}` : a.stage)
      );
      rows.append(tr);
    }
    document.getElementById('status').textContent =
      `${alerts.length} alert(s) shown — last poll ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    document.getElementById('status').textContent = 'poll failed: ' + err;
  }
}
poll();
setInterval(poll, 2000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE
