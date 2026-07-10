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
  :root {
    --bg: #070b12; --panel: #0d1420; --panel-2: #101a2b; --line: #1b2740;
    --text: #dce5f2; --muted: #6b7a93; --faint: #46536b;
    --accent: #22d3ee; --p1: #f87171; --p2: #fbbf24; --p3: #8d9aae;
    --ok: #34d399; --drift: #60a5fa;
  }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI Variable Text", "Inter", system-ui, sans-serif;
         margin: 0; background: var(--bg); color: var(--text);
         background-image: radial-gradient(1200px 400px at 70% -10%, #0e1a2e 0%, transparent 60%); }
  b, .num { font-variant-numeric: tabular-nums; }

  /* ── top bar ─────────────────────────────────────────── */
  #topbar { display: flex; align-items: center; gap: .9rem; padding: .65rem 1.2rem;
            border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5;
            background: rgba(7,11,18,.92); backdrop-filter: blur(6px); }
  #brand { display: flex; align-items: baseline; gap: .55rem; }
  #brand b { font-size: 1.02rem; letter-spacing: .02em; }
  #brand b em { font-style: normal; color: var(--accent); }
  #brand small { color: var(--muted); font-size: .74rem; }
  #topbar .spacer { flex: 1; }
  #conn-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint);
              box-shadow: 0 0 6px var(--faint); }
  #conn-dot.live { background: var(--ok); box-shadow: 0 0 8px var(--ok); }
  #conn-dot.down { background: var(--p1); box-shadow: 0 0 8px var(--p1); }
  #conn-label, #clock { color: var(--muted); font-size: .72rem;
                        font-family: ui-monospace, monospace; }
  #sort-toggle { background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
                 border-radius: 6px; padding: .28rem .7rem; cursor: pointer; font-size: .74rem; }
  #sort-toggle:hover { border-color: var(--accent); }

  main { padding: 1rem 1.2rem 2rem; max-width: 1620px; margin: 0 auto; }

  /* ── KPI band ────────────────────────────────────────── */
  #counters { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
              gap: .7rem; margin: .2rem 0 .9rem; }
  .counter { background: linear-gradient(180deg, var(--panel-2), var(--panel));
             border: 1px solid var(--line); border-radius: 10px; padding: .6rem .85rem; }
  .counter b { display: block; font-size: 1.45rem; line-height: 1.25; }
  .counter span { color: var(--muted); font-size: .66rem; text-transform: uppercase;
                  letter-spacing: .09em; }
  .counter.p1 b { color: var(--p1); } .counter.p1 { border-color: #4a1d1d; }
  .counter.p2 b { color: var(--p2); } .counter.p2 { border-color: #4a3a10; }
  .counter.accent b { color: var(--accent); }
  .counter svg { display: block; margin-top: .25rem; }

  /* ── layout grid ─────────────────────────────────────── */
  #grid { display: grid; grid-template-columns: minmax(0, 2.2fr) minmax(280px, 1fr);
          gap: .8rem; align-items: start; }
  @media (max-width: 1000px) { #grid { grid-template-columns: minmax(0, 1fr); } }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
           overflow: hidden; }
  .panel-head { display: flex; align-items: center; gap: .6rem; padding: .55rem .9rem;
                border-bottom: 1px solid var(--line); background: var(--panel-2); }
  .panel-head h2 { font-size: .8rem; margin: 0; color: var(--text); font-weight: 600;
                   text-transform: uppercase; letter-spacing: .08em; }
  .panel-head small { color: var(--muted); font-size: .7rem; font-weight: normal;
                      text-transform: none; letter-spacing: 0; }
  .panel-body { padding: .7rem .9rem; }

  /* ── alert feed ──────────────────────────────────────── */
  #feed-wrap { max-height: 60vh; overflow-y: auto; }
  table { border-collapse: collapse; width: 100%; font-size: .8rem; }
  th, td { padding: .38rem .6rem; text-align: left; border-bottom: 1px solid #141e33; }
  th { color: var(--muted); position: sticky; top: 0; background: var(--panel);
       font-size: .66rem; text-transform: uppercase; letter-spacing: .07em; z-index: 2; }
  tbody tr { border-left: 3px solid transparent; }
  tbody tr:hover { background: #101a2e; }
  tbody tr.t-P1 { border-left-color: var(--p1); }
  tbody tr.t-P2 { border-left-color: var(--p2); }
  tbody tr.t-P3 { border-left-color: #2a3a55; }
  .badge { display: inline-block; padding: .08rem .55rem; border-radius: 999px;
           font-weight: 700; font-size: .72rem; letter-spacing: .03em; }
  .badge.P1 { background: #3d1414; color: var(--p1); border: 1px solid #6b2020; }
  .badge.P2 { background: #3d3010; color: var(--p2); border: 1px solid #6b5518; }
  .badge.P3 { background: #1a2334; color: var(--p3); border: 1px solid #263349; }
  td.signal { color: #9fb0c8; font-style: italic; }
  td.mono { font-family: ui-monospace, monospace; color: #74849c; font-size: .74rem; }
  td .impact-safety { color: var(--p1); font-weight: 600; }
  td .impact-revenue { color: var(--p2); }

  /* ── coverage chips ──────────────────────────────────── */
  #coverage { display: flex; gap: .4rem; flex-wrap: wrap; }
  #coverage .headline { color: var(--muted); font-size: .72rem; width: 100%; margin-bottom: .2rem; }
  .chip { background: var(--panel-2); border: 1px solid var(--line); border-radius: 999px;
          padding: .18rem .65rem; font-size: .73rem; color: #a9b7cb; cursor: pointer;
          transition: border-color .15s; }
  .chip:hover { border-color: var(--accent); }
  .chip b { color: var(--text); }
  .chip.p1 { border-color: #6b2020; } .chip.p2 { border-color: #6b5518; }
  .chip.active { background: #0a3d4d; border-color: var(--accent); color: #d9f6fd; }
  .chip.active b { color: #fff; }

  /* ── connector health ────────────────────────────────── */
  #health { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
            gap: .4rem; }
  .health-chip { border-radius: 8px; padding: .34rem .55rem; font-size: .72rem;
                 background: var(--panel-2); border: 1px solid var(--line); color: #a9b7cb;
                 display: flex; align-items: center; gap: .4rem; }
  .health-chip b { color: var(--text); font-family: ui-monospace, monospace; font-size: .72rem; }
  .health-chip i { font-style: normal; font-weight: 600; font-size: .68rem; margin-left: auto; }
  .health-chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%;
                         background: var(--faint); flex: none; }
  .health-chip.faulted { border-color: #6b2020; } .health-chip.faulted i { color: var(--p1); }
  .health-chip.faulted::before { background: var(--p1); box-shadow: 0 0 6px var(--p1); }
  .health-chip.atrisk { border-color: #6b5518; } .health-chip.atrisk i { color: var(--p2); }
  .health-chip.atrisk::before { background: var(--p2); }
  .health-chip.degrading i { color: var(--drift); }
  .health-chip.degrading::before { background: var(--drift); }
  .health-chip.healthy i { color: var(--ok); }
  .health-chip.healthy::before { background: var(--ok); }
  #health-more { color: var(--muted); font-size: .7rem; padding: .3rem 0 0; }

  /* ── drift + telemetry row ───────────────────────────── */
  #lower { display: grid; grid-template-columns: minmax(0, 2.2fr) minmax(280px, 1fr);
           gap: .8rem; margin-top: .8rem; align-items: start; }
  @media (max-width: 1000px) { #lower { grid-template-columns: minmax(0, 1fr); } }
  select { background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
           border-radius: 6px; padding: .3rem .55rem; font-size: .78rem; max-width: 100%; }
  #chart-wrap { overflow-x: auto; }
  #chart-wrap svg, #wave { display: block; }
  .sim-badge { background: #33240a; color: var(--p2); border: 1px solid #6b5518;
               border-radius: 999px; padding: .1rem .55rem; font-size: .66rem;
               font-weight: 700; letter-spacing: .06em; }
  #wave-note { color: var(--muted); font-size: .7rem; margin-top: .4rem; line-height: 1.45; }

  footer { color: var(--faint); font-size: .72rem; margin-top: 1.1rem; padding: 0 .2rem; }
  code { background: var(--panel-2); border: 1px solid var(--line); border-radius: 4px;
         padding: 0 .3rem; font-size: .95em; }
</style>
</head>
<body>
<div id="topbar">
  <div id="brand"><b><em>EV APM</em> — Maintenance Decision Support</b>
    <small>AI maintenance recommendations for EV charging infrastructure · polling every 2s</small></div>
  <div class="spacer"></div>
  <span id="conn-dot" title="pipeline link"></span><span id="conn-label">connecting…</span>
  <span id="clock" class="num"></span>
  <button id="sort-toggle" title="toggle feed order">sort: priority</button>
</div>

<main>
<div id="counters"></div>

<div id="grid">
  <div class="panel">
    <div class="panel-head"><h2>Maintenance queue</h2>
      <small>prioritized recommendations — P1 dispatch · P2 schedule · P3 log</small></div>
    <div id="feed-wrap">
      <table>
        <thead><tr>
          <th>maintenance priority</th><th>fired at</th><th>station</th><th>connector</th>
          <th>category</th><th>impact</th><th>recommended action</th><th>deciding signal</th>
        </tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </div>

  <div style="display:flex; flex-direction:column; gap:.8rem; min-width:0;">
    <div class="panel">
      <div class="panel-head"><h2>Category coverage</h2></div>
      <div class="panel-body"><div id="coverage"></div></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Connector health</h2>
        <small>unresolved P1 → Faulted · P2 or ≥3 drift flags → At-risk ·
        any drift flag → Degrading · else Healthy</small></div>
      <div class="panel-body"><div id="health"></div><div id="health-more"></div></div>
    </div>
  </div>
</div>

<div id="lower">
  <div class="panel">
    <div class="panel-head"><h2>Per-connector drift</h2>
      <small id="drift-note"></small>
      <div class="spacer" style="flex:1"></div>
      <select id="connector-picker"><option value="">— select connector —</option></select>
    </div>
    <div class="panel-body" id="chart-wrap"><svg id="chart" width="860" height="300"></svg></div>
  </div>

  <div class="panel">
    <div class="panel-head"><h2>Telemetry preview</h2>
      <span class="sim-badge">SIMULATED</span></div>
    <div class="panel-body">
      <svg id="wave" width="100%" height="180" viewBox="0 0 420 180" preserveAspectRatio="none"></svg>
      <div id="wave-note">Illustrative waveform only — supply voltage (~227&nbsp;V nominal)
      and active power for a hypothetical session. Real per-sample measurand streams are not
      in the delivered exports (audit flags 11/20/26); no detection logic reads this panel.</div>
    </div>
  </div>
</div>

<footer>
  Demo replay speed: set <code>REPLAY_SPEED_MULTIPLIER</code> (0 = instant dump,
  1 = real time, 60 = one minute of history per second) on the replay service
  and re-run <code>docker compose up</code>.
</footer>
</main>

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

    setLink(true);
    const rows = document.getElementById('rows');
    rows.replaceChildren();
    for (const a of visible) {
      const tr = el('tr', a.priority_tier ? 't-' + a.priority_tier : null);
      const badge = el('td'); badge.append(Object.assign(el('span', 'badge ' + (a.priority_tier || '')), { textContent: a.priority_tier || '—' }));
      const impact = el('td');
      impact.append(el('span', (a.impact_class || '').startsWith('Safety') ? 'impact-safety' :
                            (a.impact_class || '').startsWith('Revenue') ? 'impact-revenue' : '',
                       a.impact_class || '—'));
      tr.append(badge, el('td', 'num', a.fired_at),
        el('td', 'mono', a.hashed_charge_box_id ? a.hashed_charge_box_id.slice(0, 10) + '…' : '—'),
        el('td', null, a.physical_plug_id != null ? `plug ${a.physical_plug_id} (pk ${a.connector_pk})` : a.connector_pk),
        el('td', null, category(a)),
        impact,
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
      counter('layer-2 flag rate', flagRate, 'accent'),
      counter('categories detected', categories.size + ' / 19'),
      inflowCard(all),
    );
  } catch (err) { setLink(false); /* keep last render on transient poll failure */ }
}

function setLink(up) {
  const dot = document.getElementById('conn-dot');
  dot.className = up ? 'live' : 'down';
  document.getElementById('conn-label').textContent = up ? 'pipeline link' : 'link lost';
}

// alert-inflow card: bucket buffered alerts by fired_at minute, render a sparkline
function inflowCard(all) {
  const box = counter('alert inflow (buffer)', String(all.length));
  const minutes = new Map();
  for (const a of all) {
    const m = (a.fired_at || '').slice(0, 16);
    if (m) minutes.set(m, (minutes.get(m) || 0) + 1);
  }
  const series = [...minutes.keys()].sort().map(k => minutes.get(k)).slice(-40);
  if (series.length > 1) {
    const W = 120, H = 22, max = Math.max(...series);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', W); svg.setAttribute('height', H);
    svg.append(polyline(series.map((v, i) =>
      `${(W - 2) * i / (series.length - 1) + 1},${H - 2 - (H - 4) * v / max}`), '#22d3ee', 1.2));
    box.append(svg);
  }
  return box;
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
  document.getElementById('health-more').textContent =
    rollup2.length > 40 ? `+${rollup2.length - 40} more (worst first)` : '';
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
  const hint = msg => svg.append(svgText(20, 30, msg, '#46536b'));
  if (!pk) { hint('select a connector to plot its per-session anomaly-score trend'); return; }
  const records = await (await fetch('/drift/' + pk)).json();
  if (!records.length) { hint('no scored sessions yet for this connector'); return; }

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

// ── simulated telemetry preview (illustrative only — see panel note) ──
const WAVE_N = 140;
const waveV = [], waveP = [];
let waveT = 0;
function waveTick() {
  waveT += 1;
  // supply voltage: 227 V nominal with sensor-grade jitter
  waveV.push(227 + Math.sin(waveT / 9) * 1.4 + (Math.random() - 0.5) * 1.6);
  // active power: session ramp-plateau-taper cycle, ~0–22 kW
  const phase = (waveT % 260) / 260;
  const envelope = phase < 0.12 ? phase / 0.12 : phase < 0.7 ? 1 : Math.max(0, (0.92 - phase) / 0.22);
  waveP.push(Math.max(0, 22 * envelope + (Math.random() - 0.5) * 0.7));
  if (waveV.length > WAVE_N) { waveV.shift(); waveP.shift(); }

  const svg = document.getElementById('wave');
  const W = 420, H = 180, PAD = 6;
  const x = i => PAD + (W - 2 * PAD) * i / (WAVE_N - 1);
  svg.replaceChildren();
  // voltage pane (top): fixed 215–240 V window
  const vy = v => 12 + 64 * (1 - (v - 215) / 25);
  svg.append(polyline(waveV.map((v, i) => `${x(i)},${vy(v)}`), '#fbbf24', 1.3));
  svg.append(svgText(PAD + 2, 10, 'supply voltage (V) — simulated', '#fbbf24'));
  // power pane (bottom): 0–24 kW
  const py = v => 96 + 76 * (1 - v / 24);
  svg.append(polyline(waveP.map((v, i) => `${x(i)},${py(v)}`), '#22d3ee', 1.3));
  svg.append(svgText(PAD + 2, 92, 'active power (kW) — simulated', '#22d3ee'));
}

function tickClock() {
  document.getElementById('clock').textContent =
    new Date().toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
}

document.getElementById('connector-picker').addEventListener('change', drawDrift);
poll(); refreshConnectors(); tickClock();
for (let i = 0; i < WAVE_N; i++) waveTick();
setInterval(() => { poll(); refreshConnectors(); drawDrift(); }, 2000);
setInterval(waveTick, 350);
setInterval(tickClock, 1000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE
