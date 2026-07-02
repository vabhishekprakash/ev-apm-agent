# EV APM Agent — Project Specification

**Repo:** `ev-apm-agent`
**Hackathon:** ET AI Hackathon 2026
**Team:** Abhishek (Layer 1 + integration), Akhil (Layer 2 + data audit)
**Duration:** 4 weeks, 12 hrs/week per person, 2 hrs/day Mon–Sat
**Status at time of writing:** End of Week 1, Day 2. Day 3 tasks defined but not started.

---

## 1. Problem statement (as accepted)

**Track:** AI for Industrial EV Supply Chain & Asset Intelligence: Accelerating Net Zero
**Sub-component:** EV Asset Performance Management (APM) Agent

**What we're building, in one paragraph:**
A watchful operator for EV charging stations that catches faults the instant they happen and spots chargers starting to go bad before they fully fail. It plugs into the data the charging network already sends to its Charging Management System (CMS) — no new sensors, no hardware changes. It runs a fast rules-based catcher for known fault patterns plus a learning layer that tracks each connector's "normal" over time to flag drift. It also sorts alerts, separating noisy self-recovering blips from real problems needing a technician. Proven on real anonymized data from 39 stations across 5+ vendors. Deploys as a drop-in container next to an existing CMS.

**Locked framing sentences (never deviate):**
- **What it is:** "Real-time fault detection and per-connector degradation tracking across an EV charging fleet."
- **What it isn't:** "Not a battery health diagnostic — it analyzes charging-station telemetry to flag faults and connector-level degradation, vendor-agnostic."
- **Where it lives:** "Deploys as a sidecar container next to an operator's existing CMS, scaling per fleet size."

**Framing NOT to use:** "predictive maintenance" as the headline. The data does not support a lead-time prediction claim on the labeled fault types (see §3.2). This decision is locked; do not revisit.

---

## 2. Scope guardrails

### In scope for the 4-week hackathon prototype

- Layer 1 deterministic fault detection (err1051 state machine, err1024 point-event handler, telemetry-silence sub-detector)
- Layer 2 per-connector session-feature drift tracking + pooled cross-fleet baseline
- Alert prioritization using 13-second self-recovery signal (transient vs technician-dispatch)
- Event-replay demo harness reading anonymized CMS export at configurable cadence
- FastAPI + simple frontend dashboard surfacing live session feed, alerts, drift signals
- Docker Compose deployment (three services: replay, detector, ui)
- Architecture diagram, 3–4 min demo video, detailed document, public GitHub repo

### Explicitly out of scope (parked to "future work" slide)

- Multi-vendor error-code NLP normalization (embedding model over error strings)
- Natural-language query interface (text-to-SQL over CMS schema)
- LLM-based operator alert summarization
- Autoencoder-based anomaly detection (Isolation Forest is the pick — see §5.2)
- Vendor-specific learned anomaly signatures (n=2 faults, not viable)
- Cloud deployment, multi-tenant SaaS, CMS vendor partnerships
- Direct battery health / SoH / SoC diagnostics — data is station-side only

---

## 3. Data — what we have and what it tells us

### 3.1 Data source and constraints

- **Source:** Production CMS MySQL database, accessed via Workbench with read-only credentials
- **Access mode:** One-time export, not live API
- **Anonymization applied at export:** SHA-256 hash of `charge_box_id`, `latitude`/`longitude` rounded to 2 decimals (~1km resolution), customer/RFID/IP fields dropped
- **Time window for transactional tables:** 90 days ending 2026-06-30 (`WHERE timestamp BETWEEN '2026-04-02 00:00:00' AND '2026-06-30 23:59:59'` UTC)
- **Dimensional tables (`chargepoint`, firmware inventory) pulled unfiltered** — one-row-per-charger, filtering by registration_time would drop most rows
- **OCPP version:** 1.6 (no vendor mapping doc, spec interpretation only)
- **Data lives:** Shared drive (indexed via a team Excel with CSV links), copied locally to `data/raw/` per teammate. Never committed.

### 3.2 Fleet inventory (confirmed numbers)

- **39 charging stations**, **80 listed connectors**, **~68 physical connectors** (12 stations have `physical_plug_ids="0,1,2"` where connectorId=0 is OCPP charge-point-level, not a physical socket)
- **Station shape mix:** 10 single-connector, 17 two-connector (`0,1` or `1,2`), 12 with `0,1,2`
- **23,084 total normal (fault-free) sessions across 46 active connectors**
- **PRABHAEV004N is the dominant charger** — ~4,439 normal sessions (~19% of fleet volume). Requires downsampling or strict per-connector training to avoid model dominance.

**Normal-session distribution (tier breakdown for Layer 2 viability):**

| Tier | Sessions/connector | Count | Modeling approach |
|---|---|---|---|
| Heavy | ≥1000 | 7 | Per-connector baseline strong |
| Medium | 250–999 | 15 | Per-connector baseline solid |
| Light | 100–249 | 13 | Per-connector baseline thin but workable |
| Marginal | 30–99 | 5 | Pooled baseline preferred |
| Sparse | <30 | 6 | Cannot model individually — pool only |

35 of 46 connectors have ≥100 sessions → per-connector baselines viable for majority; pooled baseline for the 11 sparse/marginal.

**Vendor / firmware diversity (from CP_Firmware and chargepoint tables):**

- Tucker: 11 stations
- Siemens family (SIEMENS + CN.TH running Siemens firmware): 12 stations
- IONGRID: 5 stations
- ACS family (ACSENERGY + ACS285 + ACS286): 5 stations
- Exicom (Exicom + EXICOM case variants): 3 stations
- PRABHAEV1, PRABHAEV251 self-named: 2 stations
- Unknown/NaN: 1 station
- **11 distinct vendor strings, 19 distinct firmware versions**

This confirms the "vendor-agnostic across heterogeneous fleet" pitch line is defensible with evidence, not aspiration.

### 3.3 Data-quality flags to handle in code

1. **One row in `chargepoint` has NaN vendor/model/firmware** but valid coordinates and registration time. Decision pending: drop, impute as `"unknown"`, or ask data owner. Recommend impute as `"unknown"` for Week 1, escalate if it affects Layer 2 cohorting.
2. **PRABHAEV004N has 1 normal session on `connectorId=0`** — almost certainly a malformed StartTransaction. Drop from training. Flag once to data owner.
3. **7 chargers registered <2 months before dataset end** (post-Feb 2026). Their normal-session history is shorter than fleet median; may fall into sparse tier regardless of activity.
4. **SoC field is unreliable** — reports 0 for vehicles/protocols that don't transmit SoC. Use CC-CV power-curve shape as SoC proxy for those sessions.

### 3.4 Fault labels — what actually exists

**Only 2 labeled fault events in the entire dataset**, both on the same charger (PRABHAEV004N), 7 minutes apart, on different connectors. Two distinct error codes:

**`system-err1051` (internal name: `GQ_DIN_ERROR_INIT_SOCKET`)**
- Internal charger fault, failure to initialize internal socket
- **Reproducible sequence (5-step state machine):**
  1. Charging status → `err1051` appears
  2. MeterValues drop to zero (voltage, current, power fall simultaneously)
  3. Finishing status → second instance of `err1051`
  4. StopTransaction with reason code `Other`
  5. Available status ~13 seconds later
- Deterministic, encodable as pattern matcher

**`system-err1024` (internal name: `GQ_SLAC_ERROR_PARAM_TIMEOUT`)**
- SLAC/PLC handshake failure with the vehicle during ISO 15118 high-level communication setup
- Occurs pre-charge — transaction may not have started
- **No equivalent state machine — different fault mechanism** (point event, not sequence)
- Timestamp-ordering investigation still pending (see §7 open items)

Both faults are "session never really started" failures → no usable pre-window in the session's own telemetry. Any predictive signal, if it exists, would live in *prior* sessions on the same connector, not the faulted session itself.

### 3.5 Key finding: telemetry silence IS the fault signature

Faulted sessions have **zero MeterValues during the active fault window**. The charger's periodic-reporting loop is the same control path that breaks when the fault fires. This is why searching for pre-fault measurand drift returned empty — it's a structural property of the fault, not missing data.

**Implication:** absence of MeterValues during an active session is itself a deterministic Layer 1 feature. Encode it as a sub-detector alongside the two error-code handlers.

---

## 4. Architecture

### 4.1 Two-layer detection model

**Layer 1 — Deterministic rule-based detection**
- err1051 state-machine matcher (5-step sequence)
- err1024 point-event handler
- Telemetry-silence sub-detector (active session, no MeterValues for >N seconds)
- Full precision/recall on known signatures by construction
- Value proposition: automated, faster alerting vs vendor-dashboard delays. **Not marketed as ML.**

**Layer 2 — Unsupervised anomaly detection**
- Per-connector session-feature extraction on normal sessions
- Per-connector baseline statistics (mean, std, z-score drift indicator)
- Pooled cross-fleet baseline (vendor/firmware-cohorted) for sparse connectors
- **Isolation Forest** (not autoencoder) — trains in seconds, no GPU dependency, explainable
- Feature vector per session, feature drift tracked over time per connector
- One model instance per connector for heavy/medium/light tiers; cohort-pooled for sparse

**Session-level features (Layer 2 input):**
- Peak temperature (charger body, connector outlet 1, connector outlet 2)
- Maximum outlet temperature asymmetry (10°C asymmetry observed in real data as candidate leading indicator)
- CC-CV power-curve coefficients (peak power, taper slope)
- Session duration vs energy delivered
- SoC proxy: current power as fraction of session peak power, and slope of that ratio over trailing window (for sessions where SoC field is 0)

### 4.2 Alert prioritization layer

- 13-second self-recovery signal from err1051 distinguishes transient (self-clearing) from technician-dispatch faults
- Directly reduces alert fatigue for operators
- Judge-recognizable operations problem — strong Business Impact talking point

### 4.3 Deployment topology (demo)

Single Docker Compose file, three services, all local:

- **`replay`** — reads anonymized CSV export, emits OCPP-shaped events at configurable real-time cadence via `REPLAY_SPEED_MULTIPLIER` env var
- **`detector`** — Layer 1 (state machines + silence detector) + Layer 2 (Isolation Forest inference on session close)
- **`ui`** — FastAPI + simple frontend showing live session feed, fault alerts as they fire, recovery-time classification, per-connector degradation panel

Model training happens on Akhil's machine (RTX 4060), model artifact committed as `.pkl` to the repo (via `!models/*.pkl` allowlist), inference runs on any hardware.

### 4.4 Production deployment shape (pitched, not built)

**Shape 1 (recommended, pitched):** Sidecar container next to operator's CMS. Subscribes to CMS event stream (REST poll / message queue / webhooks). Alerts pushed back into Slack, email, PagerDuty, or CMS's own alerting via write API.

**Shape 2 (scale path, future work slide):** CMS vendor licenses detection logic, bundles as feature in their platform.

**Shape 3 (future work slide):** Multi-tenant SaaS, operators connect their CMS to hosted service.

---

## 5. Infrastructure and environment

### 5.1 Hardware

- **Abhishek:** Intel i5-9400F, 16GB RAM, GTX 1050 Ti (4GB VRAM), HDD+SSD storage. Constrained. **No model training on this machine.** Runs Layer 1 and inference-only Layer 2.
- **Akhil:** Intel i9, 16GB RAM, RTX 4060, 1TB. Comfortable. **Owns all model training and Layer 2 development.**
- **No cloud budget.** Local-only deployment.

### 5.2 Model choice justification

Isolation Forest chosen over autoencoder because:
1. Trains in seconds on available data volume (23k sessions, 46 connectors)
2. Runs on any hardware including Abhishek's constrained machine at inference
3. Explainability story: "flagged because outlet asymmetry was N standard deviations above this connector's rolling baseline" — defensible in judge Q&A
4. No neural network to justify architecturally
5. Autoencoder is a future-work slide item, not a Week 2 deliverable

### 5.3 Dev environment

- Python 3.11 (pinned via `pyproject.toml` or `.python-version`)
- VS Code with Continue extension
- Akhil may run gpt-oss:20b locally on his 4060 if desired; Abhishek uses whatever is fastest on his machine — dev workflow is NOT a deliverable, do not force uniformity
- Windows dev machines, Linux Docker containers — all code uses `pathlib.Path`, no hardcoded backslashes

---

## 6. Repository structure (Pattern B — services only)

```
ev-apm-agent/
├── .continue/                 # Continue extension config (decide if sensitive)
├── .gitignore                 # See §6.1
├── .dockerignore              # See §6.2
├── .env.example               # Committed template, real .env gitignored
├── docker-compose.yml
├── LICENSE                    # MIT, added before repo goes public
├── README.md                  # Contains locked framing sentences
├── pyproject.toml             # Or requirements.txt + .python-version
│
├── data/
│   ├── raw/                   # Gitignored. Local per-teammate CSV exports.
│   │   ├── .gitkeep
│   │   └── EXPORT_NOTES.md    # Filename, row count, date, window, operator per export
│   ├── interim/               # Gitignored
│   │   └── .gitkeep
│   ├── processed/             # Gitignored
│   │   └── .gitkeep
│   ├── reference/             # COMMITTED. Inventory CSVs.
│   │   ├── .gitkeep
│   │   ├── total_stations.csv
│   │   ├── charger_stations.csv
│   │   ├── cp_firmware.csv
│   │   └── normal_sessions.csv
│   └── sql/                   # COMMITTED. One .sql file per exported table.
│       ├── .gitkeep
│       ├── chargepoint.sql
│       ├── transaction.sql
│       ├── meter_values.sql
│       ├── status_notification.sql
│       ├── heartbeat.sql
│       └── boot_notification.sql
│
├── detector/
│   ├── Dockerfile
│   ├── main.py                # Service entry point
│   ├── ocpp_messages.py       # Typed schemas for StatusNotification, MeterValues, StartTransaction, StopTransaction
│   ├── layer1.py              # err1051 state machine, err1024 handler, telemetry-silence sub-detector
│   └── layer2.py              # SessionFeatureExtractor, per-connector drift, Isolation Forest inference
│
├── replay/
│   ├── Dockerfile
│   └── main.py                # CSV → sorted event stream → stdout/socket at configurable cadence
│
├── ui/
│   ├── Dockerfile
│   └── main.py                # FastAPI + minimal frontend
│
├── models/                    # Trained Isolation Forest artifacts
│   └── .gitkeep
│
├── notebooks/                 # Akhil's exploration, not production code
│   ├── .gitkeep
│   └── 01_data_audit.ipynb
│
├── tests/
│   └── .gitkeep
│
└── docs/
    ├── .gitkeep
    ├── architecture_v0.md     # 5-line summary + two-layer description + diagram placeholder
    ├── data_audit_v0.md       # Full audit output (row counts, tier breakdown, data-quality flags)
    └── layer2_scope.md        # Tier cutoffs, per-connector vs pooled decision
```

### 6.1 .gitignore essentials

```gitignore
# Data — never commit raw or intermediate CMS data
data/raw/
data/interim/
data/processed/
*.csv
*.parquet
*.feather
*.h5
# Allow reference CSVs
!data/reference/*.csv

# Model artifacts (allowlist trained models if needed)
*.pkl
*.joblib
*.pt
*.pth
*.onnx

# Secrets
.env
.env.*
!.env.example
*.pem
*.key
secrets/
credentials.json

# Python
__pycache__/
*.py[cod]
.venv/
venv/
build/
dist/
*.egg-info/

# Jupyter
.ipynb_checkpoints/

# Testing / linting
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage

# Docker
*.pid
docker-compose.override.yml

# IDE
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db

# Logs
*.log
logs/
tmp/

# Local overrides
local_config.py
config.local.yaml
```

### 6.2 .dockerignore essentials

```
data/
.git/
.venv/
__pycache__/
*.pyc
notebooks/
tests/
.env
.env.*
*.md
```

### 6.3 .env.example

```
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
REPLAY_SPEED_MULTIPLIER=1
DATA_DIR=./data/raw
```

---

## 7. Open items still pending

### Blocking Week 1 completion
1. **err1024 reproducible sequence investigation** — Confirm whether StartTransaction precedes err1024 status, whether multiple err1024 events fire in sequence (SLAC retries), whether there's a recovery-time signal analogous to err1051's 13 seconds. Owner: Abhishek. Blocks Layer 1 completion by Day 5. If no data owner reply within 48 hrs of Day 3, escalate.

### Non-blocking, address by Week 2
2. **Handling of NaN vendor row in chargepoint** — Recommend impute as `"unknown"` for now; revisit if it affects Layer 2 cohorting.
3. **Continue extension config sensitivity** — Decide if `.continue/` folder contains anything personal or has API keys; add to `.gitignore` if so.

### Hackathon organizer questions (send one email, move on)
4. Scoring rubric details — mostly known (Innovation 25%, Business Impact 25%, Technical Excellence 20%, Scalability 15%, UX 15%), but confirm evaluation format
5. Submission deadline exact date (needed for calendar milestone planning)

---

## 8. Current progress

### Completed
- ✅ Problem statement selection and framing locked
- ✅ Data access established, one-time export via MySQL Workbench
- ✅ Anonymization scheme validated (SHA-256 charger IDs, 2-decimal geo masking)
- ✅ `chargepoint` table exported and verified (39 rows, vendor mix reconciles)
- ✅ Fleet inventory analyzed from 4 reference CSVs (Total_Stations, Charger_Stations, CP_Firmware, Normal_Sessions)
- ✅ Data-quality flags catalogued
- ✅ Two-layer architecture decided (Layer 1 state machines + Layer 2 Isolation Forest)
- ✅ Repository skeleton created with folders for detector, replay, ui, notebooks, tests, docs, data
- ✅ `.gitignore` populated
- ✅ Docker Compose scaffold with three placeholder services
- ✅ Roadmap sentences locked

### In progress (Day 1–2 close-out items)
- 🔄 `data/` subfolder skeleton with `.gitkeep` files
- 🔄 `.env.example` committed
- 🔄 `.dockerignore` committed
- 🔄 Folder cleanup: delete `layer1/` and `layer2/` folders, code lives inside `detector/` (Pattern B)
- 🔄 Remaining transactional table exports (`transaction`, `meter_values`, `status_notification`, `heartbeat`, `boot_notification`)
- 🔄 Data audit notebook (`notebooks/01_data_audit.ipynb`)

### Next: Day 3 tasks

**Abhishek — 2 hrs:**
1. `detector/ocpp_messages.py` — typed schemas for 4 OCPP message types (45 min)
2. `replay/main.py` v0 — CSV → sorted → stdout JSON at configurable cadence (60 min)
3. `detector/layer1.py` skeleton — `Err1051Detector` class shell + state enum, no transitions yet (15 min)

**Akhil — 2 hrs:**
1. `docs/data_audit_v0.md` — formalize audit outputs from notebook (60 min)
2. `detector/layer2.py` skeleton — `SessionFeatureExtractor` class with method signatures + docstrings, no logic yet (45 min)
3. `docs/layer2_scope.md` — sparse-connector decision (per-connector vs pooled cutoffs) (15 min)

**Joint — ~30 min call:**
- Merge Day 2 PRs
- Walk through audit doc together
- Log surprises as GitHub Issues (not Slack) for Week 4 traceability
- Confirm err1024 investigation status; escalate to data owner if 48-hr silence

### End-of-Day-3 acceptance criteria
- `detector/ocpp_messages.py`, `detector/layer1.py`, `detector/layer2.py` exist with defined interfaces (no logic yet)
- `replay/main.py` emits events from CSV at configurable speed
- `docs/data_audit_v0.md` committed and reviewed
- `docs/layer2_scope.md` committed with tier cutoffs
- Shared understanding of Day 4 targets

### Week 1 end (Day 6) targets
- Working err1051 state-machine detector firing on replay
- Working err1024 point-event handler
- Telemetry-silence sub-detector functional
- Per-connector session-feature extraction on real data
- Baseline statistics per connector computed
- Architecture diagram v1 photographed and committed
- `docker compose up` runs full pipeline end-to-end on at least one machine

---

## 9. Deliverables summary

- **3–4 minute demo video** (specific length TBD from organizer confirmation)
- **Detailed document** (format TBD)
- **Public GitHub repo URL** at `github.com/<org>/ev-apm-agent`
- No additional materials required

## 10. Headline numbers for the deck

- 39 charging stations, 68 physical connectors
- 23,000+ normal sessions in the training pool
- 5+ vendor families, 19 firmware versions in real deployment
- 2 distinct fault codes with reproducible signatures
- 10°C outlet temperature asymmetry as concrete degradation signal
- 13-second self-recovery signal for alert prioritization
- False-positive rate on held-out normal sessions as headline defensible metric (no held-out fault set exists)