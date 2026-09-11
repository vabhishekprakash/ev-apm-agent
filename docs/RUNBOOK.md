# RUNBOOK: run & manually test the EV APM Agent

A step-by-step guide for a human operator to start the system and verify every
feature by hand. Two ways to run it: **Docker** (recommended, one command) or
a **local Python pipeline**. No cloud, no external services.

> All commands are copy-paste ready. On Windows use **Git Bash**; where a
> command feeds a container a `/app/...` path through an env var, keep the
> `MSYS_NO_PATHCONV=1` prefix shown; it stops Git Bash from rewriting the
> path.

---

## 0. Prerequisites

- **Docker Desktop** running (for the container path), **or** Python 3.11+
  with `pip install pydantic scikit-learn==1.7.2 fastapi uvicorn` (for the
  local path).
- Port **8000** free (the UI binds it).

Verify Docker is up:
```bash
docker version --format '{{.Server.Version}}'   # prints a version = daemon ready
```

---

## 1. Start it (Docker, recommended)

From the repo root:

```bash
cp .env.example .env
docker compose up -d --build
```

Wait ~30 s, then confirm all services are healthy and the UI answers:

```bash
docker compose ps                                   # replay / detector / ui
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/   # expect 200 
                          or
curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:8000/    # expect 200
```

Open **http://localhost:8000** in a browser. **The dashboard populates within
seconds.** By default the pipeline replays the real exports under `data/raw`;
on a fresh public clone (where `data/raw` is gitignored/empty) it falls back
to the bundled `demo_replay` fixture and prints an unmissable
`SYNTHETIC FIXTURE DATA` banner in `docker compose logs replay`; fixture
rows are never silently passed off as real. **Any other missing source
folder is a hard error (exit 2)**, never a substitution: check
`docker compose logs replay` if the queue stays empty.

### 1a. Verification sequence (verified 2026-07-19, expected output at every step)

> ⚠️ **Re-injecting a stream you already loaded duplicates every row and
> doubles all KPIs.** The buffers are in-memory; the only reset is
> `docker compose down -v` (Docker) or restarting `uvicorn` (local §2).
> Run each injection exactly once per reset.

**Step 0. Reset (always start here):**
```bash
docker compose down -v
```

**Step 1. Start the stack on the REAL error-sequence export** (requires the
gitignored real exports, team machines only; a fresh public clone must use
the fixture path in §3a instead):
```bash
MSYS_NO_PATHCONV=1 DATA_DIR=/app/data/interim/sequences_replay \
  docker compose up -d
sleep 30
```

**Step 2. VERIFY the real data loaded** (all rows REAL fleet data):
```bash
curl -s "http://localhost:8000/alerts?limit=500" | python -c \
  "import json,sys; a=json.load(sys.stdin); \
print('alerts:',len(a)); print('connectors:',sorted({str(x['connector_pk']) for x in a}))"
```
**Expect:** `alerts: 500` (ring-buffer cap; 869 were emitted) and connectors
**exactly** `['1679593','1679594','1880097','1880098','1989806','1989807']`.
**4784325 must NOT appear**. If it does, the fixture leaked in: reset and
re-check your `DATA_DIR`. Queue tiers ≈ P1 219 / P2 202 / P3 79; ~76 rows say
*"self-recovered in Ns"*.

**Step 3. Inject the demo fixture ONCE** (adds the SYNTHETIC arc connector
4784325, the GroundFailure safety pill, session-drift rows, and sessions):
```bash
DATA_DIR=tests/fixtures/demo_replay REPLAY_SPEED_MULTIPLIER=0 \
  python replay/main.py | (cd detector && ALERT_SINK=http \
  LAYER2_THRESHOLD=-0.1187 ALERT_URL=http://localhost:8000/alerts python main.py)
```
**Expect on its stderr:** `sessions_closed: 21, sessions_scored: 19,
layer2_flagged: 4, alerts: 17, parse_errors: 0`.

**Step 4. VERIFY the combined state:**
```bash
curl -s http://localhost:8000/connectors     # expect: exactly [4784325]
curl -s http://localhost:8000/stats          # expect sessions_closed 21 / scored 19
```
In the browser: 4784325 now present in the queue and **auto-selected in the
drift panel** with the degrade-then-fault arc; 8 category chips; all three
tiers. Combined buffer stays at 500 (cap).

**Which rows are REAL vs FIXTURE after this sequence:** everything on
connectors 1679593/1679594/1880097/1880098/1989806/1989807 is **real fleet
data** (the sequence export). Everything on 4784325/5802030/1744735 (and
the OverVoltage/GroundFailure rows the fixture stages on 2009529/1679593)
is **synthetic fixture data**; the drift arc on 4784325 is demo sessions
scored by the real committed model. Never present fixture rows as real.

**Note:** don't replay `demo_replay` at 60× (its 79-hour span takes about 50 minutes to reach the first alert). For live motion on the dashboard, use the `--follow` raw-log tail (§3½.1, about 3 s from append to dashboard).

Stop / reset (also the duplication reset):
```bash
docker compose down -v      # -v clears the event-bus volume between runs
```

---

## 2. Start it (local Python, no Docker)

```bash
# one-shot: replay a fixture through the detector, alerts print as JSON lines
REPLAY_SPEED_MULTIPLIER=0 DATA_DIR=tests/fixtures/demo_replay \
  python replay/main.py | python detector/main.py
```

To see it in the **UI** locally, run the UI in one terminal and the pipeline
in another:

```bash
# terminal 1 — dashboard
cd ui && python -m uvicorn main:app --port 8000

# terminal 2 — drive the dashboard (all six fault categories)
DATA_DIR=tests/fixtures/demo_replay REPLAY_SPEED_MULTIPLIER=0 \
  python replay/main.py | (cd detector && \
  ALERT_SINK=http ALERT_URL=http://localhost:8000/alerts python main.py)
```

Open **http://localhost:8000**.

---

## 3. Manual feature tests

The repo ships three synthetic fixtures under `tests/fixtures/` (real CMS data
is gitignored). Each drives a specific feature. Use the Docker form
(`MSYS_NO_PATHCONV=1 DATA_DIR=/app/tests/fixtures/<name> ... docker compose up`)
or the local two-terminal form from §2 with `DATA_DIR=tests/fixtures/<name>`.

### 3a. All six fault categories fire  →  `demo_replay`
```bash
docker compose down -v
MSYS_NO_PATHCONV=1 DATA_DIR=/app/tests/fixtures/demo_replay \
  REPLAY_SPEED_MULTIPLIER=0 docker compose up -d --build
sleep 20
curl -s "http://localhost:8000/alerts?limit=100" | python -c \
  "import json,sys,collections;\
c=collections.Counter((a.get('fault_category') or a['detector_source']) for a in json.load(sys.stdin));\
print(dict(c))"
```
**Expect:** err1051, err1024, telemetry_silence, WeakSignal, GroundFailure,
Under/OverVoltage all present. In the browser they appear as color-coded rows
and as chips in the coverage bar ("N of 19 OCPP categories seen").

### 3b. Prioritization + the 13-second downgrade  →  `day5_replay`
```bash
docker compose down -v
MSYS_NO_PATHCONV=1 DATA_DIR=/app/tests/fixtures/day5_replay \
  REPLAY_SPEED_MULTIPLIER=0 docker compose up -d --build
```
In the UI feed ("Maintenance Decision Support"), verify the **deciding-signal**, **impact**, and **recommended action** columns:
- an **err1051** row is **grey P3** with *"self-recovered in 13s"*, the
  transient that gets auto-suppressed;
- a **telemetry_silence** row is **red P1** with *"active session dark for …s"*.

Click the **"sort: tier"** toggle to flip tier↔newest ordering; click a
**category chip** to filter the feed to one category.

### 3c. Per-connector drift panel
Drive any stream. The panel **auto-selects** the worst-health connector with
session history; the dropdown switches connectors manually.
**Expect:** a score trend line with red dots on flagged sessions, a threshold
line, fault-event markers, and a duration pane below. `demo_replay` ships a
synthetic degrade-then-fault arc on connector 4784325 (healthy sessions →
rising anomaly scores → err1051), scored by the committed model, so the story
renders even on a fresh clone; real session history (`data/raw`) fills it
densely with real data.

### 3d. Alert-sink toggle
- `ALERT_SINK=stdout` (default local): alerts print as JSON lines.
- `ALERT_SINK=http`: alerts POST to the UI (`ALERT_URL`). Shown in §2/§3.

---

## 3½. Bring your own data (which files, which columns, where)

The pipeline ingests **CSV exports**, not live OCPP traffic. Point `DATA_DIR`
at any folder containing some or all of these files. Each is optional; the
replay merges whatever exists into one time-ordered stream:

| File | Columns (header row required) | Drives |
|---|---|---|
| `status_notification.csv` | `connector_pk,status,error_code[,vendor_error_code],timestamp` | all Layer 1 fault detectors |
| `meter_values.csv` | `transaction_pk,connector_pk,meter_reading_wh,timestamp` | err1051 meter gate; telemetry-silence re-arm |
| `transaction.csv` | `transaction_pk,connector_pk,start_timestamp,stop_timestamp,stop_reason` | session tracking; Layer 2 scoring on close |
| `heartbeat.csv` | `log_sequence_id,hashed_charge_box_id,timestamp` | advances the silence clock only |
| `boot_notification.csv` | `log_sequence_id,hashed_charge_box_id,timestamp,registration_status` | ignored by detectors (clock only) |

Rules of the contract:
- **Timestamps**: `YYYY-MM-DD HH:MM:SS[.ffffff]` (quoted or not). Events are
  replayed in global timestamp order.
- **`status`** must be an OCPP 1.6 ChargePointStatus (`Available`,
  `Preparing`, `Charging`, `SuspendedEV`, `SuspendedEVSE`, `Finishing`,
  `Reserved`, `Unavailable`, `Faulted`) or the observed extras
  (`RemoteStartRequested`, `RemoteStopRequested`). Unknown statuses are
  counted as parse errors and skipped; the stream keeps flowing.
- **`error_code`** is the OCPP category; vendor-specific codes (incl.
  `system-err*`) may ride in `vendor_error_code`; detectors match either.
- **Station enrichment** is optional: rows in
  `data/reference/charger_stations.csv` / `fault_segment_stations.csv`
  (`connector_pk,hashed_charge_box_id,physical_plug_id`, hash = 64-char
  SHA-256) light up the station column, station-wide escalation, and
  per-connector Layer 2 models. Unknown `connector_pk`s still alert; they
  fall back to the global pooled model and show pk-only.
- **Where to put files**: anywhere; pass the folder as `DATA_DIR`
  (`data/raw/` is the conventional, gitignored spot). **Never commit raw
  operator data**: run `bash tests/anonymization_audit.sh` before any
  commit that touches `data/` or docs.

Smoke-check your own export end-to-end:

```bash
DATA_DIR=path/to/your/export REPLAY_SPEED_MULTIPLIER=0   python replay/main.py | python detector/main.py
# stderr shows: events / routed / parse_errors / alerts — parse_errors > 0
# means a column or status value doesn't match the contract above
```

### 3½.1 Native OCPP-J logs (raw CMS WebSocket export)

If instead of the flattened CSVs you have the **raw CMS log**, semicolon-
delimited rows whose `message` column holds an OCPP-J frame
(`idcms_logs;messageId;chargerId;message;messageType;messageTime`), feed it
directly; no manual flattening needed:

```bash
REPLAY_SPEED_MULTIPLIER=0 python replay/main.py \
  --format raw-ocpp path/to/logs.csv | python detector/main.py
```

The adapter parses each frame, correlates StartTransaction with its result for
the transaction id, flattens MeterValues sampled values (energy, voltage,
current, power, state-of-charge, and body/outlet/inlet temperature), and
**anonymizes at ingestion**: the charger id is SHA-256 hashed and the raw
correlation ids and any customer card fields never leave the adapter. It emits
the identical event stream the CSV path produces, so the detector and UI are
unchanged. Frame and skip counts print to stderr. Inspect the normalized
stream alone with `python detector/ocpp_log_adapter.py path/to/logs.csv`.

**Streaming raw OCPP-J ingestion (`--follow`).** Add `--follow` to TAIL a
growing log: existing content is processed first, then newly appended frames
are parsed, anonymized, reconciled to their native connector key, and pushed
through the pipeline the moment they land; the dashboard updates within
seconds. Be precise when describing this: it **simulates live ingestion by
tailing a file**; it is **not a live CMS socket connection**.

```bash
# terminal 1 — dashboard
cd ui && python -m uvicorn main:app --port 8000
# terminal 2 — stream the tail into the detector
python replay/main.py --format raw-ocpp --follow path/to/logs.csv | \
  (cd detector && ALERT_SINK=http ALERT_URL=http://localhost:8000/alerts python main.py)
# terminal 3 — append frames to the file and watch them appear in the UI
```

---

## 4. Verify correctness (automated)

```bash
python -m pytest tests/ -q            # 98 tests, all pass (95 on a fresh clone)
bash tests/anonymization_audit.sh     # data-governance gate → PASS
bash scripts/run_all_tests.sh         # everything above in one shot
```

Regenerate the measured artifacts (optional; needs pandas + scikit-learn):
```bash
python scripts/category_metrics.py    # docs/category_metrics.{md,json}
python scripts/deck_assets.py         # docs/assets/fpr_chart.png, category_coverage.png
python scripts/normalizer_coverage.py # vendor-code coverage (needs error_taxonomy.csv)
```

---

## 5. Troubleshooting

| Symptom | Fix |
|--------|-----|
| `docker compose` can't reach the daemon | Start Docker Desktop; wait for `docker version` to print a Server version. |
| UI shows no alerts | The detector waits for UI health before POSTing; give it ~20 s, or `docker compose restart detector`. |
| Replay says "0 events" and a `C:/Program Files/Git/app/...` path in logs | Git Bash rewrote the container path; prefix the command with `MSYS_NO_PATHCONV=1`. |
| Port 8000 in use | Stop the other process, or change the host port in `docker-compose.yml`. |
| Reset between demo runs | `docker compose down -v` (the `-v` clears the event-bus volume). |

---

## 6. What "good" looks like

A clean end-to-end run shows: alerts streaming into the UI within ~2 s of
replay, color-coded P1/P2/P3 with plain-language deciding signals, the coverage
bar counting categories, and the drift panel rendering a score trend. That is
the whole product in one screen.
