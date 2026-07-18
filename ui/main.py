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
    /* Direction A — industrial control-room dark. One navy surface ramp,
       one signature accent, signal colors calibrated for projector chroma
       (owned values, not framework defaults). */
    --bg: #05080f; --panel: #0b1220; --panel-2: #111a2c; --line: #1c2a44;
    --rule: #16203a;            /* hairline row rules inside panels */
    --hover: #131f36;
    --text: #e2e9f4; --muted: #8b99b3;
    --faint: #78869f;           /* 5.0:1 on --panel — was #59677f at 2.6:1 */
    --accent: #3fe0c8; --accent-wash: #0a3b38;
    --p1: #ff5c49; --p1-wash: #3a1310; --p1-edge: #7a2a20;
    --p2: #ffb020; --p2-wash: #382a0c; --p2-edge: #77571a;
    --p3: #93a1b7; --p3-wash: #17202f; --p3-edge: #2a3850;
    --ok: #2fd48c; --drift: #5aa2ff;
    /* 3-step radius scale (+ pill); was 6/8/10/12/999 mixed */
    --r-sm: 6px; --r-md: 10px; --r-lg: 14px;
  }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI Variable Text", "Inter", system-ui, sans-serif;
         margin: 0; background: var(--bg); color: var(--text);
         background-image: radial-gradient(1200px 400px at 70% -10%, #0d1729 0%, transparent 60%); }
  b, .num { font-variant-numeric: tabular-nums; }
  td.num { white-space: nowrap; }

  /* ── top bar ─────────────────────────────────────────── */
  #topbar { display: flex; align-items: center; gap: .8rem; padding: .65rem 1.2rem;
            border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5;
            background: rgba(5,8,15,.92); backdrop-filter: blur(6px); }
  #topbar > span, #topbar b { white-space: nowrap; }
  @media (max-width: 1560px) { #brand small { display: none; } }
  #brand { display: flex; align-items: center; gap: .6rem; }
  #brand svg { flex: none; display: block; }
  #brand b { font-size: 1.05rem; font-weight: 650; letter-spacing: .01em;
             white-space: nowrap; }
  #brand b em { font-style: normal; color: var(--accent); letter-spacing: .05em; }
  #brand small { color: var(--muted); font-size: .72rem; }
  #topbar .spacer { flex: 1; }
  #conn-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint);
              box-shadow: 0 0 6px var(--faint); }
  #conn-dot.live { background: var(--ok); box-shadow: 0 0 8px var(--ok); }
  #conn-dot.down { background: var(--p1); box-shadow: 0 0 8px var(--p1); }
  #conn-label, #clock { color: var(--muted); font-size: .72rem;
                        font-family: ui-monospace, monospace; }
  #thru { color: var(--ok); font-size: .7rem; font-family: ui-monospace, monospace; }
  #thru.idle { color: var(--faint); }
  #evt-time { color: var(--text); font-size: .76rem; font-family: ui-monospace, monospace; }
  #evt-time small, #clock small { color: var(--faint); font-size: .62rem;
                                  letter-spacing: .06em; margin-right: .25rem; }
  #sort-toggle { background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
                 border-radius: var(--r-sm); padding: .28rem .7rem; cursor: pointer; font-size: .75rem; }
  #sort-toggle:hover { border-color: var(--accent); }

  main { padding: 1.2rem 1.2rem 2.4rem; max-width: 1620px; margin: 0 auto; }

  /* ── KPI band — type scale steps .72 / .8 / .95 / 1.5 / 2.4rem;
       the Active-P1 count is the loudest thing on the screen ── */
  #counters { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
              gap: .8rem; margin: 0 0 1.2rem; align-items: stretch; }
  .counter { background: linear-gradient(180deg, var(--panel-2), var(--panel));
             border: 1px solid var(--line); border-radius: var(--r-md);
             padding: .65rem .85rem; display: flex; flex-direction: column;
             justify-content: flex-end; }
  .counter b { display: block; font-size: 1.5rem; font-weight: 650; line-height: 1.15; }
  .counter span { color: var(--muted); font-size: .72rem; text-transform: uppercase;
                  letter-spacing: .09em; }
  .counter.p1 { border-color: var(--p1-edge);
                background: linear-gradient(180deg, #24100d, var(--panel)); }
  .counter.p1 b { color: var(--p1); font-size: 2.4rem; }
  .counter.p2 { border-color: var(--p2-edge); }
  .counter.p2 b { color: var(--p2); font-size: 1.9rem; }
  .counter.accent b { color: var(--accent); }
  .counter svg { display: block; margin-top: .25rem; }

  /* ── layout grid ─────────────────────────────────────── */
  #grid { display: grid; grid-template-columns: minmax(0, 2.2fr) minmax(280px, 1fr);
          gap: .8rem; align-items: start; }
  @media (max-width: 1000px) { #grid { grid-template-columns: minmax(0, 1fr); } }
  .panel { background: var(--panel); border: 1px solid var(--line);
           border-radius: var(--r-lg); overflow: hidden; }
  .panel-head { display: flex; align-items: center; gap: .6rem; padding: .55rem .9rem;
                min-height: 2.5rem; border-bottom: 1px solid var(--line);
                background: var(--panel-2); }
  .panel-head h2 { font-size: .8rem; margin: 0; color: var(--text); font-weight: 650;
                   text-transform: uppercase; letter-spacing: .08em; }
  .panel-head small { color: var(--muted); font-size: .72rem; font-weight: normal;
                      text-transform: none; letter-spacing: 0; }
  .panel-body { padding: .8rem .9rem; }

  /* ── alert feed ──────────────────────────────────────── */
  #feed-wrap { max-height: 60vh; overflow-y: auto; }
  table { border-collapse: collapse; width: 100%; font-size: .8rem; }
  th, td { padding: .5rem .65rem; text-align: left; border-bottom: 1px solid var(--rule); }
  th { color: var(--muted); position: sticky; top: 0; background: var(--panel);
       font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; z-index: 2; }
  tbody tr { border-left: 3px solid transparent; }
  tbody tr:hover { background: var(--hover); }
  tbody tr.t-P1 { border-left-color: var(--p1); }
  tbody tr.t-P2 { border-left-color: var(--p2); }
  tbody tr.t-P3 { border-left-color: #52627e; }
  @keyframes p1pulse { from { background: var(--p1-wash); } to { background: transparent; } }
  tbody tr.flash { animation: p1pulse 1.6s ease-out 1; }
  tbody tr.alert-row { cursor: pointer; }
  tbody tr.open { background: var(--hover); }
  tr.trace-row td { background: #0a1120; border-left: 3px solid var(--accent);
                    padding: .65rem 1rem .75rem; cursor: default; }
  .trace-title { color: var(--accent); font-size: .72rem; font-weight: 700;
                 text-transform: uppercase; letter-spacing: .09em; margin-bottom: .45rem; }
  .trace { display: grid; grid-template-columns: max-content 1fr; gap: .3rem .8rem;
           font-size: .8rem; }
  .trace dt { color: var(--muted); font-size: .72rem; text-transform: uppercase;
              letter-spacing: .07em; padding-top: .05rem; white-space: nowrap; }
  .trace dd { margin: 0; color: #ccd7e6; line-height: 1.45; }
  .trace dd b { color: var(--text); }
  .trace dd.conclusion { color: #a5b3c9; font-style: italic; }
  .trace-foot { color: var(--faint); font-size: .72rem; margin-top: .5rem; }
  .badge { display: inline-block; padding: .08rem .55rem; border-radius: 999px;
           font-weight: 700; font-size: .72rem; letter-spacing: .03em; }
  .badge.P1 { background: var(--p1-wash); color: var(--p1); border: 1px solid var(--p1-edge); }
  .badge.P2 { background: var(--p2-wash); color: var(--p2); border: 1px solid var(--p2-edge); }
  .badge.P3 { background: var(--p3-wash); color: var(--p3); border: 1px solid var(--p3-edge); }
  td.signal { color: #a5b3c9; font-style: italic; max-width: 280px;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  td.action { font-weight: 650; color: #eef4fb; font-size: .85rem; }
  .stn { display: block; font-family: ui-monospace, monospace; color: var(--faint);
         font-size: .72rem; margin-top: .12rem; }
  .imp { display: inline-block; padding: .08rem .5rem; border-radius: 999px;
         font-size: .72rem; font-weight: 600; border: 1px solid; white-space: nowrap; }
  .imp.safety { background: var(--p1-wash); color: var(--p1); border-color: var(--p1-edge); }
  .imp.revenue { background: var(--p2-wash); color: var(--p2); border-color: var(--p2-edge); }
  .imp.transient { background: var(--p3-wash); color: var(--p3); border-color: var(--p3-edge); }

  /* ── coverage: fraction bar + seen row + not-yet-observed row ── */
  #coverage .headline { display: flex; align-items: center; gap: .6rem;
                        color: var(--muted); font-size: .72rem; margin-bottom: .5rem; }
  .cov-bar { flex: 1; height: 5px; min-width: 60px; background: var(--rule);
             border-radius: 999px; overflow: hidden; }
  .cov-bar i { display: block; height: 100%; background: var(--accent); }
  .cov-row { display: flex; gap: .4rem; flex-wrap: wrap; }
  .cov-unseen-label { color: var(--faint); font-size: .72rem;
                      margin: .6rem 0 .3rem; text-transform: uppercase;
                      letter-spacing: .07em; }
  .chip { background: var(--panel-2); border: 1px solid var(--line); border-radius: 999px;
          padding: .18rem .65rem; font-size: .75rem; color: #aebcd1; cursor: pointer;
          transition: border-color .15s; }
  .chip:hover { border-color: var(--accent); }
  .chip b { color: var(--text); }
  .chip.p1 { border-color: var(--p1-edge); } .chip.p2 { border-color: var(--p2-edge); }
  .chip.active { background: var(--accent-wash); border-color: var(--accent); color: #d8fbf4; }
  .chip.active b { color: #fff; }
  .chip.dim { opacity: .45; cursor: default; border-style: dashed; }
  .chip.dim:hover { border-color: var(--line); }

  /* ── connector health ────────────────────────────────── */
  #health { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
            gap: .45rem; }
  .health-chip { border-radius: var(--r-md); padding: .34rem .55rem; font-size: .75rem;
                 background: var(--panel-2); border: 1px solid var(--line); color: #aebcd1;
                 display: flex; align-items: center; gap: .4rem; cursor: pointer;
                 transition: border-color .15s; }
  .health-chip:hover { border-color: var(--accent); }
  .health-chip.selected { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
  .health-chip b { color: var(--text); font-family: ui-monospace, monospace; font-size: .75rem; }
  .health-chip i { font-style: normal; font-weight: 600; font-size: .72rem; margin-left: auto; }
  .health-chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%;
                         background: var(--faint); flex: none; }
  .health-chip.faulted { border-color: var(--p1-edge); } .health-chip.faulted i { color: var(--p1); }
  .health-chip.faulted::before { background: var(--p1); box-shadow: 0 0 6px var(--p1); }
  .health-chip.atrisk { border-color: var(--p2-edge); } .health-chip.atrisk i { color: var(--p2); }
  .health-chip.atrisk::before { background: var(--p2); }
  .health-chip.degrading i { color: var(--drift); }
  .health-chip.degrading::before { background: var(--drift); }
  .health-chip.healthy i { color: var(--ok); }
  .health-chip.healthy::before { background: var(--ok); }
  #health-more { color: var(--muted); font-size: .7rem; padding: .3rem 0 0; }

  /* ── drift row ───────────────────────────────────────── */
  #lower { margin-top: 1.2rem; }
  select { background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
           border-radius: var(--r-sm); padding: .3rem .55rem; font-size: .8rem; max-width: 100%; }
  #chart-wrap { overflow-x: auto; }
  #chart-wrap svg { display: block; width: 100%; height: auto; }

  footer { color: var(--faint); font-size: .72rem; margin-top: 1.2rem; padding: 0 .2rem; }
  code { background: var(--panel-2); border: 1px solid var(--line); border-radius: var(--r-sm);
         padding: 0 .3rem; font-size: .95em; }
</style>
</head>
<body>
<div id="topbar">
  <div id="brand">
    <svg width="21" height="21" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="none" stroke="var(--line)" stroke-width="1.6"/>
      <path d="M13.2 3.8 7.6 13h3.8l-1 7.2L16.4 11h-3.8z" fill="var(--accent)"/>
    </svg>
    <b><em>EV APM</em> — Maintenance Decision Support</b>
    <small>AI maintenance recommendations for EV charging infrastructure · polling every 2s</small></div>
  <div class="spacer"></div>
  <span id="conn-dot" title="pipeline link"></span><span id="conn-label">connecting…</span>
  <span id="thru"></span>
  <span id="evt-time" class="num" title="timestamp of the newest event in the replayed stream"><small>EVENT</small>—</span>
  <span id="clock" class="num" title="wall clock (UTC)"></span>
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
          <th>maintenance priority</th><th>fired at</th><th>connector · station</th>
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
    <div class="panel-body" id="chart-wrap"><svg id="chart" viewBox="0 0 1560 380" preserveAspectRatio="xMidYMid meet"></svg></div>
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
let openTraceKey = null;     // row whose decision trace is expanded (survives re-render)

function rowKey(a) { return `${a.fired_at}|${a.connector_pk}|${category(a)}`; }

// "May 16 · 15:00:00" for the queue column; the full ISO stays in the title
// attribute — display formatting only, zero information loss
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function firedAtLabel(iso) {
  const m = (iso || '').match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  return m ? `${MONTHS[+m[2] - 1]} ${+m[3]} · ${m[4]}` : (iso || '—');
}

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

function category(a) {
  // plain-language display name; the model-drift source keeps no internal jargon
  const raw = a.fault_category || a.fault_code
    || (a.detector_source === 'layer2_drift' ? 'session-drift' : a.detector_source) || '';
  return raw.replace(/_/g, '-');
}

// ── Decision trace: renders the recorded rule chain for one alert, built
// entirely from fields already on the payload. No live reasoning, no model —
// it reads back the deterministic logic that produced the recommendation.
function traceRow(a) {
  const isDrift = a.detector_source === 'layer2_drift';
  const detected = isDrift
    ? `session-profile drift — likely (anomaly score ${a.anomaly_score ?? '—'}`
      + (a.confidence != null ? `, ${a.confidence}% confidence)` : ')')
    : `${category(a)} signature — certain (rule match)`;

  // the deciding_signal is the prioritizer's own record: base rule first,
  // then any escalations it appended, ';'-joined. Parse, don't recompute.
  const clauses = (a.deciding_signal || '').split(';').map(s => s.trim()).filter(Boolean);
  const base = clauses[0] || '—';
  const escalations = clauses.slice(1);

  const dl = el('dl', 'trace');
  const pair = (term, text, cls) => {
    dl.append(el('dt', null, term));
    dl.append(el('dd', cls || null, text));
  };
  const pairNode = (term, node) => { dl.append(el('dt', null, term)); dl.append(node); };

  pair('Detected', detected + (a.mechanism ? ` — ${a.mechanism}` : ''));
  if (a.likely_root_cause) pair('Likely cause', a.likely_root_cause);
  // labeled "deciding rule", not "base rule": two prioritizer escalations
  // (drift streak, weak-signal burst) REPLACE the recorded signal rather than
  // appending, so the first clause is whichever rule actually decided
  pair('Deciding rule', base);

  // self-recovery check is the flagship rule — spell it out for err1051 from
  // the recovery_seconds field and the documented 15s transient window. Only
  // the final alert carries a recovery verdict; a candidate is still awaiting
  // one, so its Priority-rule line ("awaiting recovery") already says so.
  if (category(a) === 'err1051' && a.stage === 'final') {
    const r = a.recovery_seconds;
    pair('Self-recovery check',
      r == null ? 'no recovery observed in the window → technician dispatched'
      : r <= 15 ? `recovered in ${Math.round(r)}s — within the 15-second transient window, so downgraded to log-only`
      : `recovery took ${Math.round(r)}s — beyond the 15-second transient window, so a technician is dispatched`);
  }

  if (escalations.length) {
    const ul = el('dd');
    for (const esc of escalations) ul.append(el('div', null, '• ' + esc));
    pairNode('Escalations applied', ul);
  }

  pair('Recommendation',
    `${a.priority_tier || '—'} → ${a.recommended_action || '—'} · ${a.impact_class || '—'}`);
  pair('Conclusion', a.deciding_signal || '—', 'conclusion');

  // one-sentence readability layer, composed verbatim from the fields above —
  // deterministic string assembly, nothing generated
  const summary = `${category(a)}: ${base}`
    + (escalations.length ? `; then ${escalations.join('; ')}` : '')
    + ` — so the system filed it ${a.priority_tier || '—'}`
    + (a.recommended_action ? ` (${a.recommended_action.toLowerCase()})` : '') + '.';
  pair('In short', summary);

  const cell = el('td');
  cell.colSpan = 7;
  cell.append(el('div', 'trace-title', 'Why this recommendation'), dl,
    el('div', 'trace-foot',
      'Recorded decision logic — deterministic rules and lookups; the summary '
      + 'restates the fields above, nothing is generated.'));
  const tr = el('tr', 'trace-row');
  tr.append(cell);
  return tr;
}

// new-P1 arrival cue: one subtle background pulse per newly seen P1 row
const seenP1 = new Set();
let firstPollDone = false;

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

    setLink(true, stats);
    const rows = document.getElementById('rows');
    rows.replaceChildren();
    for (const a of visible) {
      const key = rowKey(a);
      const tr = el('tr', (a.priority_tier ? 't-' + a.priority_tier : '') + ' alert-row'
        + (key === openTraceKey ? ' open' : ''));
      if (a.priority_tier === 'P1' && firstPollDone && !seenP1.has(key)) tr.classList.add('flash');
      if (a.priority_tier === 'P1') seenP1.add(key);
      const badge = el('td'); badge.append(Object.assign(el('span', 'badge ' + (a.priority_tier || '')), { textContent: a.priority_tier || '—' }));
      // connector cell with the station hash as a caption underneath — keeps
      // multi-station visibility without spending a whole column on it
      const conn = el('td', null,
        a.physical_plug_id != null ? `plug ${a.physical_plug_id} (pk ${a.connector_pk})` : String(a.connector_pk));
      if (a.hashed_charge_box_id) conn.append(el('span', 'stn', a.hashed_charge_box_id.slice(0, 10) + '…'));
      const impact = el('td');
      impact.append(el('span', 'imp ' + ((a.impact_class || '').startsWith('Safety') ? 'safety' :
                                         (a.impact_class || '').startsWith('Revenue') ? 'revenue' : 'transient'),
                       a.impact_class || '—'));
      const signal = el('td', 'signal', a.deciding_signal || '—');
      signal.title = a.deciding_signal || '';
      const fired = el('td', 'num', firedAtLabel(a.fired_at));
      fired.title = a.fired_at || '';
      tr.append(badge, fired, conn,
        el('td', null, category(a)),
        impact,
        el('td', 'action', a.recommended_action || '—'),
        signal);
      tr.title = 'click for the decision trace';
      tr.addEventListener('click', () => {
        openTraceKey = openTraceKey === key ? null : key;
        poll();
      });
      rows.append(tr);
      if (key === openTraceKey) rows.append(traceRow(a));
    }
    firstPollDone = true;

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
    const ocppSeen = rollup.size - (rollup.has('session-drift') ? 1 : 0);
    // headline: the fraction stated AND drawn (small bar), plus the filter hint
    const headline = el('div', 'headline');
    const bar = el('span', 'cov-bar');
    const fill = document.createElement('i');
    fill.style.width = `${Math.round(100 * Math.min(ocppSeen, 19) / 19)}%`;
    bar.append(fill);
    headline.append(
      el('span', null, `${ocppSeen} of 19 OCPP categories seen in buffer`),
      bar,
      el('span', null, categoryFilter
        ? `filtering: ${categoryFilter} (click again to clear)`
        : 'click a chip to filter'));
    coverage.replaceChildren(headline);
    // seen chips, worst tier first, then by volume
    const TIER_RANK = { P1: 0, P2: 1, P3: 2 };
    const seenRow = el('div', 'cov-row');
    for (const [key, entry] of [...rollup].sort((x, y) =>
        (TIER_RANK[x[1].worst] ?? 3) - (TIER_RANK[y[1].worst] ?? 3)
        || y[1].count - x[1].count)) {
      const chip = el('span', 'chip'
        + (entry.worst === 'P1' ? ' p1' : entry.worst === 'P2' ? ' p2' : '')
        + (categoryFilter === key ? ' active' : ''));
      chip.append(el('b', null, key), document.createTextNode(` ×${entry.count}`));
      chip.addEventListener('click', () => {
        categoryFilter = categoryFilter === key ? null : key;
        poll();
      });
      seenRow.append(chip);
    }
    coverage.append(seenRow);
    // the 19 observed categories = distinct error_code values in the fleet's
    // committed taxonomy (data/reference/error_taxonomy.csv). err-code and
    // silence signals ride under OtherError in the real schema, so a seen
    // err1051/err1024/telemetry-silence marks OtherError as covered.
    const OCPP19 = ['ConnectorLockFailure', 'EVCommunicationError', 'GroundFailure',
      'HighTemperature', 'InternalError', 'LocalListConflict', 'NoError', 'OtherError',
      'OverCurrentFailure', 'OverVoltage', 'PowerMeterFailure', 'PowerSwitchFailure',
      'ReaderFailure', 'ResetFailure', 'UnderVoltage', 'WeakSignal',
      'Available after Finishing Status', 'Transaction Stopped', 'Websocket Disconnected'];
    const covered = new Set(rollup.keys());
    if (['err1051', 'err1024', 'telemetry-silence'].some(k => covered.has(k)))
      covered.add('OtherError');
    const unseen = OCPP19.filter(cat => !covered.has(cat));
    if (unseen.length) {
      coverage.append(el('div', 'cov-unseen-label', 'not yet observed in this stream'));
      const dimRow = el('div', 'cov-row');
      for (const cat of unseen) {
        const chip = el('span', 'chip dim');
        chip.title = 'in the fleet taxonomy, not yet observed in this stream';
        chip.append(el('b', null, cat));
        dimRow.append(chip);
      }
      coverage.append(dimRow);
    }
    // validated on the chronological held-out split: 3.62% (n=2,015 normal
    // sessions, notebook 04) — the number documented in docs/category_metrics.md
    // and docs/detailed_document.md §6. Static by design: it is the evaluated
    // model number, not a live counter.
    const finals = all.filter(a => a.detector_source !== 'layer2_drift' && a.stage !== 'candidate');
    const cleared = finals.filter(a => (a.deciding_signal || '').startsWith('self-recovered')).length;
    const autoClear = finals.length ? Math.round(100 * cleared / finals.length) + '%' : '—';
    const counters = document.getElementById('counters');
    counters.replaceChildren(
      counter('active P1', p1, 'p1'),
      counter('active P2', p2, 'p2'),
      counter('sessions processed', stats.sessions_closed ?? '—'),
      counter('false-alarm rate (validated)', '3.62%', 'accent'),
      counter('categories detected', categories.size + ' / 19'),
      counter('faults self-cleared, logged only', autoClear),
    );

    // replay-simulated "now": the newest event timestamp in the stream
    const newest = all.reduce((m, a) => (a.fired_at || '') > m ? a.fired_at : m, '');
    const evt = document.getElementById('evt-time');
    evt.replaceChildren(Object.assign(document.createElement('small'), {textContent: 'EVENT'}),
      document.createTextNode(newest ? newest.slice(0, 19).replace('T', ' ') : '—'));
  } catch (err) { setLink(false); /* keep last render on transient poll failure */ }
}

let lastEvents = null, lastEventsAt = 0, lastChangeAt = 0;
function setLink(up, stats) {
  const dot = document.getElementById('conn-dot');
  dot.className = up ? 'live' : 'down';
  document.getElementById('conn-label').textContent = up ? 'pipeline link' : 'link lost';
  const thru = document.getElementById('thru');
  if (!up || !stats || stats.events == null) { thru.textContent = ''; return; }
  const now = Date.now();
  if (lastEvents != null && stats.events > lastEvents) {
    const rate = (stats.events - lastEvents) / Math.max((now - lastEventsAt) / 1000, 0.001);
    thru.textContent = `live · ${rate >= 10 ? Math.round(rate) : rate.toFixed(1)} events/s`;
    thru.className = '';
    lastChangeAt = now;
  } else if (now - lastChangeAt > 6000) {
    thru.textContent = 'stream idle';
    thru.className = 'idle';
  }
  if (lastEvents !== stats.events) { lastEvents = stats.events; lastEventsAt = now; }
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
  const picker = document.getElementById('connector-picker');
  const current = picker.value;
  picker.replaceChildren(new Option('— select connector —', ''));
  for (const c of list)
    picker.append(new Option(`connector ${c.connector_pk} (${c.sessions} sessions, ${c.flagged} flagged)`, c.connector_pk));
  picker.value = current;

  // default the drift panel to the most demo-relevant connector: worst
  // health state first (At-risk preferred), among connectors that actually
  // have session history to plot.
  if (!picker.value) {
    const pref = {atrisk: 0, degrading: 1, faulted: 2, healthy: 3};
    const candidates = rollup2.filter(([c]) => c.sessions > 0)
      .sort((x, y) => pref[x[1][1]] - pref[y[1][1]]
                   || y[0].flagged - x[0].flagged || y[0].sessions - x[0].sessions);
    if (candidates.length) { picker.value = candidates[0][0].connector_pk; drawDrift(); }
  }

  const health = document.getElementById('health');
  health.replaceChildren();
  for (const [c, [label, cls]] of rollup2.slice(0, 40)) {
    const chip = el('span', 'health-chip ' + cls
      + (String(c.connector_pk) === picker.value ? ' selected' : ''));
    chip.title = 'show this connector in the degradation panel';
    chip.append(el('b', null, `${c.connector_pk}`), document.createTextNode(' '));
    chip.append(Object.assign(document.createElement('i'), {textContent: label}));
    chip.addEventListener('click', () => {
      picker.value = String(c.connector_pk);
      drawDrift();
      refreshConnectors();
    });
    health.append(chip);
  }
  document.getElementById('health-more').textContent =
    rollup2.length > 40 ? `+${rollup2.length - 40} more (worst first)` : '';
}

const SVG_NS = 'http://www.w3.org/2000/svg';

function polyline(points, color, width) {
  const p = document.createElementNS(SVG_NS, 'polyline');
  p.setAttribute('points', points.join(' '));
  p.setAttribute('fill', 'none'); p.setAttribute('stroke', color);
  p.setAttribute('stroke-width', width || 1.5);
  return p;
}

function svgText(x, y, text, color, size, anchor) {
  const t = document.createElementNS(SVG_NS, 'text');
  t.setAttribute('x', x); t.setAttribute('y', y);
  t.setAttribute('fill', color || 'var(--muted)');
  t.setAttribute('font-size', String(size || 12));
  if (anchor) t.setAttribute('text-anchor', anchor);
  t.textContent = text;
  return t;
}

function svgRect(x, y, w, h, fill, stroke, rx) {
  const r = document.createElementNS(SVG_NS, 'rect');
  r.setAttribute('x', x); r.setAttribute('y', y);
  r.setAttribute('width', w); r.setAttribute('height', h);
  r.setAttribute('fill', fill);
  if (stroke) { r.setAttribute('stroke', stroke); r.setAttribute('stroke-width', '1'); }
  if (rx) r.setAttribute('rx', rx);
  return r;
}

function svgPolygon(points, fill) {
  const p = document.createElementNS(SVG_NS, 'polygon');
  p.setAttribute('points', points.join(' '));
  p.setAttribute('fill', fill);
  return p;
}

async function drawDrift() {
  // Item-1 amplified rendering. Same data, same score/threshold/flag/fault
  // computation as before — only the drawing changed. viewBox coordinates:
  // 1560x380, so 12-13px text renders ~1:1 at demo width.
  const pk = document.getElementById('connector-picker').value;
  const svg = document.getElementById('chart');
  svg.replaceChildren();
  document.getElementById('drift-note').textContent = '';
  const hint = msg => svg.append(svgText(28, 46, msg, 'var(--faint)', 14));
  if (!pk) { hint('select a connector to plot its per-session anomaly trend'); return; }
  const [records, allAlerts] = await Promise.all([
    (await fetch('/drift/' + pk)).json(),
    (await fetch('/alerts?limit=200')).json(),
  ]);
  if (!records.length) { hint('no scored sessions yet for this connector'); return; }

  const W = 1560, PADL = 64, PADR = 24;
  const TOP = 42, BOT = 252;          // score pane
  const DTOP = 298, DBOT = 368;       // duration pane
  const n = records.length;
  const dense = n > 200;              // real-fleet views stay readable
  const lineW = dense ? 1.8 : 2.8;
  const dotR = dense ? 3.5 : 5;
  const x = i => PADL + (W - PADL - PADR) * (n === 1 ? 0.5 : i / (n - 1));

  // per-session anomaly score, shown so that HIGHER = more unusual
  // (display inversion only; the underlying score is unchanged)
  const abn = records.map(r => -(r.anomaly_score ?? 0));
  const rawThr = records[records.length - 1].layer2_threshold;
  const thr = rawThr != null ? -rawThr : null;
  const sMin = Math.min(...abn, thr ?? -0.15, -0.15);
  const sMax = Math.max(...abn, thr ?? 0.15, 0.15);
  const sy = v => TOP + (BOT - TOP - 14) * (1 - (v - sMin) / (sMax - sMin)) + 4;

  // flagged zone: everything above the threshold IS the flagged region —
  // visible geometry instead of a caption
  if (thr != null && sy(thr) > TOP) {
    svg.append(svgRect(PADL, TOP, W - PADL - PADR, Math.max(0, sy(thr) - TOP),
                       'rgba(255,92,73,.07)'));
  }

  // y-gridlines + score ticks (4-5 nice steps)
  const step = Math.max(0.05, Math.round((sMax - sMin) / 4 / 0.05) * 0.05);
  for (let v = Math.ceil(sMin / step) * step; v <= sMax + 1e-9; v += step) {
    const gy = sy(v);
    if (gy < TOP + 4 || gy > BOT - 2) continue;
    svg.append(polyline([`${PADL},${gy}`, `${W - PADR},${gy}`], 'var(--rule)', 1));
    svg.append(svgText(PADL - 10, gy + 4, v.toFixed(2), 'var(--faint)', 12, 'end'));
  }

  // threshold: dashed line, label anchored LEFT inside the zone (fault-cluster
  // chips live in the top annotation band, so the two can never collide)
  if (thr != null) {
    const ty = sy(thr);
    const t = polyline([`${PADL},${ty}`, `${W - PADR},${ty}`], 'var(--p1)', 1.5);
    t.setAttribute('stroke-dasharray', '7 5');
    svg.append(t);
    svg.append(svgText(PADL + 8, ty > TOP + 22 ? ty - 8 : ty + 18,
      'flag threshold — above = flagged', 'var(--p1)', 12.5));
  }

  // area fill under the score curve, then the curve itself
  const curve = abn.map((v, i) => `${x(i)},${sy(v)}`);
  svg.append(svgPolygon(
    [`${x(0)},${BOT}`, ...curve, `${x(n - 1)},${BOT}`], 'rgba(90,162,255,.12)'));
  svg.append(polyline(curve, 'var(--drift)', lineW));
  for (let i = 0; i < n; i++) if (records[i].flagged) {
    const dot = document.createElementNS(SVG_NS, 'circle');
    dot.setAttribute('cx', x(i)); dot.setAttribute('cy', sy(abn[i]));
    dot.setAttribute('r', dotR); dot.setAttribute('fill', 'var(--p1)');
    dot.setAttribute('stroke', '#070d18');
    dot.setAttribute('stroke-width', dense ? 1.2 : 1.6);
    dot.append(Object.assign(document.createElementNS(SVG_NS, 'title'),
      {textContent: `flagged session — closed ${records[i].closed_at}`}));
    svg.append(dot);
  }
  svg.append(svgText(PADL, 24,
    'session anomaly score — higher = more unusual (red dots = flagged)',
    'var(--drift)', 12.5));

  // fault-event annotations: each Layer 1 fault for this connector, placed at
  // its position in the plotted session sequence (by timestamp). Faults from
  // before the plotted window are skipped; faults AFTER the last plotted
  // session pin to the right edge — the degrade-then-fault story itself.
  const first = records[0].closed_at || '';
  const faults = allAlerts.filter(a => String(a.connector_pk) === String(pk)
    && a.detector_source !== 'layer2_drift' && a.stage !== 'candidate'
    && a.fired_at);
  const drawable = faults.filter(f => f.fired_at >= first);
  const groups = new Map();  // session index -> {count, category}
  for (const f of drawable) {
    const idx = Math.min(n - 1, records.filter(r => (r.closed_at || '') <= f.fired_at).length);
    const g = groups.get(idx) || { count: 0, category: category(f) };
    g.count++;
    groups.set(idx, g);
  }
  const marked = [...groups].sort((a, b) => b[0] - a[0]).slice(0, 8);
  for (const [idx] of marked) {
    const fl = polyline([`${x(idx)},34`, `${x(idx)},${BOT}`], 'var(--p2)', 1.5);
    fl.setAttribute('stroke-dasharray', '2 3');
    svg.append(fl);
  }
  // flag chips in the top annotation band (y 6..26): summary chip when the
  // cluster is big, per-group chips otherwise; chips clamp right of the title
  // zone and skip (line stays) rather than ever overlapping
  const chipFor = (fx, label) => {
    const w = 16 + label.length * 6.6;
    const minX = PADL + 560, maxX = W - PADR - w;
    const cx = Math.max(minX, Math.min(fx - w / 2, maxX));
    return { cx, w, label };
  };
  const chips = [];
  if (marked.length > 3) {
    const total = marked.reduce((s, [, g]) => s + g.count, 0);
    chips.push(chipFor(x(marked[0][0]),
      `⚠ ${total} fault events here: ${marked[0][1].category}`));
  } else {
    for (const [idx, g] of marked)
      chips.push(chipFor(x(idx),
        `⚠ ${g.count > 1 ? g.count + '× ' : ''}fault: ${g.category}`));
  }
  let prevStart = Infinity;
  for (const c of chips) {
    if (c.cx + c.w > prevStart - 8) c.cx = prevStart - 8 - c.w;   // shift left
    if (c.cx < PADL + 560) continue;                              // no room: line only
    svg.append(svgRect(c.cx, 6, c.w, 20, 'var(--p2-wash)', 'var(--p2-edge)', 10));
    svg.append(svgText(c.cx + 8, 20, c.label, 'var(--p2)', 12));
    prevStart = c.cx;
  }

  // x-axis time cues: first and last session close dates
  svg.append(svgText(PADL, 272, (records[0].closed_at || '').slice(0, 10), 'var(--faint)', 12));
  svg.append(svgText(W - PADR, 272, (records[n - 1].closed_at || '').slice(0, 10),
                     'var(--faint)', 12, 'end'));

  // bottom pane: session duration (minutes) — approved legacy surface
  const durations = records.map(r => (r.duration_sec ?? 0) / 60);
  const dMax = Math.max(...durations, 1);
  const dy = v => DTOP + (DBOT - DTOP) * (1 - v / dMax);
  const dcurve = records.map((r, i) => `${x(i)},${dy((r.duration_sec ?? 0) / 60)}`);
  svg.append(svgPolygon(
    [`${x(0)},${DBOT}`, ...dcurve, `${x(n - 1)},${DBOT}`], 'rgba(47,212,140,.08)'));
  svg.append(polyline(dcurve, 'var(--ok)', dense ? 1.6 : 2.2));
  svg.append(svgText(PADL, 292, 'session duration (min)', 'var(--ok)', 12.5));

  document.getElementById('drift-note').textContent =
    `${n} sessions, oldest → newest — ${records.filter(r => r.flagged).length} flagged`
    + (faults.length ? ` — ${drawable.length} of ${faults.length} fault events in view` : '');
}

function tickClock() {
  document.getElementById('clock').textContent =
    new Date().toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
}

document.getElementById('connector-picker').addEventListener('change', () => { drawDrift(); refreshConnectors(); });
poll(); refreshConnectors(); tickClock();
setInterval(() => { poll(); refreshConnectors(); drawDrift(); }, 2000);
setInterval(tickClock, 1000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE
