# SleepIQ — Data Pipeline and Sleep Session Semantics

**Status:** Approved v1.0 — D1–D9 approved 28 October 2026; narrower implementation thresholds remain explicit decision gates  
**Depends on:** `PRODUCT.md` v1.0; `ARCHITECTURE.md` v1.0 (A1–A7 approved)  
**Audience:** Owner, backend agents, test authors  
**Purpose:** Specify the journey from Health Auto Export JSON v2 to trustworthy canonical readings, sleep sessions, nightly summary values and downstream scoring inputs. This is *not* the scoring formula.

> **Owner decision authority.** Agents must explain substantive alternative algorithms in accessible language with pros, cons, recommendation, and wait for approval. D1–D9 are approved below. Implementation thresholds and algorithms not explicitly selected remain subject to owner approval. For routine implementation minutiae, choose sensible documented defaults and explain what changed. Never leak real health records or credentials into the repository, logs or AI prompts.

## 1. Approved boundaries and scope

- Source: Apple Watch → Apple Health → Health Auto Export JSON v2 → encrypted, authenticated direct home-LAN endpoint → FastAPI → local SQLite → local React dashboard.
- Store **original granular readings plus calculated nightly summaries** (A2). Preserve **raw import batches with configurable retention** (A3). Account for overlapping repeated uploads, missed uploads and offline-PC periods.
- Currently configured metrics: `sleep_analysis`, `heart_rate`, `heart_rate_variability`, `respiratory_rate`, `resting_heart_rate`, `apple_sleeping_wrist_temperature`. Include additional *relevant, explicitly configured feed metrics* via a controlled adapter expansion; do not silently ingest the entire Apple Health catalogue.
- Version sleep-session reconstruction and derivation logic independently of the versioned SleepIQ score. Score formulas/weights are specified in `SCORING.md` later. Sleep-efficiency calculation must be isolated behind a versioned, testable function so D5 can be changed later without restructuring stored readings or losing historical comparability.
- No manual tracking, nocturia questions, training notes, daily diaries, official Apple Sleep Score or synthetic unlabelled inputs.
- Manual Windows app launch (A5) means receiver availability is intermittent; reliable incremental recovery must not depend upon an always-on service. Daily same-PC SQLite backups retain the latest 14 successful snapshots (A7).

## 2. Evidence from real ingestion (28 October 2026)

A real ~1.53 MB JSON POST returned HTTP 200 and was saved by the temporary receiver. The *observed* JSON shape is a root `data.metrics` array, where each metric object has `name`, `units`, `data`.

| Metric name | Observed count | Units | Per-reading fields of interest |
|---|---:|---|---|
| `sleep_analysis` | 202 | `hr` | `start`, `end`, `value` (Core/Deep/REM/Awake), `qty`, `source`; also `date`, `startDate`, `endDate` |
| `heart_rate` | 3,390 | `count/min` | `start`, `end`, `Avg`, `Min`, `Max`, `context`, `source` — **no `qty` in inspected sample** |
| `heart_rate_variability` | 28 | `ms` | `start`, `end`, `qty`, optional `heartbeatSeries`, `source` |
| `respiratory_rate` | 320 | `count/min` | `start`, `end`, `qty`, `source` |
| `resting_heart_rate` | 4 | `count/min` | `start`, `end`, `qty`, `source` |
| `apple_sleeping_wrist_temperature` | 4 | `degC` | `start`, `end`, `qty`, `source` |

**Important:** These are sample counts from one inspected export, not a guaranteed full-history inventory. A timestamp can include an explicit `+0100` or `+0000` offset. The 25 October 2026 fall-back creates *visually reversed local clock times* within an actually positive-duration interval. `heartbeatSeries` is nested source data; retain or handle it deliberately rather than implicitly sending it to AI. Observed wrist temperature intervals can span many hours; do not assume they are instantaneous points. The exporter may evolve: validate by observed version/keys and fail safely on unsupported shapes.

## 3. Proposed processing stages

```text
JSON POST
  → transport authentication + request-size/content-type limits
  → durable raw batch (subject to retention policy)
  → schema validation and import metadata (digest, receive time, source, status)
  → per-metric normalisation (units, timestamp offsets, provenance)
  → idempotent upsert into canonical observations
  → session detection and sleep-date assignment
  → timestamp-based nightly metrics + quality flags
  → derived-metric versioned snapshots (rebuildable)
  → analytics, charts, score inputs, optional user-invoked AI summaries
```

**Atomicity:** Never mark a batch 'processed' until the required database operations are committed. Failed or partial batches must be retryable without double-counting. Logging should include counts/status/error codes, *not* raw records.

### Proposed canonical observation contract

- `metric_key`, `provider`, `source_label`, `start_utc`, `end_utc`, `observed_local_offset` (where supplied), `original_unit`, `normalized_unit`, numeric or categorical value, and additional provider-defined fields only when necessary.
- `original_record_hash`, `import_batch_id`, quality flags and source priority. Use UTC instants for comparisons and calculations; retain sufficient zone metadata to reconstruct clock-time charts.
- `heart_rate`: `Avg` as representative sample value (with `Min` and `Max` retained as associated attributes); do not search for a nonexistent `qty` field.
- Sleep-stage `qty` hours is a cross-check against timestamps. For actual elapsed time, compute from timezone-aware start/end instants (D-stage accuracy test); avoid floating-point accumulation error by using seconds internally.
- `resting_heart_rate` is a separate recorded daily metric, **not** interchangeable with sleeping heart rate. Nightly HR uses observations inside the sleep interval.
- For `heart_rate_variability`, label values as *Apple Health HRV / SDNN (ms)*. Overnight HRV must aggregate recorded SDNN observations per an owner-approved policy, not pretend to reconstruct a clinically equivalent full-night SDNN from multiple sample `qty` values.
- Preserve source metadata and unknown optional fields as bounded/raw source evidence where needed. Avoid schema lock-in or quietly discarding unexpected metric names.

## 4. Proposed nightly output contract

Each night has a stable ID, `sleep_date`, `session_start_utc`, `session_end_utc`, local displayed onset/wake, timezone context, stage durations (seconds), total time asleep, time awake, window duration, sleep efficiency, sleeping HR, overnight HRV SDNN (ms, recorded-sample aggregation), respiratory rate, RHR separately, wrist temperature with data-type/period labels, calculation version, sample counts and explicit missing/quality flags.

Store enough derived metadata to answer **how** a value was calculated (chosen source, intervals, counts, policy version). A nightly summary is not a substitute for raw measurements. Date-based queries should use assigned `sleep_date` rather than naïvely splitting at midnight.

## 5. Essential correctness and privacy controls

1. **Offset-aware UTC math:** `2026-10-25 01:48:29 +0100` → `2026-10-25 01:12:31 +0000` means roughly 24 minutes elapsed, not negative 36 minutes. Test spring-forward too.
2. **Overlap/duplicates:** Same readings may reappear in exports. Prevent duplicate sessions and double-counted heart rate or stages on repeat import. Handle provider edits and corrections explicitly.
3. **Session quality:** Detect gaps, overlapping sources, missing stages, short partial nights, non-monotonic timestamps, implausible values and out-of-order uploads. Display uncertainty rather than fabricating plausible data.
4. **Data minimisation:** keep raw files locally according to configured retention and encrypt the transport; avoid cloud upload, real patient fixtures, or exposing receiver publicly.
5. **Reprocessing:** Parser version and calculation version let new rules recompute past nights from canonical observations; preserve auditability and invalidate stale cached summaries.
6. **Export audit:** Test real future auto-exports to establish whether payloads contain full history, time windows or deltas; use a safe overlap/backfill plan regardless of cadence.

## 6. Owner decisions required before implementing sleep calculations

The owner approved D1–D9 on 28 October 2026. The choices below are binding, while numerical thresholds and unresolved semantics remain decision gates before implementation.

### D1. APPROVED — A: Wake-up local calendar date owns overnight session
- **A (recommended): Date you woke up, in local time.** A 22:50 Tuesday–06:30 Wednesday session is Wednesday's night; matches common sleep-app conventions. *Cons:* the session began Tuesday.
- **B: Date you fell asleep.** Aligns with bedtime log and some diary habits. *Cons:* graphs may feel one day behind.
- **C: Configurable convention.** Most flexible, but complicated for trends/consistency and increases testing.

### D2. APPROVED — C: Ignore naps in SleepIQ analysis and nightly scoring
- **A (recommended): Keep naps as separate sessions but exclude them from the main overnight SleepIQ score by default.** Preserves information without distorting nightly trends. *Cons:* requires identifying a main session with robust heuristics.
- **B: Merge every sleep block in a 24-hour window into one total.** Simple aggregate, but can inflate night duration and blur onset/wake.
- **C (APPROVED): Ignore naps for nightly metrics, dashboard analysis and SleepIQ scoring.** Simpler and matches owner preference. Preserve incoming original granular records as required by A2/A3; do not deliberately delete raw nap observations, but do not surface or aggregate them as naps. Distinguishing main sleep from other blocks must be tested.

### D3. APPROVED — A: Join contiguous intervals with configurable gap threshold
- **A (recommended): Same contiguous stage chain plus a configurable gap threshold; pick the main overnight session by a documented rule.** More realistic and tolerant of watch interruptions. *Cons:* needs edge-case tests, owner-approved gap threshold.
- **B: Merge all stage records between fixed evening/morning cutoffs.** Simple, but can accidentally combine separate sleeps or omit unusual schedules.
- **C: Require zero gaps.** Deterministic but fragile to missing samples.

### D4. APPROVED — A: Apple Watch authoritative for sleep stages
- **A (recommended): Prefer the Apple Watch stages as authoritative where present; preserve the other source's raw observations and flag overlap.** Prevents double counting. *Cons:* priority settings might need adjustment for a new device.
- **B: Merge all intervals across sources.** Captures broad coverage but risks inflated duration or conflicting stage labels.
- **C: Reject any night with overlapping sources.** Conservative but may hide usable nights.

### D5. APPROVED — A initially: Sleep-stage efficiency, explicitly replaceable
- **A (APPROVED initially, replaceable): Sleep-stage efficiency = (Core + Deep + REM) ÷ (Core + Deep + REM + recorded Awake), clearly labeled.** Derivable from stage data. *Cons:* excludes any unrecorded time in bed; must not claim to be clinical time-in-bed efficiency.
- **B: Efficiency relative to time in bed using In Bed records, when available.** Closer to conventional efficiency, but In Bed is not confirmed in the current export; missing data becomes common.
- **C: Show both when supported; label clearly and leave in-bed efficiency blank if missing.** Most transparent, but more UI/metric complexity.

### D6. APPROVED — Prefer time-weighted sleeping heart rate; permit explicit mean fallback

- Compute sleeping heart rate preferentially using a **time-weighted average** of validated Apple Health heart-rate `Avg` readings, *only when their time intervals represent reliable measurement coverage*. Clip eligible observations to the chosen overnight sleep window and avoid double-counting overlapping sample intervals. Specify the exact weighting, overlap and minimum-coverage rules in an owner-reviewed implementation proposal before coding.
- If the export timestamps represent point samples, incompatible summary windows or unreliable coverage, **fall back to a simple arithmetic mean** of valid in-window readings rather than asserting false precision. This fallback must be **clearly labelled as a limitation** in the UI/API (e.g. `method=simple_mean_fallback`, sample count and optional reason).
- HRV is a **different metric**: present overnight HRV as an aggregation of Apple Health SDNN (`qty`, ms) observations occurring within the sleep window; do not weight SDNN values by heart-rate sampling intervals or call the result a full-night SDNN measurement. The precise SDNN summary method (initially propose sample mean), minimum samples and labels must be approved with the final implementation details. Never invent missing SDNN samples.
- Keep algorithms independent and replaceable, retain method/version metadata, and recompute past nightly results consistently when the policy changes.

### D7. APPROVED — Missing readings remain missing

- Show **“Missing data”** (rather than an estimate) when a nightly reading is absent, invalid or cannot reliably be derived. **A measurement is not required every day**; preserve gaps in history and charts.
- Never substitute an adjacent-night value, a historical average or daily resting HR for missing overnight measurements. Nightly scores' missing-component behaviour is a separate decision in `SCORING.md`.

### D8. APPROVED — Intelligent deduplication, correction handling and backfill

- Use idempotent ingestion: canonical sample identity where available and a stable content fingerprint otherwise, with overlap-safe reconciliation across distinct batches.
- Preserve provenance, detect and safely handle changed readings, protect against partial imports, and support a separate owner-invoked historical backfill. Whole-file hashes alone are not sufficient.
- The record identity and conflict-reconciliation policy must be validated against exporter behaviour, with explicit tests for repeat, overlapping and corrected exports.

### D9. APPROVED — Preserve original JSON indefinitely during development

- Keep original raw JSON upload batches indefinitely during **development** to enable debugging, parser improvements and reconstruction; make retention configurable for later use.
- Store files locally in a restricted location; never commit genuine health exports to Git, include them in agent context by default, or silently transmit them externally. Require explicit owner approval before implementing deletion or changing the default retention period.

## 7. Remaining implementation decision gates

- **Historical import:** what maximum historical range should the initial backfill attempt, and how does the Health Auto Export app handle API export history and chunking? Owner approved importing as much history as possible, but procedure/capability not yet verified.
- **Main-session threshold:** D3 approved a configurable gap threshold, but the exact default and main-session identification heuristic still need owner approval before implementation.
- **Time zone for travel:** local offset in each measurement vs a single user-configured 'home time zone'; clock change interpretation must be consistent with D1 and later consistency scoring.
- **Granular metric alignment:** hourly vs nightly average respiratory rate, daily RHR attribution and wrist-temperature observation semantics; present options during detailed metric design.
- **Data retention/security:** precise local path, encrypted storage at rest if desired, backups and source metadata retention; consistent with `SECURITY.md`.

## 8. Tests and acceptance gates (proposed; expand in `TESTING.md`)

- Validate real-shape anonymised JSON v2 fixtures with every configured metric and distinct per-metric fields.
- Import same file twice, overlapping history ranges, revised records and out-of-order batches; assert no duplicate canonical observations or sessions.
- Validate inclusive/exclusive interval semantics and stage total equality within explicit tolerances; no negative durations across October/April clock changes.
- Validate heart-rate `Avg` (not `qty`); HRV data points and nested heartbeat series handling; wrist-temperature interval preservation.
- Test cross-midnight sessions, naps, split sessions, sleep time inside unusual day hours, overlapping sources and quality flags.
- Recompute nightly summaries from raw/canonical data after version changes; test no future-night leakage into rolling 30-day consistency baselines.
- Restore from daily local SQLite backup, with integrity check and clear UI indication of backup failures.
- Do not run real exports or secrets inside the committed repository, CI artefacts or AI prompts; use synthetic/anonymised fixtures.

## 9. Minimal agent context routing

- Implementing JSON adapter: read `AGENTS.md`, this document §§2–3 and 5, API/security contract in `ARCHITECTURE.md`, related tests only.
- Implementing nightly session builder: read this document §§3–8, approved D decisions, relevant tests and `SCORING.md` only if an interface needs it.
- Implementing graph/reporting: read the nightly output contract §4, API contract in `ARCHITECTURE.md`, `DESIGN.md` charts section and tests.
- Planning any nontrivial policy change: first surface options with pros/cons, wait for owner selection, then change this document and `DECISIONS.md` before coding.

**Next action:** Proceed to `SCORING.md`. Before implementing the pipeline, resolve the precise D3 gap threshold/session heuristic and D6 timestamp-coverage and HRV aggregation methodology with the owner; do not silently choose these consequential semantics.

## Documentation package completion

This document is final for planning. Implementation agents use `AGENTS.md` for task-level context routing and `DECISIONS.md` for owner approvals. Any still-open implementation detail must be proposed with alternatives, pros/cons and an owner checkpoint where consequential; do not delay documentation completion or silently treat a recommendation as approval.
