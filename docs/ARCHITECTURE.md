# SleepIQ — System Architecture

**Status:** Approved v1.0 — A1–A7 owner-approved (28 October 2026); implementation details and later domain/security choices remain subject to their own decision gates  
**Depends on:** `PRODUCT.md` (approved product scope v1.0)  
**Audience:** Owner, planner, backend/frontend coding agents  
**Purpose:** Define owner-approved system boundaries and explain remaining implementation-level decision gates.

> **Approval rule:** This document proposes a practical implementation, not an instruction to silently select technology. Before adopting a consequential option, explain it to the owner in plain language, present alternatives with pros/cons (including security, complexity and maintenance), recommend one and await approval. Record approved decisions in `DECISIONS.md`. Routine implementation details may proceed once the associated architecture is approved.

## 1. Architectural objectives and constraints

1. **Windows-first, local-first, single-user:** SleepIQ runs on the owner's Windows PC; its dashboard opens in a browser and its database lives locally. No public hosting, mandatory account or mobile app for v1.
2. **Automatic eventual ingestion:** Apple Watch → Apple Health → Health Auto Export → authenticated SleepIQ ingest endpoint. PC downtime must not create corrupt data; overlapping or repeated exports must be safe.
3. **Correct, reproducible metrics:** Store original observations and calculate clean nightly measurements locally with documented units, timestamp semantics, provenance and formula versions.
4. **Composable analytics:** Individual metric charts, arbitrary supported metric overlays, date ranges, rolling averages, persistent graph presets, and correlations share a single reusable analytics API.
5. **AI is optional and read-only:** The embedded trend investigator receives validated statistical results and strictly scoped data, not direct unrestricted database access. The dashboard works without internet access except AI requests.
6. **Owner-guided development:** Every phase has short decision checkpoints and teaching-oriented explanations. Agents do not silently choose irreversible architecture, security or cost trade-offs.
7. **Progressive disclosure:** `AGENTS.md` routes agents to only the docs relevant to a task. Avoid repeatedly loading the entire documentation set or complete health exports.

## 2. Confirmed evidence from the feasibility test

- A temporary FastAPI receiver on Windows accepted `POST /ingest` from Health Auto Export and returned HTTP `200`; a JSON export was saved locally. `GET /health` returned a readiness response.
- A supplied export uses a top-level `data.metrics` list with the following metric names and sample counts in the inspected file: `sleep_analysis` (202), `heart_rate` (3,390), `heart_rate_variability` (28), `respiratory_rate` (320), `resting_heart_rate` (4), `apple_sleeping_wrist_temperature` (4).
- `sleep_analysis` records contain `start`/`end` (also `startDate`/`endDate`), `value` (`Core`, `Deep`, `REM`, `Awake`), `qty` in hours, and `source`.
- **Important schema distinction:** `heart_rate` records expose `Avg`, `Min`, `Max` and time bounds, **not** the same `qty` field as many other metrics. HRV records include `qty` and may include `heartbeatSeries`. The parser must validate per-metric schemas.
- Actual sleep data includes the 25 October 2026 UK DST clock rollback, with an interval beginning in `+0100` and ending in `+0000`. Elapsed durations must use timezone-aware instants, never naive wall-clock subtraction.
- **Not yet demonstrated:** a fully unattended background upload, guaranteed offline catch-up or long-running secure transport. These are integration verification items, **not reasons to delay architecture work**.
- **Security exception strictly for the feasibility test:** the temporary receiver uses LAN HTTP and permits an eight-character token. **Never deploy that combination as permanent app security.**

## 3. Proposed architecture at a glance

```text
Apple Watch
    ↓ health measurements
Apple Health (iPhone)
    ↓ Health Auto Export JSON v2 (configured metrics)
Direct encrypted trusted-home-network delivery [HTTPS implementation requires a separately approved security design]
    ↓ HTTP request to authenticated /api/ingest
FastAPI application (local Windows PC)
    ├── Request security and payload validation
    ├── Immutable source-import metadata / raw payload boundary
    ├── Health Auto Export schema adapter
    ├── Canonical measurement storage + deduplication
    ├── Night/session builder + derived nightly metrics
    ├── Versioned scoring + consistency engine
    ├── Local statistics/analytics service
    ├── Read-only AI investigation orchestration → optional OpenAI API
    └── REST API for local frontend
            ↕
    SQLite persistent store + same-PC backups
            ↕
React + TypeScript dashboard in desktop browser
```

**Boundaries:** The ingestion endpoint receives external input; the parser normalises provider-specific records; the database stores source and canonical data; calculation modules derive nightly summaries; frontend queries read-only views and invokes explicit preset/export/AI operations. No analytics component should directly interpret raw provider JSON.

## 4. Component responsibilities

### 4.1 Data acquisition / inbound transport

- Receive Health Auto Export JSON v2 at a stable configured endpoint.
- Authenticate each upload before processing the body; reject unauthorised, oversized, invalid-format and malformed requests with safe error responses.
- Use an approved secure transport method for continuous use; keep the listener limited to the appropriate trusted interface/network.
- Record import time, source, content digest, processing status and error reason without logging raw health payloads or secrets.
- Clarify whether exports send complete history, rolling date windows or increments; never assume delivery semantics without testing.

**Separation:** Security/transport configuration is independent of parsing logic and nightly calculations.

### 4.2 Import adapter and validation

- Parse `data.metrics` by metric name and declared unit. Validate record fields by metric type; provider updates must fail explicitly or be safely quarantined, not silently misread.
- Preserve timestamp offsets from export, convert instants to UTC for comparisons, and retain relevant time-zone identity for local calendar interpretation.
- Map stages, heart-rate windows and other measurements to canonical records with consistent units and source identifiers.
- Unknown future metrics are inventoried and surfaced as **unmapped**, not discarded or treated as supported. The owner chooses whether to add them in a planned increment.
- Import raw records and derived summaries transactionally where appropriate; an invalid sample must not corrupt existing data.

**Detailed rules live in:** `DATA_PIPELINE.md`.

### 4.3 Persistence and history

**Approved P5:** SQLite accessed via SQLAlchemy with Alembic migrations. Detailed schema and real-data migration actions retain their review gates.

Conceptual entities (not a final schema):

| Entity | Responsibility |
|---|---|
| `import_batches` | Id, arrival time, digest, source, validation status, counts and safe errors |
| `raw_measurements` | Source-specific record values, time ranges, unit and provenance needed for reprocessing |
| `normalized_measurements` | Validated canonical metric type, value/range, unit and UTC/local-time metadata |
| `sleep_sessions` | Start/end instant, sleep-date attribution, source, completion/quality status |
| `nightly_metrics` | Reproducibly derived per-night metrics and completeness/missing-data markers |
| `score_versions` and `nightly_scores` | Formula identities, parameter snapshots and versioned/recomputed nightly scores |
| `graph_presets` | User-named chart selections, modes, windows and default flag |
| `app_settings` | Non-secret user preferences and approved calculation choices |

This is a **logical decomposition**, not approval to build eight particular tables. Owner approved keeping granular measurements, nightly summaries and configurable raw-payload retention (A2–A3); precise schema cardinality, indexes and migration strategy remain implementation decisions subject to relevant review.

**Idempotency:** An identical import, or overlapping imports with the same source observations, must not double-count samples or produce duplicate nights. Import-level digests alone are insufficient if batches partially overlap. Define a stable observation identity based on available source fields, recording collisions and corrections rather than discarding legitimate distinct records. Do not assume the export has globally unique sample IDs.

### 4.4 Session construction and calculations

- Build overnight sleep sessions from timestamped stage intervals, respecting midnight, naps, missing intervals, overlaps and DST changes.
- Calculate elapsed sleep-stage durations from validated start/end instants; use documented rounding and exclusivity rules.
- Define sleeping HR/overnight SDNN HRV using observations overlapping the approved sleep interval (not a day's unfiltered averages).
- Differentiate provider readings and nightly aggregates. For example, a heart-rate sample might represent an interval with an `Avg`, not a single instantaneous bpm reading.
- Track when a night is incomplete or a metric cannot be computed. No synthetic values to fill gaps without an approved labelled method.
- Recompute derived views when raw data, an aggregation rule or a scoring version changes, without editing source observations.

**Detailed rules live in:** `DATA_PIPELINE.md` and `SCORING.md`.

### 4.5 Scoring engine

- Dedicated Python module, independently testable; no formula embedded in React components or database triggers.
- Initial simple placeholder score with a **mandatory consistency component**; placeholder weights/thresholds are not final science and must be labelled as development-only.
- Separate 0–100 consistency score calculated against **preceding 30 calendar days**, excluding the evaluated night, with midnight wrapping and DST-aware wall-clock handling.
- Scores carry formula version/parameters and are reproducible; activate a new version through a controlled historical recalculation.
- Missing inputs have explicit policies approved before their implementation.

### 4.6 Local application API

**Proposed:** versioned `/api/v1/...` routes with request/response models (Pydantic via FastAPI).

Illustrative interface families (proposals, not promises of exact paths):

- `GET /api/v1/status`: import freshness, service health, current formula version.
- `GET /api/v1/nights` and `GET /api/v1/nights/{date}`: nightly timeline and latest selected night, including unscored/partial states (latest night implemented as `GET /api/v1/dashboard`; see the U01/X01 section).
- `GET /api/v1/metrics/catalog`: supported metrics, units, scope and completeness.
- `GET /api/v1/analytics/timeseries`: chosen metrics, date window and rolling-average options (implemented as POST; see "U02 chart API and preset contract").
- `GET /api/v1/analytics/correlation`: paired-night results computed in Python (implemented as POST; see the same section).
- `GET/POST/PATCH/DELETE /api/v1/presets`: persistent graph presets.
- `GET /api/v1/analysis/status` and `POST /api/v1/analysis`: AI statistical question scoped to selected metrics/date range, with explicit cost/privacy controls (implemented; see the AI01 section).
- `POST /api/v1/analytics/export`: CSV of computed nightly metrics (implemented as POST; Excel not built, see P22 and the X01 section).
- Inbound `POST /api/ingest`: **separate authentication and request restrictions** from the browser API.

Avoid directly exposing raw measurements, database file paths or unrestricted query executors to browser requests. Browser API security needs review even though this is a single-user local app (including cross-origin and local-network attack surfaces).

### 4.7 Frontend

**Proposed:** React + TypeScript + Tailwind CSS, charting with Recharts. Alternatives remain open if important trade-offs surface.

- Latest selected night at top, including unscored/partial states, with a large SleepIQ Score and individual metrics.
- Further down: individual metric graphs, multi-metric overlay builder, real-value vs normalised trend, date windows, rolling averages, saved graph presets, correlation explorer and contextual AI panel.
- UI uses typed API responses; no independently implemented scoring or HRV calculations in JavaScript.
- Missing, incomplete, syncing and AI-offline states are first-class interface states.
- Visual design/components/interaction details live in `DESIGN.md`; do not choose a visual direction silently.

### 4.8 AI investigator

- Back end computes statistics first (Python: Pandas/NumPy/SciPy as justified). The language model interprets bounded, computed evidence with sample counts, units and qualifiers.
- User's selected metrics and chart window are the default context. Allow a documented, consented expanded scope when their question requires it.
- Use an OpenAI model configurable by setting; economical GPT-6 Luna is the starting candidate, not a dependency on an exact model identity. **Owner-approved A6:** no automatic AI requests on ingest, schedule, or dashboard load: the owner must explicitly initiate each analysis. Scope data sent to selected derived statistics, with cost and privacy controls to be approved.
- No unrestricted SQL generation/execution, arbitrary code, medical conclusions or changes to stored measurements.
- Send only the necessary derived data to the provider, show when AI is unavailable and control provider costs/rate limits.
- Privacy/cost choices require owner approval; implementation and evaluation details live in `SECURITY.md`, `TESTING.md` and AI task briefs.

### 4.9 Export, backups and recovery

- CSV and Excel outputs based on selected nightly metrics and versions; include units and explicit missing values.
- **Owner-approved A7:** daily consistent database backups to a distinct same-PC folder, retaining the latest 14 successful daily snapshots; a missed backup is retried at next app launch (specific scheduling/retention mechanics to be implemented and tested).
- Use a database-consistent backup mechanism (rather than indiscriminately copying a live SQLite file). Retain protected raw/reprocessable data according to an owner-approved retention policy.
- Same-PC backup does **not** protect against full drive failure; owner accepts that trade-off for v1.

## 5. Candidate codebase layout — illustrative only

```text
sleepiq/
  AGENTS.md
  docs/
    PRODUCT.md
    ARCHITECTURE.md
    DATA_PIPELINE.md
    SCORING.md
    DESIGN.md
    SECURITY.md
    TESTING.md
    DEVELOPMENT_PLAN.md
    DECISIONS.md
  backend/
    app/
      api/            # browser endpoints and distinct ingest boundary
      ingest/         # adapter, validation, import orchestration
      domain/         # session rules, nightly metrics, scoring
      analytics/      # trends and statistics
      ai/             # optional, read-only evidence-oriented analysis
      db/             # models, migrations, repositories
      settings/       # typed non-secret configuration and secret loading
    tests/
  frontend/
    src/
    tests/
  test_fixtures/      # synthetic/anonymised data only
  scripts/            # documented local setup, backup and migration
  .github/workflows/  # CI with no real health data or credentials
```

This separates high-impact domain calculations from transport and UI. Avoid proliferating layers and folders without demonstrable need; small modules are preferable to premature abstractions.

## 6. Runtime and developer experience

- **Development:** Windows + VS Code; backend via a Python virtual environment; frontend via a modern JS toolchain. Run on localhost for browser access; expose only the explicitly configured ingest service to iPhone delivery.
- **Normal use:** A simple documented command or local launcher should start everything and expose the dashboard in a desktop browser. **Owner-approved A5:** a manually launched local shortcut/script; do not register a Windows startup task or service by default. Ingestion can occur only while the app is running; accept eventual sync/catch-up as a separately tested requirement.
- **Environment config:** secrets live outside Git; example templates carry names only. No token or medical data in terminal demonstrations, CI fixtures or Git commits.
- **Offline behaviour:** dashboard, charts, scores and correlation explorer work locally; only AI and incoming uploads depend on external network connectivity.
- **Testing and quality:** pytest for parser/domain/API/database, frontend unit tests, Playwright real-browser workflows, type/static checks, dependency/security scanning and CI. The exact checks/commands are in `TESTING.md`.
- **Documentation access:** `AGENTS.md` is intentionally brief, routing each task to at most the relevant doc(s). Planning output uses small actionable tickets, file boundaries, explicit acceptance tests and an approval gate. Codex and Claude Code share the same agent contract; no mandatory `CLAUDE.md`.

## 7. Architectural decisions for owner approval

> **These are questions, not defaults that an agent may treat as permission.** Explain in plain language; owner chooses. Where appropriate, the planner may advise a variation or propose a third option.

### A1. Backend + frontend separation

- **A: FastAPI + React/TypeScript (recommended):** powerful interactive charts, clear independent API, strong Python data tooling. **Trade-off:** two build/toolchains and more setup.
- **B: Python-rendered web app with lightweight JavaScript:** faster initial setup and fewer technologies. **Trade-off:** advanced overlays, chart presets and high-polish interactions may be harder to maintain.

**Owner decision — APPROVED (28 October 2026): FastAPI + React/TypeScript.**

**Original question resolved.**

### A2. Data storage granularity

- **A: Keep validated individual readings + nightly summaries (recommended):** supports future recalculation, genuine overnight HRV, advanced correlations and data audits. **Trade-off:** larger local DB, more complex deduplication.
- **B: Keep nightly aggregates only:** smaller and simpler. **Trade-off:** loses source precision and limits future scoring/analysis changes; conflicts with long-term flexibility.

**Owner decision — APPROVED (28 October 2026): Individual readings and nightly summaries.**

**Original question resolved.** A raw-input retention policy will be a separate follow-up.

### A3. Raw export retention

- **A: Retain raw import batches locally, with configurable retention (recommended for early development):** simplifies debugging and reprocessing when the exporter schema changes. **Trade-off:** duplicates sensitive data and increases disk usage; privacy and backup handling matter.
- **B: Verify/normalise, then discard imported JSON after durable database commit:** smaller privacy footprint. **Trade-off:** less forensic/debugging ability and limited re-import without asking the phone to resend.

**Owner decision — APPROVED (28 October 2026): Raw exports retained with configurable retention.**

**Original question resolved.** Owner will approve exact retention period and deletion semantics during data/security design.

### A4. Long-running secure iPhone-to-PC connection

- **A: Encrypted, authenticated direct connection on trusted home Wi-Fi (candidate recommendation):** minimal external dependencies. **Trade-off:** local HTTPS certificate trust, iPhone compatibility and firewall setup need an implementation spike.
- **B: An approved secure intermediary/relay:** simplifies some connectivity scenarios. **Trade-off:** adds reliance on a third party, cost and potentially sensitive data exposure; must be explicitly authorised.

**Owner decision — APPROVED (28 October 2026): Direct encrypted home-network connection as first approach.**

**Original question resolved.** Direct encrypted LAN is the chosen first approach; P1 selects publicly trusted certificates with DNS-based validation and a generated 256-bit ingest credential. Compatibility testing and concrete setup still require review and authorization. No permanent HTTP+8-character-token configuration.

### A5. Local app startup

- **A: User launches with a simple script/shortcut (recommended initially):** easier to understand and debug. **Trade-off:** requires starting after reboot; receiver may be offline until launch.
- **B: Start automatically with Windows:** better unattended sync availability. **Trade-off:** more permissions/service administration, more complex troubleshooting.

**Owner decision — APPROVED (28 October 2026): A — Manual launch via a simple script/shortcut.** No automatic start with Windows for v1. **Exception P20 (29 October 2026):** the HTTPS ingest receiver only may start at the owner's logon via a per-user scheduled task; the dashboard stays manually launched. **L01 (29 October 2026):** the manual launch is now a Desktop shortcut running `scripts/launch.ps1` (starts `start.ps1` if SleepIQ is not already answering on 127.0.0.1:8765, then opens the browser); still no autostart.

### A6. AI privacy and budget

- **A: AI is off until user invokes analysis; only narrowly selected, derived statistics are sent (recommended):** lower privacy exposure and API cost. **Trade-off:** no proactive AI narrative.
- **B: Automatically refresh an AI insight after each import:** more immediate. **Trade-off:** recurrent costs and uploads, possibly unhelpful insights.

**Owner decision — APPROVED (28 October 2026): A — AI analysis only upon explicit user request.** Exact model, context limits and budget ceiling to be approved later.

### A7. Local data backup schedule and retention

- **A: Daily backup, with a modest rolling history (recommended):** automatic protection against errors and accidental deletion. **Trade-off:** slightly more disk use and rotation logic.
- **B: Backup whenever app launches or data imports:** more timely snapshots. **Trade-off:** many redundant copies or extra maintenance.

**Owner decision — APPROVED (28 October 2026): A — Daily consistent backups, retaining the most recent 14 successful daily backups, locally on the PC.** The app must make its backup status visible, document how missed backups are retried, and include a restoration test.

## 8. Decision gates and sequencing

**Gate 1 — Architecture review: PASSED (28 October 2026).** A1–A7 are approved and recorded below. `DECISIONS.md` records these approvals and P1-P8. This approval does not grant permission to choose unresolved domain rules or deploy an insecure transport.

**Gate 2 — Data semantics:** `DATA_PIPELINE.md` presents choices for nightly date, naps, session boundaries, overlapping samples, duration, aggregation, catch-up and DST. Approval before coding domain rules.

**Gate 3 — Scoring:** `SCORING.md` presents placeholder scoring semantics and missing-data policy. Approval before declaring any score valid.

**Gate 4 — Design:** `DESIGN.md` presents visual style and user interaction decisions; implementation follows approval.

**Gate 5 — Production security and AI:** `SECURITY.md` and AI planning cover network exposure, secrets, consent, cost and safe agent permissions before permanent operation.

**Gate 6 — Quality and rollout:** `TESTING.md` and `DEVELOPMENT_PLAN.md` define objective acceptance tests and milestones; user receives brief what-changed/tested/learned reports.

**Definition of complete for this architecture document:** all major choices have recorded owner decisions; proposed and approved statements are visibly distinguished; no dependencies on the temporary receiver's weak security; implementation agents can locate the relevant deeper documents without loading everything.

## 9. Handoff guidance for coding agents

At the beginning of a task, do **not** read every Markdown file. Use this routing:

| Task | Read first, then only as needed |
|---|---|
| Provider JSON parsing, sync and dedup | `AGENTS.md`, `ARCHITECTURE.md` §4.1–4.3, `DATA_PIPELINE.md`, `SECURITY.md` relevant sections |
| Sleep calculations and consistency | `AGENTS.md`, `DATA_PIPELINE.md`, `SCORING.md`, relevant tests |
| Dashboard or charts | `AGENTS.md`, `DESIGN.md`, API contract in this document, `PRODUCT.md` relevant section |
| Statistical explorer | `AGENTS.md`, analytics contract, `TESTING.md` relevant section |
| AI integration | `AGENTS.md`, `PRODUCT.md` §3.6, `SECURITY.md`, AI acceptance tests |
| Security, backup or deployment | `AGENTS.md`, `SECURITY.md`, relevant architecture decision, `TESTING.md` |
| Planning/coordination | `AGENTS.md`, `DEVELOPMENT_PLAN.md`, `DECISIONS.md`; fetch other documents only for affected workstreams |

Before implementation: summarise task scope, relevant approved decisions, expected changes, tests and any unresolved decision requiring owner approval. After implementation: show what changed, test evidence, how to verify and **one or two concepts learned**. Do not re-ask approved questions unless new evidence changes the trade-off.

## 10. Related documents

- `PRODUCT.md` — approved scope and exclusions.
- `DATA_PIPELINE.md` — detailed source mapping, normalisation and session algorithms (next after architecture).
- `SCORING.md` — consistency and overall score definitions.
- `DESIGN.md` — frontend specifics.
- `SECURITY.md` — trust boundaries and controls.
- `TESTING.md` — fixtures and test gates.
- `DEVELOPMENT_PLAN.md` — work breakdown and model/effort proposal.
- `DECISIONS.md` — approved choices and rationale.
- `AGENTS.md` — concise agent-wide rules and routing.

**Document owner:** SleepIQ owner. **Change policy:** significant edits require explanation, alternatives and explicit owner approval before coding agents act on them.

## Documentation package completion

This document is final for planning. Implementation agents use `AGENTS.md` for task-level context routing and `DECISIONS.md` for owner approvals. Any still-open implementation detail must be proposed with alternatives, pros/cons and an owner checkpoint where consequential; do not delay documentation completion or silently treat a recommendation as approval.

## Planning checkpoint implementation boundaries
P1 selects public-certificate HTTPS with DNS validation, LAN-only ingest and loopback UI/admin. P5 selects SQLAlchemy/Alembic and private data under %LOCALAPPDATA%\SleepIQ, separate same-PC backups and a raw recovery manifest. Concrete DNS/certificate/firewall setup is not authorized by design selection alone.

Use docs/PLAN.md as the sole progress, task and phase-approval record. DEVELOPMENT_PLAN.md describes workflow, not a second roadmap. Build backup/isolated restore before routine real-data ingestion. Keep current root documentation paths; do not create docs/TASKS.md.

## D01 implemented persistence boundary

`backend/app/db/engine.py` creates an explicitly selected SQLite connection pool with modern transaction handling, a five-second busy timeout and foreign-key enforcement on each connection. The caller must supply an existing directory. `db/migrate.py` invokes Alembic on a caller-owned transaction. Revision `0001_settings` creates only the non-secret `app_settings` table with a unique, bounded key and JSON-text value; health observations and presets are not implemented in that revision (Phase 2 adds revision `0002_health` with observations, import batches and derived tables; presets remain Phase 3). Destructive downgrade is refused. No migration runs on app import or browser startup. Real-database migration remains an owner approval gate. Tests use fresh synthetic databases under ignored `.cache/test-runs` and preserve artifacts for inspection.

## Phase 2 ingest and domain boundary

`ingest/` validates and stores (parse, atomic store, CLI, service); `domain/` is pure session/metric/score logic plus `rebuild.py` (SQL orchestration); `transport/probe.py` hosts `/api/ingest`, which stays 503 unless `serve.py` is given `SLEEPIQ_INGEST_DATA`. Imports and backups share `db/coordinator.write_guard`. Details: DATA_PIPELINE.md, "Phase 2 implemented contracts".

## B01 backup foundation

`db/backup.py` implements verified self-contained daily snapshots with immutable manifest inventory and SQLite consistency checks. `db/backup_cli.py` provides daily/verify/restore-isolated commands. `scripts/setup-data.ps1` checks private folders and invokes a new-empty-store initializer and first backup; it never migrates an existing database. This leaves raw/DB import synchronization, normal launcher/runtime scheduling and owner-folder acceptance as explicit integration gates in PLAN.md.

## U02 chart API and preset contract
The loopback application optionally receives an explicitly configured `chart_data` directory; opening it never migrates the store. `start.py` uses the existing owner-configured data directory. `scripts/preview-charts.py` instead creates synthetic data only under `.cache/chart-preview`, serves on 127.0.0.1:8766 and persists preview presets across restarts. `--fresh` creates an independent synthetic store for each browser test run.

- `GET /api/v1/metrics/catalog`: fixed configured nightly metric catalog with units/methods/clock eligibility.
- `POST /api/v1/analytics/timeseries`: bounded Selection JSON (metrics, range 7/30/90/all/custom, start/end dates, actual/normalized mode). Read-only despite POST; avoids large query strings. Returns a dense calendar axis, explicit nulls, values/original values, sample counts, quality flags, clock offsets, normalization metadata and derivation/score versions. Synthetic preview responses explicitly identify synthetic data.
- Relative ranges end at the latest stored wake date; custom endpoints are inclusive. Maximum 10000-day span. Active derive-1/pilot-1 versions only; newest unscored nights remain eligible. Efficiency fractions become percentages; stage seconds become minutes/hours. Python computes population z-scores over observed selected-range samples, not zoomed view. Constant/empty series normalize to unavailable; clock metrics cannot normalize.
- A01: `Selection.rolling` is `off`/`7`/`30`. Each series then carries `rolling` {window, minimum, values, counts, reason}: trailing calendar-window means from `analytics/stats.py`, null below 4/7 or 15/30 observed nights, counts always present. Early windows may use stored nights before the range start. Clock metrics return null values with a reason. Normalized mode applies the selected-range z transform.
- `POST /api/v1/analytics/correlation`: bounded `Pairing` JSON (two distinct non-clock metrics plus the same range fields). Returns same-wake-date pairs, n, exclusion counts (missing_x, missing_y, neither), days, Pearson r or a reason (<3 pairs, constant series, no nights), metric units/methods and versions. Read-only.
- `GET /api/v1/presets`, `PUT /api/v1/presets/new`, `PUT /api/v1/presets/{id}`, `DELETE /api/v1/presets/{id}?revision=N`: bounded named chart selections in existing `app_settings` key `charts.presets.v1` (no migration). Maximum 100, case-insensitive unique names, one default, revision conflicts return 409. Changing defaults increments affected revisions. Mutations use the shared writer gate and a SQLite transaction. UI confirms overwrite/deletion. These endpoints never modify health records.

Chart reads and preset writes reject non-loopback clients, foreign Origin and cross-site/same-site fetch requests. POST/PUT/DELETE require an exact same Origin and `X-SleepIQ-Request: charts`, with a streamed 16 KiB cap before parsing. Successful protected responses use no-store. No CORS, raw exports, filesystem paths or arbitrary queries are exposed. Existing LAN receiver routing is untouched.

## U01 dashboard and X01 export contracts (Phase 3)
- `GET /api/v1/dashboard`: read-only model of the latest stored night: source-local onset/wake strings and offsets, durations, efficiency, physiology values with sample counts (null when missing), stage intervals relative to session start, flags, score status/components/missing reasons/ceiling (null score object if never computed), a 30-calendar-night duration trend (null for unrecorded nights) and import counts. `latest` is null for an empty store. Same loopback, origin and `Cache-Control: no-store` boundary as the other chart routes; 503 when no store is configured.
- `POST /api/v1/analytics/export`: body `{metrics, range, start, end}` (same bounded range rules as charts; 1-15 distinct catalog metrics; unknown fields rejected). Returns `text/csv` attachment with a server-generated file name and `X-SleepIQ-Rows`. Columns: `wake_date`, one per metric with unit, `flags`, `score_status`, `derivation_version`, `score_version`. Needs the same-origin `X-SleepIQ-Request` header as other POSTs.

## AI01 analysis contract (Phase 4)
- `GET /api/v1/analysis/status`: read-only. `state` (`ready`, `disabled`, `not_configured`), model name, limits, local usage counts, and the disclosure text shown in the UI. Never contains the key.
- `POST /api/v1/analysis`: body `{question (3-500 chars), metrics (1-6 distinct), range/start/end, confirm: true}`; unknown fields rejected. Builds the evidence in Python, refuses without contacting the provider when AI is off, unconfigured, over a daily/monthly limit, too large, without data or busy, otherwise reserves a count, makes one provider request and returns `{answer, model, evidence, usage}`. Same loopback, origin, header and no-store boundary as the chart routes.
- Provider boundary (`app/ai/provider.py`): `Provider.complete(system, user, max_output_tokens)`; the OpenAI implementation posts to one fixed URL with no tools. Tests inject fakes or a mock transport.
