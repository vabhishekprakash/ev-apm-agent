"""UI service: priority-aware alert dashboard (Week 2 Day 2).

Endpoints:
- GET  /            single-file dashboard (vanilla JS, no CDN — demo-safe offline)
- GET  /alerts      ring buffer, newest first
- POST /alerts      alerts from the detector (single or batch)
- GET/POST /stats   detector pipeline counters (sessions processed, flag rate)
- POST /sessions    per-closed-session record from the detector (drift trends)
- GET  /connectors  connectors with session history, for the drift picker
- GET  /drift/{pk}  chronological per-session records for one connector
- GET  /health

In-memory only; restart clears. ALERT_BUFFER_SIZE caps the alert ring buffer
(default 500); per-connector session history caps at SESSION_BUFFER_SIZE.
"""

import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from itertools import islice

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

BUFFER_SIZE = int(os.environ.get("ALERT_BUFFER_SIZE", "500"))
SESSION_BUFFER_SIZE = int(os.environ.get("SESSION_BUFFER_SIZE", "2000"))

app = FastAPI(title="EV APM — Maintenance Decision Support")
alerts: deque = deque(maxlen=BUFFER_SIZE)
sessions: dict[int, deque] = defaultdict(lambda: deque(maxlen=SESSION_BUFFER_SIZE))
stats: dict = {}


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
async def list_alerts(limit: int = 200):
    # async keeps this on the event loop with the POST handler — a sync def
    # would run in the threadpool and race the deque appends.
    return list(islice(reversed(alerts), max(limit, 0)))  # newest first


@app.post("/stats")
async def receive_stats(request: Request):
    stats.clear()
    stats.update(await request.json())
    stats["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"ok": True}


@app.get("/stats")
async def get_stats():
    return stats


@app.post("/sessions")
async def receive_session(request: Request):
    record = await request.json()
    connector = record.get("connector_pk")
    if connector is not None:
        sessions[int(connector)].append(record)
    return {"ok": True}


@app.get("/connectors")
async def list_connectors():
    return [
        {"connector_pk": pk, "sessions": len(history),
         "flagged": sum(1 for r in history if r.get("flagged"))}
        for pk, history in sorted(sessions.items())
    ]


@app.get("/drift/{connector_pk}")
async def drift(connector_pk: int, limit: int = 400):
    history = sessions.get(connector_pk)
    return list(history)[-limit:] if history else []


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>EV APM — Maintenance Decision Support</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 1.2rem; background: #101418; color: #e8eaed; }
  h1 { font-size: 1.15rem; margin: 0 0 .3rem; } h1 small { color: #7a869a; font-weight: normal; }
  #counters { display: flex; gap: .8rem; margin: .8rem 0 1rem; flex-wrap: wrap; }
  .counter { background: #1a2027; border-radius: 8px; padding: .5rem .9rem; min-width: 7.5rem; }
  .counter b { display: block; font-size: 1.3rem; }
  .counter span { color: #7a869a; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
  .counter.p1 b { color: #ff6b6b; } .counter.p2 b { color: #fdcb6e; }
  #coverage { display: flex; gap: .45rem; flex-wrap: wrap; margin: 0 0 1rem; }
  .chip { background: #1a2027; border: 1px solid #2a323d; border-radius: 12px;
          padding: .15rem .6rem; font-size: .74rem; color: #b7c0cc; }
  .chip b { color: #e8eaed; }
  .chip.p1 { border-color: #5c1a1a; } .chip.p2 { border-color: #52400f; }
  #coverage .headline { color: #7a869a; font-size: .78rem; align-self: center; }
  #health { display: flex; gap: .45rem; flex-wrap: wrap; margin: 0 0 .6rem; }
  .health-chip { border-radius: 10px; padding: .18rem .6rem; font-size: .74rem;
                 background: #1a2027; border: 1px solid #2a323d; color: #b7c0cc; }
  .health-chip b { color: #e8eaed; }
  .health-chip.faulted { border-color: #5c1a1a; } .health-chip.faulted i { color: #ff6b6b; }
  .health-chip.atrisk { border-color: #52400f; } .health-chip.atrisk i { color: #fdcb6e; }
  .health-chip.degrading i { color: #74b9ff; } .health-chip.healthy i { color: #2ecc71; }
  .health-chip i { font-style: normal; font-weight: 700; }
  .chip { cursor: pointer; }
  .chip.active { background: #2b6cb0; color: #fff; }
  .chip.active b { color: #fff; }
  #sort-toggle { background: #1a2027; color: #b7c0cc; border: 1px solid #333c47;
                 border-radius: 6px; padding: .2rem .6rem; cursor: pointer;
                 font-size: .74rem; margin-left: .4rem; }
  table { border-collapse: collapse; width: 100%; font-size: .82rem; }
  th, td { padding: .32rem .55rem; text-align: left; border-bottom: 1px solid #262d36; }
  th { color: #7a869a; position: sticky; top: 0; background: #101418; }
  .badge { display: inline-block; padding: .05rem .5rem; border-radius: 10px; font-weight: 700; font-size: .75rem; }
  .badge.P1 { background: #5c1a1a; color: #ff6b6b; }
  .badge.P2 { background: #52400f; color: #fdcb6e; }
  .badge.P3 { background: #2a2f36; color: #9aa4b2; }
  td.signal { color: #b7c0cc; font-style: italic; }
  td.mono { font-family: ui-monospace, monospace; color: #8a94a2; }
  h2 { font-size: .95rem; color: #b7c0cc; margin: 1.4rem 0 .5rem; }
  select { background: #1a2027; color: #e8eaed; border: 1px solid #333c47; border-radius: 6px; padding: .25rem .5rem; }
  #chart-wrap { background: #1a2027; border-radius: 8px; padding: .8rem; margin-top: .5rem; overflow-x: auto; }
  footer { color: #55606d; font-size: .72rem; margin-top: 1.2rem; }
</style>
</head>
<body>
<h1>EV APM — Maintenance Decision Support <small>AI maintenance recommendations for EV charging infrastructure · polling every 2s</small>
  <button id="sort-toggle" title="toggle feed order">sort: priority</button>
</h1>
<div id="counters"></div>
<div id="coverage"></div>

<table>
  <thead><tr>
    <th>maintenance priority</th><th>fired at</th><th>station</th><th>connector</th>
    <th>category</th><th>impact</th><th>recommended action</th><th>deciding signal</th>
  </tr></thead>
  <tbody id="rows"></tbody>
</table>

<h2>Connector health <small>rule table: unresolved P1 in buffer → Faulted ·
P2 or ≥3 drift flags → At-risk · any drift flag → Degrading · else Healthy</small></h2>
<div id="health"></div>

<h2>Per-connector drift <small id="drift-note"></small></h2>
<select id="connector-picker"><option value="">— select connector —</option></select>
<div id="chart-wrap"><svg id="chart" width="860" height="300"></svg></div>

<footer>
  Demo replay speed: set <code>REPLAY_SPEED_MULTIPLIER</code> (0 = instant dump,
  1 = real time, 60 = one minute of history per second) on the replay service
  and re-run <code>docker compose up</code>.
</footer>

<script>
const TIER_ORDER = { P1: 0, P2: 1, P3: 2 };
// dry-run must-fixes: feed order toggle + category filter (click a chip)
let sortMode = 'tier';       // 'tier' | 'newest'
let categoryFilter = null;   // category string or null = all

document.getElementById('sort-toggle').addEventListener('click', () => {
  sortMode = sortMode === 'tier' ? 'newest' : 'tier';
  document.getElementById('sort-toggle').textContent = 'sort: ' + (sortMode === 'tier' ? 'priority' : 'newest');
  poll();
});

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function counter(label, value, cls) {
  const box = el('div', 'counter' + (cls ? ' ' + cls : ''));
  box.append(el('b', null, value), el('span', null, label));
  return box;
}

function category(a) { return (a.fault_category || a.fault_code || a.detector_source || '').replace(/_/g, '-'); }

async function poll() {
  try {
    const [alertsRes, statsRes] = await Promise.all([fetch('/alerts?limit=200'), fetch('/stats')]);
    const all = await alertsRes.json();
    const stats = await statsRes.json();

    if (sortMode === 'tier')
      all.sort((x, y) => (TIER_ORDER[x.priority_tier] ?? 3) - (TIER_ORDER[y.priority_tier] ?? 3)
                      || (y.fired_at || '').localeCompare(x.fired_at || ''));
    else
      all.sort((x, y) => (y.fired_at || '').localeCompare(x.fired_at || ''));
    const visible = categoryFilter ? all.filter(a => category(a) === categoryFilter) : all;

    const rows = document.getElementById('rows');
    rows.replaceChildren();
    for (const a of visible) {
      const tr = el('tr');
      const badge = el('td'); badge.append(Object.assign(el('span', 'badge ' + (a.priority_tier || '')), { textContent: a.priority_tier || '—' }));
      tr.append(badge, el('td', null, a.fired_at),
        el('td', 'mono', a.hashed_charge_box_id ? a.hashed_charge_box_id.slice(0, 10) + '…' : '—'),
        el('td', null, a.physical_plug_id != null ? `plug ${a.physical_plug_id} (pk ${a.connector_pk})` : a.connector_pk),
        el('td', null, category(a)),
        el('td', (a.impact_class || '').startsWith('Safety') ? 'technician-dispatch' :
                 (a.impact_class || '').startsWith('Revenue') ? 'investigate' : '', a.impact_class || '—'),
        el('td', null, a.recommended_action || '—'),
        el('td', 'signal', a.deciding_signal || '—'));
      rows.append(tr);
    }

    const p1 = all.filter(a => a.priority_tier === 'P1').length;
    const p2 = all.filter(a => a.priority_tier === 'P2').length;
    const categories = new Set(all.filter(a => a.detector_source !== 'layer2_drift').map(category));

    // category-coverage panel: one chip per category with count + worst tier
    const rollup = new Map();
    for (const a of all) {
      const key = category(a);
      const entry = rollup.get(key) || { count: 0, worst: 'P3' };
      entry.count++;
      if (a.priority_tier === 'P1' || (a.priority_tier === 'P2' && entry.worst === 'P3'))
        entry.worst = a.priority_tier;
      rollup.set(key, entry);
    }
    const coverage = document.getElementById('coverage');
    coverage.replaceChildren(el('span', 'headline',
      `${rollup.size} of 19 OCPP categories seen in buffer` +
      (categoryFilter ? ` — filtering: ${categoryFilter} (click again to clear)` : ' — click a chip to filter:')));
    for (const [key, entry] of [...rollup].sort((a, b) => b[1].count - a[1].count)) {
      const chip = el('span', 'chip'
        + (entry.worst === 'P1' ? ' p1' : entry.worst === 'P2' ? ' p2' : '')
        + (categoryFilter === key ? ' active' : ''));
      chip.append(el('b', null, key), document.createTextNode(` ×${entry.count}`));
      chip.addEventListener('click', () => {
        categoryFilter = categoryFilter === key ? null : key;
        poll();
      });
      coverage.append(chip);
    }
    const flagRate = stats.sessions_scored
      ? (100 * stats.layer2_flagged / stats.sessions_scored).toFixed(1) + '%' : '—';
    const counters = document.getElementById('counters');
    counters.replaceChildren(
      counter('active P1', p1, 'p1'),
      counter('active P2', p2, 'p2'),
      counter('sessions processed', stats.sessions_closed ?? '—'),
      counter('layer-2 flag rate', flagRate),
      counter('categories detected', categories.size + ' / 19'),
      counter('events', stats.events ?? '—'),
    );
  } catch (err) { /* keep last render on transient poll failure */ }
}

function healthState(c, alertsByConn) {
  const a = alertsByConn.get(c.connector_pk) || {p1: 0, p2: 0, drift: 0};
  if (a.p1 > 0) return ['Faulted', 'faulted'];
  if (a.p2 > 0 || c.flagged >= 3) return ['At-risk', 'atrisk'];
  if (a.drift > 0 || c.flagged > 0) return ['Degrading', 'degrading'];
  return ['Healthy', 'healthy'];
}

async function refreshConnectors() {
  const res = await fetch('/connectors');
  const list = await res.json();
  const alerts = await (await fetch('/alerts?limit=200')).json();
  const byConn = new Map();
  for (const a of alerts) {
    const e = byConn.get(a.connector_pk) || {p1: 0, p2: 0, drift: 0};
    if (a.priority_tier === 'P1') e.p1++;
    if (a.priority_tier === 'P2') e.p2++;
    if (a.detector_source === 'layer2_drift') e.drift++;
    byConn.set(a.connector_pk, e);
  }
  // union: session-bearing connectors + alert-only connectors (the fault
  // segment has recommendations but no session history — it must still
  // appear in the health rollup)
  const known = new Map(list.map(c => [c.connector_pk, c]));
  for (const pk of byConn.keys())
    if (!known.has(pk)) known.set(pk, {connector_pk: pk, sessions: 0, flagged: 0});
  const rollup2 = [...known.values()].map(c => [c, healthState(c, byConn)]);
  const rank = {faulted: 0, atrisk: 1, degrading: 2, healthy: 3};
  rollup2.sort((x, y) => rank[x[1][1]] - rank[y[1][1]] || x[0].connector_pk - y[0].connector_pk);
  const health = document.getElementById('health');
  health.replaceChildren();
  for (const [c, [label, cls]] of rollup2.slice(0, 40)) {
    const chip = el('span', 'health-chip ' + cls);
    chip.append(el('b', null, `${c.connector_pk}`), document.createTextNode(' '));
    chip.append(Object.assign(document.createElement('i'), {textContent: label}));
    health.append(chip);
  }
  if (rollup2.length > 40)
    health.append(el('span', 'headline', `+${rollup2.length - 40} more (worst first)`));
  const picker = document.getElementById('connector-picker');
  const current = picker.value;
  picker.replaceChildren(new Option('— select connector —', ''));
  for (const c of list)
    picker.append(new Option(`connector ${c.connector_pk} (${c.sessions} sessions, ${c.flagged} flagged)`, c.connector_pk));
  picker.value = current;
}

function polyline(points, color, width) {
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  p.setAttribute('points', points.join(' '));
  p.setAttribute('fill', 'none'); p.setAttribute('stroke', color);
  p.setAttribute('stroke-width', width || 1.5);
  return p;
}

function svgText(x, y, text, color) {
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  t.setAttribute('x', x); t.setAttribute('y', y);
  t.setAttribute('fill', color || '#7a869a'); t.setAttribute('font-size', '10');
  t.textContent = text;
  return t;
}

async function drawDrift() {
  const pk = document.getElementById('connector-picker').value;
  const svg = document.getElementById('chart');
  svg.replaceChildren();
  document.getElementById('drift-note').textContent = '';
  if (!pk) return;
  const records = await (await fetch('/drift/' + pk)).json();
  if (!records.length) return;

  const W = 860, H = 300, PAD = 34, midY = 150;
  const n = records.length;
  const x = i => PAD + (W - 2 * PAD) * (n === 1 ? 0.5 : i / (n - 1));

  // top pane: anomaly score per session (higher = healthier)
  const scores = records.map(r => r.anomaly_score ?? 0);
  const sMin = Math.min(...scores, -0.15), sMax = Math.max(...scores, 0.15);
  const sy = v => 12 + (midY - 40) * (1 - (v - sMin) / (sMax - sMin));
  svg.append(polyline(records.map((r, i) => `${x(i)},${sy(r.anomaly_score ?? 0)}`), '#74b9ff'));
  const thr = records[records.length - 1].layer2_threshold;
  if (thr != null) {
    svg.append(polyline([`${PAD},${sy(thr)}`, `${W - PAD},${sy(thr)}`], '#ff6b6b', 1));
    svg.append(svgText(W - PAD - 130, sy(thr) - 4, `threshold ${thr}`, '#ff6b6b'));
  }
  for (let i = 0; i < n; i++) if (records[i].flagged) {
    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', x(i)); dot.setAttribute('cy', sy(records[i].anomaly_score ?? 0));
    dot.setAttribute('r', 3.5); dot.setAttribute('fill', '#ff6b6b');
    svg.append(dot);
  }
  svg.append(svgText(PAD, 12, 'anomaly score per session (dots = flagged)', '#74b9ff'));

  // bottom pane: session duration (minutes)
  const durations = records.map(r => (r.duration_sec ?? 0) / 60);
  const dMax = Math.max(...durations, 1);
  const dy = v => midY + 18 + (H - midY - 34) * (1 - v / dMax);
  svg.append(polyline(records.map((r, i) => `${x(i)},${dy((r.duration_sec ?? 0) / 60)}`), '#2ecc71'));
  svg.append(svgText(PAD, midY + 14, 'session duration (min)', '#2ecc71'));

  document.getElementById('drift-note').textContent =
    `${n} sessions, chronological — ${records.filter(r => r.flagged).length} drift-flagged`;
}

document.getElementById('connector-picker').addEventListener('change', drawDrift);
poll(); refreshConnectors();
setInterval(() => { poll(); refreshConnectors(); drawDrift(); }, 2000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE
