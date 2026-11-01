# SleepIQ — Data Pipeline and Sleep Session Semantics

**Status:** Approved v1.0 — D1–D9 approved 28 October 2026; narrower implementation thresholds remain explicit decision gates  
**Depends on:** `PRODUCT.md` v1.0; `ARCHITECTURE.md` v1.0 (A1–A7 approved)  
**Audience:** Owner, backend agents, test authors  
**Purpose:** Specify the journey from Health Auto Export JSON v2 to trustworthy canonical readings, sleep sessions, nightly summary values and downstream scoring inputs. This is *not* the scoring formula.

> **Owner decision authority.** Agents must explain substantive alternative algorithms in accessible language with pros, cons, recommendation, and wait for approval. D1–D9 are approved below. Implementation thresholds and algorithms not explicitly selected remain subject to owner approval. For routine implementation minutiae, choose sensible documented defaults and explain what changed. Never leak real health records or credentials into the repository, logs or AI prompts.

## 1. Approved boundaries and scope

### Exporter documentation evidence (not device verification)

The [official REST API guide](https://help.healthyapps.dev/en/health-auto-export/automations/rest-api/) documents HTTP POST, custom Authorization headers, JSON version 2, automatic application/json content type and optional JSON request batching. These capabilities fit the approved transport; they do not establish successful exporter delivery to SleepIQ.

Distinguish sidebar Manual Export (file creation) from Manual Export inside an API automation (sends actual data to its configured URL). Keep real uploads disabled while the synthetic receiver is in use.

Granularity needs verification. The earlier reviewed guide described multiple selected metrics as always aggregated; the current guide reviewed during HR-1 instead describes Summarize Data OFF as individual readings where available. This documentation change does not verify actual or historical export settings. Do not promise preserved individual readings from configuration alone; compare permitted shape/configuration evidence before changing the approved acquisition design.

Documented date-range options include overlapping days and Since Last Sync; the guide does not establish safe retry/checkpoint behaviour after failure or correction ordering. Extra automation/session headers are untrusted metadata, not proven record IDs or revision clocks. Validate batching, date coverage and failure/retry semantics empirically before relying on them; retain bounded payload limits rather than adopting generic large-upload advice.

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

**Important:** These are sample counts from one inspected export, not a guaranteed full-history inventory. A timestamp can include an explicit `+0100` or `+0000` offset. The 25 October 2026 fall-back creates *visually reversed local clock times* within an actually positive-duration interval. `heartbeatSeries` is nested source data; retain or handle it deliberately rather than implicitly. Observed wrist temperature intervals can span many hours; do not assume they are instantaneous points. The exporter may evolve: validate by observed version/keys and fail safely on unsupported shapes.

### Export date-range evidence (30 October 2026)

Owner-supervised, counts-only diagnosis of a night whose onset showed about 1.5 h late:
- The night came from automatic exports whose sleep data began after local midnight. Neither the stored observations nor the retained raw JSON held any sleep row, under any label, from the four hours before the displayed onset.
- The first exported stage began well after midnight, not at it. This suggests Health Auto Export selects sleep stages by start time within the date range: a stage that crosses midnight is dropped, not clipped.
- A wrist-temperature interval starting before midnight was still included, so selection appears to vary by metric.
- SleepIQ computed the session correctly from what it received.
- An owner re-export of the last 7 days restored the night (3,034 exact repeats skipped, 0 conflicts). The rebuild reaches back two days, which joined the late rows and put the onset back in the evening.

Consequences:
- A range that starts at today's midnight cuts off the pre-midnight part of every night.
- A range ending at yesterday's end omits the latest night, as seen on 29 October.
- Exports must overlap the previous day. Overlap is safe because exact repeats deduplicate.

The owner has since selected Since Last Sync. Whether it misses stages that HealthKit writes after a mid-night sync, with start times before that sync, is **unverified**. Check the next nights' onsets against the owner's recollection.

## 3. Proposed processing stages

### Consequences of the owner-supervised shape diagnostic

The single-file metadata report confirms expected metric/unit blocks and offset-bearing timestamp pairs, while leaving numerical validity, actual source identities, sleep-stage values and current automation settings unverified. Counts and progress evidence live only in PLAN.md.

HR samples have equal start/end instants and Avg/Min/Max rather than qty. Apply the current D6/P4 arithmetic mean fallback to valid in-window Avg readings, with method label, sample count and coverage limitation; never infer measured coverage from point spacing. Estimated point interpolation is specified in [P34](#proposed-sleeping-hr-time-weighting-p34), accepted as an implementation policy in HR-1 but not implemented or active. Respiratory observations are also points. RHR and wrist temperature have positive-duration scope; do not assume instantaneous or full-night attribution.

Recognized observation ID and revision fields are absent throughout this file. Exact repeats may be deduplicated by a specified canonical content identity, but matching timestamps/source/metric alone do not prove that changed values replace older ones. Retain/flag ambiguous changes. Zero reported repeated_identity or changed_identity is inconclusive when no IDs exist. Cross-export delivery/retry/correction evidence and the precise Phase 2 identity algorithm remain unresolved.

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
  → analytics, charts, score inputs
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
6. **Export audit:** Test real future auto-exports to establish whether payloads contain full history, time windows or deltas; use a safe overlap/backfill plan regardless of cadence. Calendar-day ranges cut overnight sessions at midnight (§2, "Export date-range evidence").

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
- HRV is a **different metric**: present overnight HRV as an aggregation of Apple Health SDNN (`qty`, ms) observations occurring within the sleep window; do not weight SDNN values by heart-rate sampling intervals or call the result a full-night SDNN measurement. P4 approves arithmetic mean with at least one valid overnight SDNN sample and visible sample count; one sample does not imply representative full-night coverage. Never invent missing SDNN samples.
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
- **Main-session policy P3:** configurable maximum gap 30 minutes; greatest recorded sleep per source-local wake date; flag ambiguity. Gaps are neither sleep nor awake. Tie, nap-only and completion-evidence rules are resolved by P18 (see "Phase 2 implemented contracts").
- **Travel P3:** source-local wake date and local clock time for consistency; retain offsets, no forced home-zone conversion. Define mixed-offset edge behavior before implementation.
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

**Status:** the gap threshold, session heuristic, HR method and HRV aggregation were resolved by P3/P4/P18 and implemented in Phase 2. Time-weighted HR remains deferred under the active policy; P34 proposes explicitly estimated point interpolation subject to approval. Mixed-offset behaviour: onset/wake use the offsets of the first and last segment rows.

## Proposed sleeping HR time weighting (P34)

**HR-2 candidate implementation, 2026-11-01.** Owner approved HR-2 entry after the HR-1 checkpoint. The pure integrator, nullable metadata and explicit candidate-only derive-2/score-3 rebuild are implemented; P4/P18 simple-mean HR remains active in the application. HR-3 consumer integration and HR-4 real-record operations remain separately gated. Phases/statuses/executed checks live only in [PLAN.md](PLAN.md#sleeping-hr-time-weighting---planning-only-p34-2026-11-01). This does not assert improved measurement accuracy.

### Accepted input and calculation contract

1. Use valid active HR `Avg`, never `qty`, RHR, Min/Max or conflicting/rejected rows. Confirm exporter point-`Avg` semantics: equal start/end does not establish that an `Avg` is suitable for interpolation. Incompatible buckets require a revised proposal. Existing sleep window remains first asleep start to last asleep end, including interior Awake/gaps. UTC elapsed seconds; only inclusive in-window points, no previous/next-night points or edge extrapolation.
2. Proposed source rule: HR stream matching the selected sleep source label if present; otherwise the sole watch-labelled HR stream if unambiguous; otherwise current simple fallback with `ambiguous_source`. Never connect sources. Confirm labels can support this in HR-1. Fallback retains current eligible-row semantics. Sort by UTC; equal-time equal-value points collapse only for integration; different values at one instant require fallback with `ambiguous_timestamp`. Preserve all raw records/correction rules. Nonpoint HR intervals use existing midpoint/simple mean with `unsupported_interval`, not inferred coverage.
3. Connect successive distinct points `(t0,h0)` and `(t1,h1)` by a straight line only when `0 < t1-t0 <= maximum_gap`. Proposed gap limit: **30 minutes**, independent of sleep-session gap. Longer gaps are wholly excluded, not shortened. Duration `d=t1-t0`; area `A=(h0+h1)/2*d`; weighted HR `sum(A)/sum(d)`. Non-overlapping segments within one stream stay inside the window; no whole-hour rounding or extrapolation. Future genuine measurement intervals require a separate coverage/overlap contract.
4. Estimated covered seconds = union length of accepted segments. Coverage = covered seconds / full window seconds, including interior Awake/gaps. This is interpolation support, not proven measurement/wear time. Accepted implementation policy: **>=70% coverage** and >=1 accepted positive-duration segment (>=2 distinct contributing points), with a **30-minute** maximum HR gap. Compare `10 * covered_s >= 7 * window_s` using integers to avoid floating-point threshold ambiguity. These are engineering limits, not validated physiological cutoffs; no runtime change before later phase approval.
5. Eligible method: `time_weighted_linear`. Otherwise return existing `simple_mean_fallback` with reason (`insufficient_points`, `long_gaps`, `low_coverage`, `ambiguous_source`, `ambiguous_timestamp`, `unsupported_interval`), using the HR-1 precedence below. No eligible readings: null/count 0, never substitution. Single reading: simple mean, zero coverage. Coverage is null when ambiguity/unsupported semantics prevent estimation. An absent reading is never a zero HR value.
6. Store/expose method, eligible/contributing counts, estimated covered/window seconds, coverage fraction and fallback reason; finalize field names in HR-1. `hr_mean` remains consumer value; `hr_n` counts points contributing to returned mean (current eligible count on fallback). Version/hash policy constants. HRV SDNN averaging, other physiology, general daily HR, equal weighting across nights, rolling/correlation and zoom-average policies are unchanged.

### Independent synthetic references

- 22:40=50 bpm to 23:00=60 bpm: **20 minutes**, area 66,000 bpm-seconds, segment mean **55 bpm**. Segment maths alone does not establish overnight coverage.
- Add 23:10=80 bpm: durations 20 and 10 minutes, means 55 and 70. Weighted HR `(55*20+70*10)/30 = 60 bpm`; equal sample mean **63.333333... bpm**.
- Exactly 30 minutes connects; 30 minutes + 1 second does not. Exactly 70% coverage qualifies; one second below threshold does not. Excluded gaps/edges enter coverage denominator but not HR-mean denominator.

### Owner checkpoint before implementation

| Option | Benefit | Limitation |
| --- | --- | --- |
| Linear interpolation with gap/coverage guards (recommended) | Actual elapsed time matters; reduces sample-frequency bias | Assumes smooth change; unrecorded spikes unknown; sparse nights fall back |
| Last-value hold with same guards | Simple assumption that previous value persists | Directional bias around changes; assumes constant HR between points |
| Keep simple mean until genuine coverage intervals exist | No new point-to-time assumption | Leaves uneven point sampling unresolved for current export |

The instruction to implement accepts the recommended linear method, 30-minute/70% limits, source/boundary/fallback rules and retained-history approach. Sparse fallback preserves score availability but creates a labelled mix of methods across nights. Strict missing-on-low-coverage would be a separate owner choice and could withhold scores. The running P18 calculation remains unchanged until rollout approval.

### HR-1 input evidence and deterministic result contract

The official [REST guide](https://help.healthyapps.dev/en/health-auto-export/automations/rest-api/) describes JSON Summarize Data off as individual readings where available and on as grouped readings; Time Grouping determines group size. This supersedes the older public-documentation observation in section 1. The official [HR JSON format](https://help.healthyapps.dev/en/health-auto-export/export-format/health-metrics/) defines `Avg` over a measurement period, without proving point semantics for every mode. Existing shape evidence establishes equal start/end. **Owner confirmed Summarize Data is off; Time Grouping is unknown (2026-11-01).** Together these support an explicit individual-point working assumption for synthetic implementation of the current configuration, not a claim of continuous coverage or certification of past exports. No fixed grouping duration is needed: interpolation uses each point's actual timestamp. Do not infer hourly buckets or silently interpolate known summarized data. No private file/live API was read in this review. Historical eligibility and final live activation remain HR-4 gates.

HR-2 implements the HR-1 metadata contract: retain `hr_mean`, `hr_n`, `hr_method`; add nullable `hr_eligible_n`, `hr_contributing_n`, `hr_covered_s`, `hr_window_s`, `hr_coverage`, `hr_fallback_reason`, `derivation_config_hash`. Old rows stay null for new fields. Eligible count includes all currently eligible active in-window HR rows; contributing count is distinct timestamps in accepted segments after integration-only collapse. Weighted `hr_n=hr_contributing_n`; fallback `hr_n=hr_eligible_n`, preserving current arithmetic over original eligible rows. Never invent old coverage.

Reason priority: no eligible readings -> null value/method/reason, count 0; then any eligible nonpoint interval -> `unsupported_interval`; unresolved stream -> `ambiguous_source`; unequal same-instant values in selected stream -> `ambiguous_timestamp`; fewer than two distinct selected points -> `insufficient_points`; no accepted segments despite >=2 points -> `long_gaps`; positive coverage below 70% -> `low_coverage`; otherwise `time_weighted_linear` with null fallback reason. Coverage/contributors are null for unsupported/ambiguous input; known empty segment sets have zero coverage/contributors. Retain precision until display.

Input approval must distinguish future raw-point settings from historical files: present settings do not certify older imports. Unknown/incompatible periods retain the old mean until separately validated or covered by an explicitly approved assumption. Do not change acquisition settings, replace stored readings or reconstruct hourly bucket bounds from adjacent timestamps without approval.

### HR-2 implemented boundary

`domain/heart_rate.py` is a pure calculation using the accepted HR-1 rules. `WeightedDeriveConfig` fingerprints the interpolation assumption and all derivation parameters. Explicit `rebuild(conn, derive=WEIGHTED_DERIVE, score=WEIGHTED_SCORE)` stores candidate rows only after checking exact version/config pairing and the additive schema. `rescore` uses the same guard; mismatched identities, modified policy under the same identity or stored candidate fingerprint disagreement fail before derived-row deletion. Old score/measurement rows, raw observations, HRV and non-HR metrics are retained.

Migration `0003_weighted_hr` only adds nullable HR metadata columns; it does not change measurements, backfill history or activate anything. Legacy calculation remains compatible with schema `0002_health` and `0003_weighted_hr`; weighted selection requires the latter. HR-3 adds explicit owner rollout commands and coordinated active-pair consumers; there is still no automatic startup activation. No migration has been applied to owner data by the agent.

### HR-3 consumers and explicit rollout

Dashboard HR has `quality` metadata; chart HR point details and HR correlation pairs have `hr_quality`. Both contain method, n/eligible/contributing counts, covered/window seconds, coverage fraction and fallback reason. Legacy rows return unknown nullable coverage, never fabricated full coverage. Summary HR includes method counts across selected nights, while all across-night means retain equal night weights. CSV adds `hr_method`, `hr_n`, `hr_eligible_n`, `hr_contributing_n`, `hr_covered_s`, `hr_window_s`, `hr_coverage`, `hr_fallback_reason`, `derivation_config_hash` only when HR is selected; version columns describe the same queried pair. HRV remains unchanged.

Owner `scripts/weighted-hr.ps1` wraps preparation, reviewed activation, rollback and status. The mutating wrapper refuses listening dashboard/receiver ports; owner stops legacy processes first because they cannot enforce new generation guards. Preparation requires explicit confirmation that historical HR inputs are individual readings, preserves original rows/raw files, and prints counts/checkpoint/review token only. Unknown historical settings are not silently accepted by an "approve all phases" instruction. Operational commands/review: [OPERATIONS.md](OPERATIONS.md#weighted-hr-rollout-p34).

## Documentation package completion

This document is final for planning. Implementation agents use `AGENTS.md` for task-level context routing and `DECISIONS.md` for owner approvals. Any still-open implementation detail must be proposed with alternatives, pros/cons and an owner checkpoint where consequential; do not delay documentation completion or silently treat a recommendation as approval.

## Phase 2 implemented contracts (P18)
- Identity: the observed export has no provider IDs, so identity is a content fingerprint (metric, source, instants, offsets, stage, values); exact repeats are skipped. A different fingerprint in the same slot (or overlapping stage rows from an earlier batch of the same source) is stored `conflicting`; the first received stays active and affected nights are flagged `revised`.
- Sessions: per-source chains joined by gaps up to 30 minutes (gaps are neither sleep nor Awake); overlapping rows resolve to the latest start without double counting and flag `overlapping_stages`; leading/trailing Awake trimmed; blocks under 3 h asleep are naps; Apple Watch source preferred (case-insensitive substring), others flagged; wake date is the local date at the window end in that row's offset.
- Physiology: a reading whose midpoint is inside the window counts for the night (HR labelled `simple_mean_fallback` with n; HRV mean of SDNN with n); everything else is a general daily metric. Missing stays missing.
- Rebuild: `domain/rebuild.rebuild(conn, from_date)`; incremental equals clean rebuild. Derived tables carry derive-1 / pilot-1 versions and a config hash.
- Rejected rows are counted by fixed reason codes only; raw JSON is retained content-addressed as `raw/<sha256>.json`.

## Approved planning refinements P3-P5
- Show latest selected night even if unscored; partial/conflicted status is separate from absent score inputs. Age alone does not prove source completeness.
- P4 selects owner-supervised local metadata-only validation. Arrange the specific private input and supervision before access. Actual records, identifiers and payloads never enter agent/model context.
- Exact repeats deduplicate. Automatic corrections require verified identity and revision ordering. Preserve/flag ambiguity without silent overwrite; changed content hashes do not prove identity.
- Preserve daily RHR and long temperature intervals in their actual scope. Weighted-HR coverage/overlap rules and respiratory attribution still require evidence.
- Recompute affected downstream 30-calendar-day consistency baselines after corrections/backfill; incremental results must equal a clean rebuild.
