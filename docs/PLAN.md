# SleepIQ implementation plan and progress

Last updated: 2026-10-29.

## Authority and current state

This is the **single source of truth for implementation progress**: phase/task statuses, dependencies, blockers, approvals and actual verification evidence. [DECISIONS.md](DECISIONS.md) remains authoritative for owner choices; specialist documents specify behavior. [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) defines workflow. Do not create a second task log.

**Current phase: 2 - ingest/domain/scoring, implemented and verified on synthetic data (see Phase 2 evidence); phase-end commit and Phase 3 approval pending.** Phase 1 was committed as fb23f79; the Phase 1 text below describing its commit as blocked is historical.

**Phase 1 note:** Owner confirmed Phase 1 entry: "Yes i did approve this" (2026-10-28). Foundation exit review passed with P16's explicit phone-test deferral. P17 adds a successful checked local commit to the phase-end checkpoint; it has not occurred. Phase 2 remains unapproved, with no importer implementation or real-data ingestion authorized.

Historic feasibility: documentation reports a successful manual plaintext iPhone POST. This workspace contains no receiver or original experiment artifacts. That evidence is not a secure-ingestion test and is not counted as implementation completion here.

Status vocabulary: `planned`, `in_progress`, `blocked`, `awaiting_approval`, `done`. A task is done only with its acceptance evidence recorded. Record failures and unavailable checks honestly. A completed phase must still receive explicit approval before the next phase starts.

## Approved checkpoint summary

| Decision | Selected behavior |
|---|---|
| P1 / 1.B | Publicly trusted HTTPS with DNS validation; LAN ingest only; 256-bit ingest credential; loopback browser/admin |
| P2 / 2.A | Neutral Deep/REM/physiology = 75; approved duration/efficiency curves; precision preserved, one-decimal display; ceiling 92.5 |
| P3 / 3.A | Source-local wake date; 30-minute gap; greatest recorded sleep candidate; ambiguity flags; latest selected night visible even if unscored |
| P4 / 4.A | Owner-supervised local metadata validation; conservative correction handling; defensible HR weighting/fallback; mean overnight SDNN with >=1 sample |
| P5 / 5.A | SQLAlchemy/Alembic; private local data; 14 successful daily SQLite snapshots; raw recovery manifest and isolated restore |
| P6 / 6.A | Paired Pearson, n>=3 and nonconstant inputs; per-series z-scores; calendar-window rolling means with counts |
| P7 / 7.A | Economical model allocation; AI disabled pending dedicated approval |
| P8 | This progress record, synchronized docs and explicit phase-transition approval |

Full meanings, limitations and superseded decisions: [planning checkpoint](DECISIONS.md#planning-checkpoint-p1p8--approved-28-october-2026). Do not treat this summary as authorization for unspecified infrastructure, paid calls or real-data migrations.

## Phase roadmap and approval ledger

Estimate: five working weeks at roughly 20–25 focused development hours/week, prompt owner reviews and available Windows/iPhone integration sessions. Three weeks is optimistic; TLS/exporter uncertainty can extend the estimate. No automatic background-work promise.

| Phase | Status / entry authorization | Deliverables | Exit gate and next approval |
|---|---|---|---|
| 0 — Plan and reconcile (1–2 days) | done; documentation update authorized 2026-10-28; D-V02/D-V03 passed | P01; synchronized decisions/specifications and this plan | Documentation checks and traceability pass; request Phase 1 approval |
| 1 — Foundation/security (remainder week 1) | in_progress: implementation/checks passed; P17 final commit blocked | F01, D01, B01, S01, E01; isolated environment, schema, launcher, secure synthetic upload, backup/restore | Foundation gates passed with P16; complete checked local commit per P17, then request Phase 2 approval. Actual exporter authentication/delivery remains a before-real-use gate |
| 2 — Ingest/domain/scoring (week 2) | done pending commit; owner approved entry 2026-10-29 ("Complete phase 2") | I01, D02, C01; six metrics, corrections/backfill, sessions, versioned metrics/scores | Domain fixtures exact; incremental rebuild equals clean rebuild; missingness/no-future-leakage gates pass; request Phase 3 approval |
| 3 — UI/analytics (weeks 3–4) | planned; no entry authorization | U01, U02, A01, X01; approved design, charts/presets, statistics, exports | Browser workflows, numerical references, keyboard/missing-data tests pass; request Phase 4 approval |
| 4 — Optional AI (early week 5) | planned; no entry authorization | AI01; local evidence, explicit Analyze, provider boundary | Zero calls without action; approved payload/budget; mocked failures safe. Live validation requires separate spend/disclosure approval; request Phase 5 approval |
| 5 — Hardening/delivery (rest week 5) | planned; no entry authorization | R01; security/performance/regression, real-device delivery/retry, restore drill, Windows guide | Full checks pass; owner demonstrations and operational approval recorded |

If AI approval is deferred, record that limitation and obtain explicit approval to change phase sequencing; never silently declare AI complete or skip a phase gate.

At each boundary record: exit evidence IDs, unresolved risks, next scope, owner approval text/date and limitations. Phase 1 approved 2026-10-28: "Yes i did approve this". Phases 2-5 have no entry authorization.

## Task register

All tasks read AGENTS.md, this plan's relevant entries and approved decisions. Named modules/scripts below are planned paths; consult task status and verification evidence for implemented artifacts. Commands below are **planned acceptance commands, not executed results**. Run Python from SleepIQ's isolated environment; frontend commands from the repository root.

Risk notation: complexity / risk / uncertainty = low, medium or high. Models are recommendations, not delegation authorization. L = gpt-6-luna; T = gpt-6.1-terra; S = gpt-6.1-sol; A = gpt-6-astra.

| ID | Phase / status | Objective, dependencies and bounded files | Acceptance and evidence | Risk; model / cheaper fallback |
|---|---|---|---|---|
| P01 | 0 / done | Record P1–P8; root specs, AGENTS.md and docs/PLAN.md only; no implementation | D-V01 document inventory; D-V02 consistency/link/plan checks; D-V03 synthetic arithmetic check. Evidence below | low/medium/low; L medium / L low with review |
| F01 | 1 / done | Depends P01 + phase approval. Create isolated manifests, .gitignore, backend/frontend smoke scaffolds, scripts/start.ps1, stop.ps1, check.ps1 and synthetic CI. No real-data access | `pwsh -File scripts/check.ps1 -Suite Foundation`: backend smoke, strict TS/build, runtime isolation pass. Manual launch twice prevents duplicate processes; stop closes only owned processes; no autostart | medium/low/medium; T medium / L high |
| D01 | 1 / done | F01/P5. backend/app/db/, migrations and persistence tests; additive synthetic schema first | `python -m pytest backend/tests/persistence -q`: empty/upgrade migrations, uniqueness, rollback and concurrent access pass | medium/high/medium; T high / L high for settled plumbing only |
| B01 | 1 / done | D01/P5. Backup module, backup/restore scripts, isolated fixtures; no live overwrite/deletion | `python -m pytest backend/tests/backup -q`: consistent snapshot, corrupt/disk-full failure, rotation of 14 successful daily copies, one catch-up, raw manifest and isolated restore pass | medium/high/medium; S high / T high |
| S01 | 1 / done (foundation spike; P16 integration gate retained) | F01/P1. Dedicated synthetic transport, scoped approved DNS/certificate/firewall setup, separate loopback dashboard | 29 security tests pass; iPhone TLS health observed; live PC auth/negative/route checks pass; isolated real TLS rejects bad chain/expiry/hostname. Actual exporter auth/delivery and operational renewal integration required before routine real use | high/high/high; S high + A boundary review / T high + same review |
| E01 | 1 / done (single-file metadata; delivery/corrections explicitly unknown) | F01/P4. Owner ran private diagnostic on an existing local export and shared allowed report only; raw file not accessed by agent | Diagnostic synthetic tests and owner report recorded below. Six metrics/expected-unit blocks; zoned point/interval patterns established for this file; recognized ID/revision fields absent. Cross-export identity, delivery/retry/corrections and current REST configuration remain unverified and must constrain I01 | medium/high/high; S high / T high with review |
| I01 | 2 / done (synthetic; real-export import is an owner-run step) | D01/S01/E01 + Phase 2 approval. backend/app/ingest/, synthetic fixtures/tests. Six configured metrics; atomic raw/DB bookkeeping | `python -m pytest backend/tests/ingest -q`: repeat/overlap/reorder stable; verified corrections applied, ambiguity retained/flagged; unsupported shapes visible; invalid batches and crash points cannot partially commit | high/high/high; S high / T high after contract approval |
| D02 | 2 / done | I01/P3/P4 and remaining domain contract approval. domain session/metric modules only | `python -m pytest backend/tests/domain -q`: midnight, DST, gaps, naps, overlaps, ties, HR fallback, SDNN and scoped daily/interval metrics match hand-calculated references | high/high/high; S high + A rule review / T high + same review |
| C01 | 2 / done | D02/P2; scoring/config/rebuild modules and tests | `python -m pytest backend/tests/scoring -q`: exact anchors/neutral values, bounds, required-input missingness, seven prior nights, no future leakage, historical invalidation and clean-rebuild equivalence pass | high/high/medium; S high + A boundary review / T high + same review |
| U01 | 3 / planned | D02/C01 + Phase 3 approval. One reviewable visual proposal before substantive UI; dashboard/status API/components only | `npm --prefix frontend run test -- --run`; `npm --prefix frontend run test:e2e -- dashboard`: latest selected/partial/unscored/missing/error states pass; owner visual approval recorded | medium/medium/medium; T medium / L high |
| U02 | 3 / planned | U01; charts, presets, settings API persistence; all configured supported metrics, actual/normalized overlays and ranges | Frontend unit tests plus `npm --prefix frontend run test:e2e -- charts presets`: 7/30/90/all/custom, gap rendering, preset CRUD/default/restart round-trip and keyboard interaction pass | medium/medium/medium; T medium / L high |
| A01 | 3 / planned | D02/P6, low-coverage/clock-metric contract. backend/app/analytics/ and correlation UI | `python -m pytest backend/tests/analytics -q`; `npm --prefix frontend run test:e2e -- analytics`: paired n, missing exclusions, constants/<3 pairs, z-scores and calendar rolling outputs match independent references | medium/high/medium; S high / T high |
| X01 | 3 / planned | D02/C01/U01. Export endpoints and UI only; CSV first, settle whether XLSX also required before task starts | `python -m pytest backend/tests/export -q`; `npm --prefix frontend run test:e2e -- export`: selected/all metrics/ranges, units, missing values, versions, spreadsheet-formula escaping and secret exclusion pass | medium/medium/medium; T medium / L high |
| AI01 | 4 / planned | A01 + Phase 4 approval; backend/app/ai/ and Analytics panel. Provider/budget/disclosure gate before live request | `python -m pytest backend/tests/ai -q`; `npm --prefix frontend run test:e2e -- ai`: no background calls, minimal approved evidence, no write tools, quota/timeout failures safe, request budget enforced | high/high/high; S high + A privacy review / T high + same review |
| R01 | 5 / planned | Prior gates + Phase 5 approval. Hardening, docs and targeted fixes only; broaden scope only with approval | `pwsh -File scripts/check.ps1 -Suite Full`: static/unit/integration/build/browser/security checks pass. Separate owner-observed real encrypted ingest, downtime/retry, restore and launcher acceptance; record performance workload/results | high/high/medium; S high + A final review / T high + same review |

## Progressive reading and rollback

| Tasks | Read only relevant sections | Demo / rollback safety |
|---|---|---|
| P01/F01 | DEVELOPMENT_PLAN workflow; ARCHITECTURE layout/runtime; TESTING strategy/CI | Show plan/launcher. Revert scoped source changes; no shared-environment edits |
| S01/E01 | SECURITY ingress/privacy; ARCHITECTURE acquisition/browser API; DATA_PIPELINE observed shapes | Show synthetic secure POST and sanitized diagnostic. Stop listener; concrete DNS/certificate/firewall rollback documented before changes |
| D01/B01/I01 | ARCHITECTURE persistence/recovery; DATA_PIPELINE stages/contracts/D8; SECURITY backups; TESTING persistence/import | Demonstrate duplicate import and isolated restore. Backup before live migration; verify restore, never assume downgrade is safe |
| D02/C01 | DATA_PIPELINE D1–D7 and nightly contract; SCORING current curves/consistency/versioning; TESTING domain edges | Explain one synthetic night. New derivation/score versions built separately before active-version switch; preserve source data |
| U01/U02/A01/X01 | DESIGN relevant dashboard/chart/correlation sections, typed API contracts, TESTING UI/analytics/export | Show missing-night/preset/export workflow. Revert scoped UI/API code; preserve user presets and records |
| AI01/R01 | SECURITY egress/gates, PRODUCT AI scope, TESTING completion, relevant runtime docs | Show explicit Analyze and offline behavior; disable AI independently. No real-data restore overwrites during drills |

Each task must include a short Built / Why / Tests / How to verify / Owner input report and one relevant engineering concept. Keep implementation tickets narrow; split before editing if a row cannot fit a reviewable increment, maintaining IDs/dependencies here.

## Remaining phase-specific decisions and evidence

Do not reopen P1–P7 without new evidence. Resolve these items before their dependent task, grouped with the relevant phase checkpoint:

- Phase 1: domain ownership/provider, DNS-based validation and private resolution, renewal credential protection, exact network rule and certificate setup; dependency versions compatible with Windows; backup location/raw-file recovery procedure; specific supervised diagnostic input. No health data may enter agent context.
- Phase 2: source identity/revision evidence; nap-only/tied/overlapping session handling and completion evidence; mixed offsets; valid baseline eligibility and circular estimator/degenerate baseline handling; HR coverage/overlap rules; remaining respiratory/daily metric attribution. Unknown identities must not cause silent replacement.
- Phase 3: one visual proposal; low-coverage rolling display, z-score zero variance and circular clock-metric eligibility; CSV versus additional XLSX requirement. No period-versus-period comparison scope.
- Phase 4: exact provider/model, current cost, hard spend limit, disclosed payload, retention and consent. Core app must work while AI remains off.
- Phase 5: calibrated performance workload/budgets, actual delayed delivery/recovery evidence and operational readiness approval.

## Quality and security gates

- Every implementation task: relevant tests, type/lint checks and updated specification; record command, exit/result, limitations and evidence ID here. Full suite at phase boundaries. Do not bypass failed checks.
- Synthetic fixtures only in Git/CI. Secret/dependency scans required; exact tools chosen in F01, versions locked after compatibility checks.
- Ingest: bounded auth-first processing, content/size/time limits, safe paths, raw evidence outside web roots, no sensitive logs. Atomic bookkeeping and recovery tested at raw-write/commit/recalculation crash points.
- Correctness: UK fall-back sample `2026-10-25 01:48:29 +0100` to `01:12:31 +0000` equals 1,442 seconds; spring-forward/midnight tested. Missing is not zero; naps preserved but excluded; gap time not invented.
- Score: 75 neutral constants and 92.5 ceiling; no score without required HR/HRV/history. Corrected historical input updates affected future 30-day baselines; adding future nights does not change earlier results. Incremental and clean rebuilds agree.
- Recovery: backup before routine real use; 14 successful daily snapshots, failed attempt preserves prior valid copies, isolated restore checks integrity/counts/presets/versions/raw manifest. Raw recovery is explicitly verified, not implied by manifest existence.
- Security: valid iPhone TLS plus negative certificate cases; auth/rotation/request-abuse/origin/host tests; LAN cannot access browser/admin routes; no plaintext fallback or public ingress.
- UI/statistics: no fabricated points; display counts/units/methods; keyboard and reduced-motion checks; presets survive restart; exports have versions/units and no secrets.
- AI: mock network boundary and assert zero calls on launch/import/chart changes; bounded evidence only on explicit Analyze; no arbitrary code/SQL or record mutation; safe provider failures.
- Performance proposal, not yet an approved commitment: one million synthetic physiology observations and five years of nightly summaries; nightly query <1 s, dashboard ready <2 s on owner's PC. Calibrate before adopting budgets; record actual workload/hardware/results.

## Model allocation and cost evidence

P7 approves cheaper capable models for routine work and premium review at risk boundaries. Current session advertises L/T/S/A identifiers above; account quotas and subscription cost were not inspected. No subagents or paid calls authorized by this table.

Official API pricing checked during planning on 2026-10-28: standard short-context input/output per million tokens: Luna $0.10/$0.50, Terra $1/$5, Sol $2/$10, Astra $10/$50 ([pricing source](https://developers.openai.com/api/docs/pricing)). These are API rates, not Codex subscription charges; recheck before paid use. Small scoped prompts and one active implementation ticket reduce cost. Escalate for uncertainty/failure, not formatting.

## Verification evidence log

| ID / date | Actual check | Result / limitation |
|---|---|---|
| D-V01 / 2026-10-28 | Read AGENTS.md, root planning prompt and relevant specs; `rg --files --hidden`, `git status --short`, runtime discovery | Documentation-only workspace; not a Git repo; no code/tests. Python resolves into another project's environment (3.13.16); Node 26.8.1/npm 11.19.0 detected. No compatibility or application pass claimed |
| D-V02 / 2026-10-28 | `python -` with inline pathlib/re assertions: UTF-8 decoding, local links/heading anchors, unique task IDs, plan routing, phase gate and selected stale-rule checks | PASS (exit 0): 12 Markdown files, 4 local links/anchors, 15 unique task IDs; single scoring status; no obsolete nearest-slope/internal-rounding rule; no competing task log. Manual review of P1-P8 mapping and remaining gates completed |
| D-V03 / 2026-10-28 | `python -` inline Decimal/datetime reference assertions | PASS (exit 0): synthetic scores 92.5 and 80.25; 5-hour duration subscore 5; 40% efficiency subscore 30; fall-back interval 1,442 seconds. Documentation references only, not application tests |

## Foundation evidence and blocker (2026-10-29)

- Phase 1 entry reaffirmed by owner: "Okay lets get started with phase 1". Work remains inside this phase.
- F01 source scaffold added: FastAPI health/static app with loopback host allowlist, three backend tests, React/strict TypeScript setup page, local Python environment, dependency manifests, ignore rules, PowerShell setup/check/foreground-start scripts and SETUP.md.
- `uv --cache-dir .cache/uv venv --python 3.13 --no-python-downloads .venv`: PASS, isolated CPython 3.13.16 environment. Initial default-cache attempt failed due access restrictions; workspace-local cache succeeded.
- `uv --cache-dir .cache/uv lock`: FAIL, PyPI connection refused after retries. `npm.cmd --cache .cache/npm --prefix frontend install --ignore-scripts`: FAIL, ENOTCACHED in cache-only environment. No lockfiles/dependencies installed. F01 blocked on package access, not owner phase approval.
- `.venv/Scripts/python.exe -m compileall -q backend`: PASS. PowerShell Parser.ParseFile for check/setup/start scripts: PASS. These are syntax checks only; backend tests, TypeScript build, browser behavior, dependency audits and startup have NOT run.
- Remaining F01: resolve/pin/lock dependencies, frontend tests, lint/types/build/backend tests, security/dependency scanning and CI, launcher duplicate-instance/stop tests. Foreground Ctrl+C launcher is a preliminary implementation, not the final tested background controller. Do not mark F01 complete.
- Owner confirmed registrar Porkbun and domain mgilham.online. Read-only NS lookup on 2026-10-29 returned ruth.ns.cloudflare.com and ed.ns.cloudflare.com: authoritative DNS is Cloudflare, not the registrar. Owner confirmed on 2026-10-29 that mgilham.online appears in their Cloudflare dashboard. Zone access established; credentials have not been requested or created. Determine router/local DNS capabilities before finalizing private hostname resolution. No DNS/email settings modified; preserve existing mail records. Candidate ingest hostname sleepiq.mgilham.online is a proposal, not yet approved.

- Owner identified home broadband as EE and router as Smart Hub SH32B. Model capabilities have not yet been verified; no router changes made. Finish F01 dependency installation before guided router/certificate setup.

## Dependency progress and checks (2026-10-29)

- Owner ran `uv lock` successfully (30 packages), then confirmed `uv sync --locked --python .venv/Scripts/python.exe` succeeded. Python dependencies are now installed; previous statement that no dependencies were installed is historical.
- Backend lint initially found one import-order issue; targeted Ruff fix applied. Recheck PASS. Mypy PASS (2 source files).
- Pytest: 2 passed, 1 setup error caused by denied temporary-directory access in this session. Retry with unique workspace basetemp and cache provider disabled still failed on temporary-directory permissions/cleanup. No full test pass claimed. Starlette also emitted an httpx deprecation warning; review test-client dependencies before F01 completion.
- Frontend install retry still failed ENOTCACHED in this session. Next owner-assisted step: `npm.cmd --cache .cache/npm --prefix frontend install --ignore-scripts` from project root. Then build/test using the installed dependencies. F01 remains blocked/incomplete.

## Frontend installation and build evidence (2026-10-29)

- Owner completed npm install: 43 packages added, 44 audited, zero reported vulnerabilities. This is npm audit evidence, not a complete security review.
- `npm.cmd --prefix frontend run build`: initial failure TS2882 (CSS import declarations). Added frontend/src/vite-env.d.ts referencing vite/client; rerun PASS, Vite 8.3.5 built 15 modules.
- Backend Ruff and Mypy rerun: PASS. FastAPI TestClient smoke initially failed because the static-directory path pointed outside the project. Corrected the path to root/frontend/dist; rerun PASS for homepage HTTP 200, exact health response and /.env HTTP 404. No real health data accessed.
- Next owner verification: manually launch scripts/start.ps1 and open http://127.0.0.1:8765. Full F01 completion still requires unresolved test/environment, launcher, dependency locking/pinning and CI items; Phase 1 remains in progress.

## Foundation check completion evidence (2026-10-29)

- Owner confirmed the local setup page looks good after manually launching scripts/start.ps1. This verifies the preliminary manual launch/browser connection, not the whole Phase 1 gate.
- Replaced the writable temporary static-site fixture with committed synthetic test_fixtures/web/index.html. First run exposed an incorrect fixture path (2 passed/1 failed); corrected it and reran. Tests still check successful static serving, same-origin health API and private-file exclusion; no security gate removed.
- Added health-response tests for valid/invalid JSON shapes, HTTP failure, network failure and cancellation forwarding. Vitest's default forks failed with spawn EPERM; thread workers execute the same tests successfully. Package test command now uses threads.
- Frontend direct package versions pinned to installed lockfile versions; synchronized root lockfile dependency metadata. No dependency versions changed or new package downloads needed.
- `powershell -File scripts/check.ps1 -Suite Foundation`: PASS, exit 0: Ruff, Mypy, 3 backend tests, 7 frontend tests, strict TypeScript check and Vite build (16 modules). Existing Starlette/httpx deprecation warning remains visible and needs compatibility review before F01 completion.
- F01 now in_progress rather than package-blocked. Remaining scope: reproducible-install/CI and security-scan wiring, launcher ownership/duplicate-instance/stop verification, and test-client deprecation review. D01/B01 remain planned and require F01 completion. No Phase 2 advancement.

## Continued Phase 1 verification (2026-10-29)

- Added subprocess launcher ownership test on an ephemeral loopback port, leaving the owner's running port 8765 untouched. Verified second listener exits nonzero while original responds; test terminates only its own process handles.
- `powershell -File scripts/check.ps1 -Suite Foundation`: PASS, exit 0, after launcher test addition: Ruff/Mypy, 4 backend tests, 7 frontend tests and production build. Existing httpx deprecation warning remains visible.
- Added scripts/security.ps1: source-only secret detection using detect-secrets, Python dependency audit using pip-audit, frontend npm audit; findings/unavailable audits fail the command. No private .env or health exports are included in scan input. Added Windows GitHub Actions workflow with read-only repository permissions and locked dependency installation. Workflow/security execution NOT yet verified; no push or remote workflow run performed.
- PowerShell parser checks: PASS for check/security/setup/start. setup.ps1 now preserves an existing project environment.
- Attempted local install of approved SQLAlchemy/Alembic, audit tooling and httpx2: FAIL, registry connection refused after retries. Added sqlalchemy/alembic runtime dependencies, pip-audit/detect-secrets development dependencies, and switched deprecated direct httpx test dependency to httpx2 in pyproject.toml. Lockfile now needs refresh and sync from owner's network-enabled terminal. No database schema/migration or real data touched.
- F01 blocked on dependency refresh/security-tool verification, not Phase 1 approval. D01/B01 remain planned; SQLAlchemy/Alembic source APIs reviewed in official documentation, but no untested storage implementation added ahead of the foundation gate.

## Scoped dependency permission and installed tools (2026-10-29)

- P9 approved by owner: routine project-local dependency downloads, resolves/locks/installs and package-metadata advisory checks may proceed without repeated permission within an approved phase. AGENTS.md and SECURITY.md specify the narrow scope and unchanged infrastructure/global-install/private-data/paid-service gates. Documents cannot override session network restrictions.
- Owner confirmed lock/sync completed. Local importlib.metadata check verified installed versions: SQLAlchemy 2.1.6, Alembic 1.20.1, httpx2 2.16.0, pip-audit 2.10.1, detect-secrets 1.5.0. F01 unblocked for tool execution; security/audit results still pending.

## Post-install verification (2026-10-29)

- `powershell -File scripts/check.ps1 -Suite Foundation`: PASS after refreshed dependencies: 4 backend tests, 7 frontend tests, Ruff/Mypy and production build; prior httpx deprecation warning resolved by httpx2.
- `powershell -File scripts/security.ps1`: FAIL before auditing, detect-secrets multiprocessing hit Windows pipe permission denial. No secret-scan or audit pass claimed. Investigated installed library: single-file scan avoids multiprocessing; next implement a serial source-only scan with the same detectors and private-file exclusions, then retry audits. Do not weaken detection or bypass the gate.
- Scoped permission documentation consistency checks: PASS across AGENTS.md, SECURITY.md, DECISIONS.md and PLAN.md. Owner consent changes repository guidance only, not tool sandbox permissions.

## Serial secret scan and audit gate (2026-10-29)

- Added scripts/scan_source.py using the same detect-secrets default detectors/filters serially. Whole inventory is validated before content reads; private/escaping/symlink candidates fail; ignored local files excluded. Findings display filenames only, no values. Readable current-source checks prevent silently skipping inaccessible candidates. Deleted tracked files are not scanned.
- Secret scan PASS: 37 source files before scanner tests; final scanner rerun after tests recorded by command output. Added tests for synthetic in-memory credential detection, private/escaping path rejection and valid source path.
- `powershell -File scripts/check.ps1 -Suite Foundation`: PASS, exit 0: 11 backend tests, 7 frontend tests, Ruff/Mypy and production build. Scanner Ruff check PASS.
- Security script audit invocation corrected: workspace cache set; removed unsupported --disable-pip mode for installed-environment audit. `powershell -File scripts/security.ps1` now passes secret scanning but FAILS at Python advisory service connection (blocked proxy/network). This is an unavailable audit gate, not a finding and not a pass. Do not change proxies or bypass security checks. No dependency or npm audit result claimed for this run.
- F01 blocked awaiting owner-run network-enabled security command. D01/B01 cannot start under the current F01 prerequisite until the security gate is satisfied. No additional phase authorization needed.

## Foundation security gate satisfied (2026-10-29)

- Owner ran scripts/security.ps1 in their normal terminal and reported: secret scan 38 source files/no findings; Python audit no known vulnerabilities; npm audit zero vulnerabilities. This is owner-reported network-enabled evidence; local foundation/scanner checks were independently executed as recorded above.
- F01 complete: locked package installs, passing static/types/backend/frontend/build checks, manual browser confirmation, duplicate-listener ownership test, secret scan and dependency audit, CI workflow prepared. Remote CI has NOT run (no push authorized/performed). Foreground manual launcher with Ctrl+C is the implemented startup/stop flow; no separate background process controller or stop.ps1 is needed for this increment. Full release command remains gated. No source-control commits or deployment implied.
- D01 now in_progress: build SQLAlchemy/Alembic persistence infrastructure and first non-secret app-settings migration on synthetic test databases only. No live health schema/import or production migration.

## D01 persistence evidence (2026-10-29)

- Implemented explicit SQLAlchemy engine setup and caller-transaction Alembic migration; only non-secret app_settings foundation, no health-data schema/import. No migration on app startup and no production DB touched.
- `python -m pytest backend/tests/persistence -q -p no:cacheprovider` from the project environment: PASS, 4 tests (repeatable migration preserves settings and records revision; duplicate-key transaction rolls back completely; 12 concurrent writes preserved; missing directory not created). Mypy PASS for 7 source files. Ruff lint/format applied successfully.
- Test databases live only under ignored workspace .cache/test-runs with no real health records. Foreign-key enforcement and current migration revision asserted. No destructive downgrade implemented.
- Full regression: `powershell -File scripts/check.ps1 -Suite Foundation` PASS (15 backend tests, 7 frontend tests, Ruff/Mypy, build); serial secret scan PASS for 45 source files, no findings. No dependency versions changed since the owner-reported audit.
- B01 needs owner choice of actual backup folder and raw-file recovery strategy as reserved in P5, SECURITY.md and this plan. Proposed checkpoint: full daily self-contained DB+raw snapshot (simpler restore, more disk use) versus daily DB plus shared content-addressed raw archive (less duplication, more implementation/recovery complexity). No real snapshot/deletion/retention operation performed.

## Next action and handoff

Phase 1 exit review passed, incorporating P16. Do not ask owner to build the optional Shortcut or run the credential viewer. Present foundation deliverables, final 72 backend/13 frontend tests and remaining integration limits, then request explicit Phase 2 approval. Proposed Phase 2: synthetic importer/deduplication, domain/session calculations and scoring under approved rules; resolve consequential domain contracts before implementing them. Include actual Health Auto Export authentication/delivery and operational renewal integration before routine real-data use. Real uploads, production migration and credential disclosure retain their separate gates. Router reservation deferred per P12. Do not begin Phase 2 until approval.

## B01 entry approval (2026-10-29)

P10 approved: self-contained daily database + raw JSON snapshots in C:\Users\Matth\SleepIQ-Backups, latest 14 successful days. B01 in progress on synthetic scratch data only. Backup default/folder authorization does not authorize reading real exports or overwriting any live database. No repeated question needed for this choice.

## B01 backup implementation evidence (2026-10-29)

- P10 implemented: full SQLite backup API snapshot plus JSON copies/hash manifest, isolated new-directory restore, verify-before-publication, 14-successful-date rotation, repeat-date reuse and single current-date catch-up. Unknown/corrupt/failed folders are preserved; no recursive delete or live restore implemented. Source raw data is never rotated/deleted.
- Backup-specific tests PASS: 13 cases cover full restore/settings and raw bytes, empty raw restoration, repeated date, retention, downtime, simulated disk-full, corruption/checksum and actual SQLite integrity, committed WAL data, traversal, unsupported raw files, existing-target safety and unknown-file retention protection.
- Initialization tests PASS in earlier full run: new empty store only; no existing DB overwrite; nonempty raw refused. Full regression before final empty-raw addition passed 29 backend/7 frontend tests plus types/lint/build. Final run recorded separately below.
- Durability improvement initially failed Windows fsync tests (read-only descriptor); corrected stage-file mode to r+b before fsync; all 13 backup tests then passed. No failure bypassed.
- Added setup-data.ps1/private-folders.ps1 and RECOVERY.md. All PowerShell scripts passed parser checks; positive live-folder execution is pending. Tests/provisioning have not accessed real health records or written the approved external data/backup folders from the agent session.
- B01 blocked on owner-assisted provisioning, not a new design approval. Next run `powershell -File scripts/setup-data.ps1` in normal non-admin project PowerShell. This creates the approved private folders and first empty baseline only. If an existing DB or broad ACL is detected, stop and inspect rather than overwrite/weaken checks.
- Still pending before B01 done: owner-folder provisioning/isolated restore demonstration, daily launcher/long-running scheduling and importer/write-coordination integration. E01/S01 remain planned. No advance to Phase 2.

- Final B01 regression: `powershell -File scripts/check.ps1 -Suite Foundation` PASS (30 backend tests, 7 frontend tests, Ruff/Mypy and build); final serial secret scan PASS (54 source files, no findings). No dependency versions changed since the owner-run vulnerability audits.

## B01 operational integration (2026-10-29)

- Owner ran setup-data.ps1 successfully: new empty DB initialized, first daily snapshot verified, private folder checks passed in normal Windows session.
- Agent independently verified the explicitly owner-created empty 2026-10-29 snapshot and restored it into a new ignored .cache/restore-drills UUID folder: PASS, one manifest entry; no live target overwritten or health exports inspected.
- Added backup lifespan service: launch-time verification/catch-up, hourly new-date/retry checks, sanitized readonly status API, visible setup-page backup message, and shutdown stop. Manual start.ps1 validates private folders and opts in the approved paths; generic create_app/tests do not discover or read private data by default.
- Added Windows cross-process/thread data-write guard shared by service and backup CLI. Future importer must use the same guard for raw publication and DB commits. Tests assert conflicting writer lock timeout rather than bypass. No importer exists yet.
- Backup tests PASS (17) including runtime date advancement, failed backup remains visible with healthy dashboard endpoint, successful retry, restart catch-up, shutdown stops polling and writer-lock conflict. Ruff/Mypy PASS (13 source files). Frontend status-message tests added; final regression pending.
- E01 diagnostic tooling now in_progress using synthetic input only; no real export selected/accessed.

## B01 completion and E01 tooling (2026-10-29)

- B01 complete: owner private-folder provisioning/initial snapshot succeeded, agent baseline verification and isolated restore passed, runtime scheduling and guarded CLI integrated, sanitized backup status shown in API/setup page. Shared writer gate is required for the future importer; no importer or production observation schema exists yet. Owner restart of manual launcher activates new runtime code; no service started automatically by agent.
- E01 metadata diagnostic implemented and 9 targeted tests PASS: all six metric shapes, no values/timestamps/IDs/source/heartbeat/unknown-name leakage, malformed envelope/row handling, offset-aware fall-back interval classification, identity repetition/change counts with explicit not-verified disclaimer. Ruff/Mypy PASS. Size-limited, owner-selected local-file CLI and PowerShell wrapper added; docs/EXPORT_DIAGNOSTIC.md explains safe invocation.
- E01 remains blocked on owner-supervised choice/run of a real local export. No real export path selected, discovered, opened or uploaded by the agent. A single-file report cannot establish delivery/revision semantics; those remain evidence gates. S01 concrete certificate/private-resolution proposal remains planned, no DNS/API token/firewall changes performed.

- Final B01/E01 regression: Foundation command PASS, exit 0 (43 backend tests, 13 frontend tests, Ruff/Mypy, production build). All PowerShell scripts parse successfully. Final serial secret scan PASS (65 source files, no findings). No dependencies changed since the owner-run audits.

## Export availability and S01 sequencing (2026-10-29)

Owner has not configured a saved JSON export; earlier manual test succeeded. E01 remains pending owner-supervised data availability, not a blocker for independent S01 work. Do not require the owner to upload/recreate a raw file merely to continue secure transport preparation. No real export accessed. S01 in progress: public-certificate/direct-LAN design per P1, with concrete hostname/DNS/firewall actions still awaiting their reviewable setup gate. CIM network/profile discovery was denied in this session; no network/profile changes made.

- S01 readonly reconnaissance: ipconfig found current PC IPv4 192.168.1.190/24; stability/reservation and Windows Private profile not yet verified. Public A lookup returned Cloudflare addresses for both sync and sleepiq hostnames; explicit-versus-wildcard DNS configuration unknown. Do not replace existing records. Draft docs/SECURE_SETUP.md records concrete proposal/boundaries and reference sources, with no deployment authorization implied.
- Next owner check is Cloudflare DNS record names/types for *, sync, sleepiq. No token creation, DNS changes, certificate downloads, listener exposure or firewall edits performed. E01 remains pending future local export availability; owner should not recreate a raw file just to unblock independent S01 preparation.

## S01 owner DNS observation (2026-10-29)

Owner reports a wildcard CNAME named *.mgilham.online. This explains generic subdomain resolution, though individual record absence must still be checked before adding one. Preserve the wildcard and all email/root records. Proposed specific DNS-only A record: sync -> PC private IPv4 (last observed 192.168.1.190); TTL Auto. Recheck current IPv4 before action. This record would override wildcard handling for sync only; it does not open a port or deploy a receiver. Creation remains awaiting explicit owner approval and absence of an existing explicit sync entry. Router reservation and iPhone resolver compatibility remain unverified.

## S01 P11 DNS action approval (2026-10-29)

Owner approved adding NEW DNS-only A record sync.mgilham.online -> 192.168.1.190, TTL Auto, preserving wildcard/root/mail records. Do not request this same approval again. No record has been added by agent. Execution requires authenticated Cloudflare dashboard/API access; never ask owner to paste an API key into chat. If explicit sync exists, stop before replacement. Certificate/client/firewall steps retain separate concrete setup gates.

## S01 DNS verification (2026-10-29)

Owner saved the P11 record. `Resolve-DnsName sync.mgilham.online -Type A -DnsOnly` independently returned 192.168.1.190: PASS for PC resolver; iPhone Wi-Fi resolution still unverified. No agent-authenticated DNS write performed. Current PC address reservation remains pending before relying on permanent delivery. Certificate tool research found official lego v5.5.2 release; this is not approval to download/execute a GitHub binary or create certificate credentials. No certificate, firewall or receiver exposure action performed.

## S01 router deferral P12 (2026-10-29)

Owner requests no address-reservation setup now. Recorded P12; leave EE hub unchanged. Proceed with S01 synthetic receiver tests and a reviewable certificate/client/token proposal. Recheck current IPv4 before infrastructure action. Revisit stable address before dependable routine syncing, not as a current coding blocker. No blanket TLS bypass approved.

## S01 synthetic transport boundary (2026-10-29)

- Added separate app.transport.probe factory, with no browser/admin routes or disk writes. Only synthetic {probe:sleepiq} is accepted at /transport-check; /api/ingest returns 503 so exports are not acknowledged and discarded as successful imports. No listener launched or firewall opened.
- HTTPS scheme, expected hostname and private IPv4 source checks; ignores forwarded source headers; browser Origin requests denied; constant-time fixed-length digest credential check, generated 256-bit token format and rotation; rate-limits authenticated/unauthenticated requests and health; bounds request body/chunks and total body timeout; rejects unsupported compressed/type inputs without leaking payloads.
- Security tests PASS (15); Ruff/Mypy PASS (17 source files). One initial rotation-test fixture incorrectly handled ASGI lifespan; replaced it with actual FastAPI downstream and reran successfully. No security assertion bypassed. These ASGI tests are not evidence of real TLS/certificate/iPhone compatibility.
- Real certificate/client/token setup approval is next. P12 router deferral remains binding; no router steps requested. Existing P11 hostname record remains verified from PC. E01 remains pending local export availability.

## S01 certificate checkpoint preparation (2026-10-29)

- Prepared docs/CERTIFICATE_SETUP.md with automatic scoped-token DNS validation (recommended) versus manual TXT proof. Common client proposal is official immutable lego v5.5.2 Windows x64, exact public release checksum, local .tools folder; no privileged install. Prepared bounded installer, DPAPI token-store and staging-first issuer wrappers. No script executed with real token, no binary downloaded and no certificate requested.
- Token wrapper checks private folders and refuses overwrite; issuer uses a child-only credential environment, strips inherited global provider keys/URLs/lego overrides, preserves proxy restrictions, captures output without raw logs, times out only its owned process and explicitly requires owner terms acceptance. Actual credential/client behavior still pending, not claimed from syntax checks.
- Foundation regression PASS (60 backend tests, 13 frontend tests, Ruff/Mypy, build), including 16 transport tests and one bad-archive checksum rejection test. All PowerShell scripts parse successfully.
- Secret scan initially flagged the public vendor SHA-256 checksum in lego-tools.ps1. It is identical to the immutable official release digest, not a credential. Added a documented single-line detect-secrets allowlist for that public hash only; all actual credential detectors and synthetic credential-detection tests remain enabled. Final scanner rerun result recorded separately.
- S01 awaiting the specific certificate/client/DNS-token approval, not a repeated Phase 1 or P11/P12 approval. Ask owner A (zone-scoped token stored Windows-encrypted, automatic TXT proof/renewal) or B (manual TXT each time, no DNS token stored). Firewall/listener deployment remains a separate concrete gate. E01 data availability still pending. No Phase 2 advancement.

- Final S01 preparation secret scan PASS: 75 source files, no findings; PowerShell parser checks PASS. Only the public artifact checksum has a line-specific allowlist with provenance documented above.

## S01 certificate option A approved P13 (2026-10-29)

Owner selected A. Proceed with the exact pinned client/zone-restricted token/Windows-encrypted storage and DNS-01 staging/production scope in CERTIFICATE_SETUP.md; do not re-request this approval. Terms acceptance is an explicit command flag; firewall/listener activation still has its own gate. Attempt client download before requesting owner terminal assistance. Token will be entered only into the local hidden prompt, never chat.

- P13 execution attempt: `powershell -File scripts/install-lego.ps1` FAILED in this session at Invoke-WebRequest (connection closed/unexpected receive error). No archive extraction/execution, credential creation or certificate request occurred. Do not bypass proxy/TLS controls. Owner-assisted next step is the same approved installer command in normal PowerShell; it checks the pinned vendor archive hash before extracting project-local files. No renewed design approval needed.

## S01 pinned tool installed (2026-10-29)

Owner ran the absolute-path installer successfully: Lego 5.5.2 archive verified/extracted locally; no certificate requested. Previous relative-path error was resolved by using the full script path. Next owner-only step is authenticated Cloudflare token creation with Zone DNS Edit + Zone Zone Read, resources restricted to specific zone mgilham.online. Keep wildcard/root/mail records unchanged; do not share the key in chat. Save locally only through save-cloudflare-token.ps1 hidden prompt. No certificate account/terms acceptance, TXT mutation or listener/firewall action yet.

- Agent version check: `.tools/lego/5.5.2/lego.exe --version` PASS, exit 0, reports lego version 5.5.2 windows/amd64. No certificate requested.

## S01 credential rotation required (2026-10-29)

Owner reports successful local DPAPI token storage, but a later pasted Authorization command fragment exposed the token in conversation. Secret value is not reproduced or persisted in project files. Treat that credential as compromised; owner must revoke it in Cloudflare and create a same-scope replacement. No API call/certificate issuance with the exposed credential is authorized or performed. The separate -H fragment is unnecessary for these PowerShell wrappers.

Prepared explicit save-cloudflare-token.ps1 -Rotate, replacing the local encrypted blob atomically after writing a new temporary encrypted file. Requires an existing token for rotation, refuses silent initial overwrite, and does not create a backup of the old credential. Parser check passed; real token not read/decrypted/modified by agent. New key must be entered only at the hidden local prompt. Resume staging only after revocation and local replacement are confirmed.

- Rotation platform check: initial .NET File.Replace with PowerShell $null failed (coerced empty path); original synthetic file stayed intact. Corrected script to use [NullString]::Value. Retry reached File.Replace but was blocked by session filesystem permissions (access denied); no successful atomic replacement is claimed. Original synthetic file was preserved on failure. Real rotation must execute in the owner normal session after revocation. No real token read or modified; no Cloudflare revocation/new-key validity claimed.

## S01 local token replacement confirmed (2026-10-29)

Owner ran save-cloudflare-token.ps1 -Rotate successfully in normal Windows PowerShell; replacement DPAPI storage confirmed by script output. No token value was included in the replacement report. This validates real local replacement behavior after session-only filesystem test restrictions. Agent has not opened/decrypted the blob or used the replacement for an API call. Revocation/deletion of the exposed Cloudflare token has not yet been explicitly confirmed; certificate requests remain paused until confirmation. Local replacement alone does not revoke the provider credential.

## S01 provider revocation confirmed (2026-10-29)

Owner explicitly confirmed deletion of the exposed old Cloudflare token. Local replacement DPAPI storage already confirmed. Resume P13 staging-first issuance; no old/new key values in project files, no agent credential decryption. Next command is reviewed request-certificate.ps1 -Environment Staging -AcceptTerms, with Email entered at the local mandatory prompt after owner reads CA terms. Phase 1 remaining: staging/production certificate, restricted HTTPS receiver/firewall review and phone TLS/auth tests, plus supervised export-metadata evidence. Address reservation remains deferred, not a current blocker.

## S01 staging request succeeded (2026-10-29)

Owner ran the absolute-path request-certificate.ps1 -Environment Staging -AcceptTerms in normal PowerShell and reported: "Staging certificate request completed. No listener or firewall rule was enabled." PASS for owner-observed staging client completion with the replacement credential. This does not establish production trust, certificate contents/expiry, phone compatibility or a deployed receiver. Contact email is deliberately omitted from this record. Next: production issuance under existing P13, then public certificate metadata/chain verification and separately approved LAN activation. No additional code/test changes in this checkpoint; documentation consistency checked, application tests not rerun.

## S01 production issuance and public metadata (2026-10-29)

- Owner ran request-certificate.ps1 -Environment Production -AcceptTerms and reported successful completion with no listener/firewall enabled. Contact email is omitted from documentation.
- Agent read only the public acme-production/certificates/sync.mgilham.online.crt using X509Certificate2. PASS: subject CN and sole displayed DNS SAN sync.mgilham.online; issuer Let's Encrypt YE2; validity 2026-10-29 11:10:41 UTC through 2027-01-27 11:10:40 UTC. Public certificate has no embedded private key, as expected; separate key was not opened. This is not a verified trust chain/key match or iPhone handshake.
- Resolve-DnsName sync.mgilham.online -Type A -DnsOnly PASS: 192.168.1.190. Get-NetConnectionProfile FAILED with Access denied in agent session; profile/interface still unknown. Owner normal-terminal read-only check needed before a concrete narrow firewall proposal. Do not change the profile automatically, enable a rule or launch a LAN listener.
- Documentation-only checkpoint; application suite not rerun. S01 remains in_progress, E01 pending export availability, no Phase 2 approval.

## S01 Windows network category checkpoint (2026-10-29)

Owner reports NetworkCategory Public from the normal-terminal check; interface name not yet supplied. The proposed Private-only firewall rule would not apply. Present two options: explicitly change only the trusted home connection to Private (recommended for the selected LAN design), acknowledging that other existing Private-profile discovery/sharing/firewall rules may then apply; or keep Public and defer phone/LAN testing while local work proceeds. No category change, discovery/sharing toggle, Public-profile exception, firewall rule or LAN listener has been executed or approved. Documentation consistency check only; no code changes/application tests needed for this observation.

## S01 P14 and receiver preparation (2026-10-29)

Owner approved the home-only Private profile choice and reports completing it. Recorded P14; no agent profile modification. Starting bounded synthetic HTTPS launcher and firewall preview/add/remove tooling. Acceptance: fixed current IPv4/port, Private profile/interface checks, no proxy-header trust, TLS >=1.2, no access logs, generated 256-bit credential stored only under private DPAPI protection, no health importer/UI, explicit activation commands and single-rule rollback. Tests must not bind the real LAN or read real private keys/credentials. Firewall/listener activation approval still pending.

## S01 receiver preparation verification and activation gate (2026-10-29)

- Implemented app.transport.serve, start-probe.ps1, probe-network.ps1 and probe-firewall.ps1. Exact rule, normal/admin separation, activation commands and rollback documented in SECURE_SETUP.md. No script invoked with -Activate or -Mode Add/Remove; no LAN listener, real private-key loading, ingest credential creation or firewall mutation occurred.
- `.venv/Scripts/python.exe -m pytest backend/tests/security -q -p no:cacheprovider`: PASS 19 tests, including explicit activation refusal and missing TLS files failing configuration before bind. Ruff PASS; Mypy PASS (18 source files); all PowerShell scripts parsed successfully.
- `powershell -File scripts/check.ps1 -Suite Foundation`: PASS 62 backend tests, 13 frontend tests, Ruff/Mypy, strict TypeScript and Vite production build. `.venv/Scripts/python.exe scripts/scan_source.py`: PASS 80 source files, no findings. No dependency changes; advisory audits not rerun at this checkpoint.
- Real Windows profile/DNS/firewall operations and real TLS chain/key/phone checks remain unexecuted. S01 remains in_progress, activation awaiting approval. No public exposure or Phase 2 authorization inferred. After these checks, added one additional parent certificate-directory privacy check; rechecked PowerShell syntax and diff only (no Python changes).

## S01 P15 activation authorized; owner execution needed (2026-10-29)

Owner explicitly approved the prepared setup and phone test; recorded P15. Agent ran `powershell -NoProfile -File scripts/probe-firewall.ps1` (default read-only Preview): FAILED at Get-NetIPAddress with Access denied; no rule mutation or listener start occurred. Do not bypass session controls or ask for the same approval again. Owner-assisted next actions: -Mode Add in administrator PowerShell, then start-probe.ps1 -Activate in a separate normal-owner PowerShell. If either command fails, stop and report the error rather than proceeding. First iPhone test on the same home Wi-Fi is Safari https://sync.mgilham.online:8443/health expecting status ok with no certificate warning; this does not establish authenticated POST/exporter compatibility. Documentation-only update; diff check run, application tests not rerun.

## S01 owner iPhone HTTPS health check (2026-10-29)

Owner reports all P15 steps worked and Safari displayed status ok on the iPhone. PASS for owner-observed phone-to-PC HTTPS health reachability and accepted production certificate through the documented hostname. Successful launcher also implies certificate/key pairing loaded before binding; no private key content read into agent context. No authenticated POST, Health Auto Export compatibility, negative TLS case or remote route-isolation pass is inferred. Receiver may still be running in owner's foreground console; no automatic stop/rollback claimed. Next prepare a sanitized owner-run authenticated synthetic verification command, then remaining device/negative gates. Real health exports still unavailable for E01.

## S01 sanitized live-verifier preparation (2026-10-29)

- Added verify-probe.ps1 plus probe-checks.ps1: normal-user private DPAPI credential use, fixed synthetic JSON, default Windows TLS trust, no redirects, nine status/body/route checks, fixed sanitized results. No real token decrypted/read or live request made by agent. Owner execution needed because agent network-profile discovery is denied.
- Ruff PASS for the new synthetic test; security suite PASS 23 tests. Four new mocked-boundary cases establish that the verifier accepts expected responses and fails unexpected authentication success, stored=true or a redirect; they are not live network evidence. All PowerShell scripts parse PASS. Source scan PASS 83 source files/no findings. Full foundation suite not repeated: no app/frontend behavior changed.
- Next owner command is the absolute-path verify-probe.ps1 in a separate normal PowerShell, leaving the foreground receiver running for the check. After results, continue remaining device POST/negative TLS/export evidence gates; do not declare Phase 1 complete from Safari health alone. Documentation/diff checks complete.

## S01 live PC verifier passed (2026-10-29)

Owner supplied all nine PASS lines and the final success message from verify-probe.ps1. PASS (owner-executed live evidence): Windows HTTPS health, authenticated synthetic POST with no storage, missing/wrong credentials rejected, browser Origin rejected, dashboard/status/docs absent and real importer disabled. No readings sent/stored by these checks. Phone evidence remains the separate Safari health test; do not describe the PC POST as a phone/exporter POST. Next build/run isolated synthetic TLS rejection tests (chain, hostname, expiry) without touching Windows trust, real certificate files, network/firewall policy or the active LAN server. Then arrange exporter/metadata evidence with the owner. No Phase 2 entry approval.

## S01 isolated TLS verification (2026-10-29)

- Added test_tls_handshake.py and make_tls_fixtures.ps1: real Python/OpenSSL TLS over MemoryBIO using the server configuration; synthetic CA trusted by one in-memory test client only. PASS valid chain/hostname/time positive control; PASS untrusted issuer, wrong hostname and expired leaf rejection. No socket, OS trust mutation, real production key/token read or real certificate replacement.
- Initial Git OpenSSL invocation failed with CreateFileMapping Access denied; fixture generation failed in all four cases, no pass claimed. Replaced the external executable with Windows .NET in-memory CertificateRequest/RSA objects. Initial RSA.Create().KeySize assignment was unsupported; corrected to explicit 2048-bit RSACryptoServiceProvider with CreateEphemeralKey. Four handshake tests then PASS. No new dependencies or control bypass.
- Full regression powershell -File scripts/check.ps1 -Suite Foundation: PASS 70 backend tests, 13 frontend tests, Ruff/Mypy (18 app source files), TypeScript and Vite build. Test fixture PowerShell parser PASS.
- Source scan initially flagged a literal PEM header in test code (no key bytes). Added a documented one-line allowlist for the delimiter expression only, preserving real secret detectors and synthetic credential-detection tests. Reran Ruff PASS and source scan PASS 85 source files/no findings. Final change after full regression was comments/line-specific delimiter allowlist only.
- S01 remains in_progress: phone/exporter POST and renewal operation not yet demonstrated. E01 still needs owner-selected export availability and supervised metadata/delivery evidence. Owner may stop the foreground receiver now with Ctrl+C; stop is not yet confirmed. The approved firewall rule persists unless explicitly removed using the documented single-rule rollback. Phase 1 remains active, no Phase 2 approval.

## E01 exporter screen clarification (2026-10-29)

Owner is in Health Auto Export's REST API setup screen asking for API URL. The configured future destination is https://sync.mgilham.online:8443/api/ingest per ARCHITECTURE.md; saving a disabled configuration is distinct from running it. Current synthetic receiver deliberately returns 503 for this path, so do not enable automation, Run or Send real readings yet. No exporter authentication/real-upload success inferred. Guide owner instead to sidebar Manual Export, JSON version 2, then a short export and local-only storage/transfer after metric settings review. Official manual-export documentation checked at https://help.healthyapps.dev/en/health-auto-export/manual-export/ confirms sidebar navigation, JSON and version selection; no export/health file accessed by agent. Phase 1 remains active.

## E01 owner-provided REST API guide review (2026-10-29)

Read the owner's exact official link https://help.healthyapps.dev/en/health-auto-export/automations/rest-api/ (page marked updated 2026-08-23). Confirmed documented POST, custom Bearer header, JSON v2/content type and JSON batching capabilities. Added narrowly scoped documentation-evidence section to DATA_PIPELINE.md; no approved design changed or capability claimed as device-tested.

Flagged two meaningful distinctions: automation-level Manual Export sends real readings, whereas sidebar Manual Export creates a file; multi-metric aggregation wording conflicts with preserving individual readings and must be resolved by actual export evidence before adapter/settings approval. Retry/checkpoint/correction ordering is not established by this guide. No automation enabled, real file opened or data sent. Next owner navigates sidebar Manual Export (outside the automation) and selects JSON v2 for the supervised file-format check. Documentation-only change; diff check performed, application tests not rerun.

## E01 unsuccessful export attempt (2026-10-29)

Owner reports generic export failure and asks whether the API URL needs a key. Actual export screen, HTTP status and cause unknown; do not infer authentication failure or successful local-file creation. Clarify whether an API URL field was visible before another attempt. Sidebar file export needs no SleepIQ server/credential; REST upload requires the separate generated ingest credential (never the Cloudflare DNS token) and the future importer is not enabled. Current /api/ingest returns 503 even with valid authentication. Do not suggest sending real readings, bypassing authentication or retrying the API automation. If this was definitely a local file export, next diagnose a shorter Yesterday range and Health permissions without weakening granular-data requirements. No health file opened by agent, no successful delivery claimed. Documentation-only checkpoint; application tests not rerun.

## E01 supervised report received and interpreted (2026-10-29)

Owner ran diagnose-export.ps1 on an existing export outside this repository and supplied only its sanitized version-1 report. No raw file, measurement, actual timestamp, identifier, source label or secret was requested/read into agent context. This is owner-run evidence, not a new export or current REST-configuration test.

- Six configured metrics present, each with one expected-unit block and no unexpected-unit blocks. Counts: sleep 202, HR 3390, HRV 28, respiratory 320, RHR 4, wrist temperature 4. Counts happen to match the historical example; do not infer an independent second export. No unknown/malformed blocks or non-dictionary samples reported. Numeric validity, stage enumeration, source identity, granularity/completeness and sleep-night coverage are not checked by this report.
- All recognized start/end pairs parsed with offsets; no missing, negative or invalid/unzoned intervals reported. HR and respiratory observations are points. Sleep, HRV, RHR and temperature are positive-duration intervals. Sleep also has startDate/endDate, but equality with start/end is not established by this diagnostic.
- HR has Avg/Min/Max and no qty. Since this file provides point-HR readings, the already approved D6/P4 simple mean of valid in-window Avg values applies; label simple_mean_fallback, count and unknown duration coverage. Do not manufacture interval weights from adjacent point timestamps. HRV qty/heartbeatSeries presence does not prove heartbeat-series validity or warrant reconstructing a full-night SDNN; retain approved mean-of-recorded-SDNN policy.
- Every sample lacks the recognized id/uuid/recordId and updatedAt/modifiedAt/lastModified fields. Zero repeated/changed identity counts therefore provide no duplicate/correction evidence. Apply approved exact-content deduplication; ambiguous revisions retained/flagged, never silently overwritten. Single-file delivery, retries, deletion semantics and correction ordering remain explicitly unknown.
- E01 marked done under its existing “or explicitly records unknowns” acceptance clause. This does not approve Phase 2, a final record-key/correction algorithm, real ingestion or current exporter settings. Updated DATA_PIPELINE.md and diagnostic limitations; documentation-only checks, application tests not rerun. S01 is still in_progress.

## S01 phone synthetic POST preparation (2026-10-29)

Owner requests proceeding with the previously approved supervised phone test. Preparing an explicit normal-user, local-only credential viewing dialog (never console/chat/clipboard/file output) so the owner can type the existing ingest credential into a runtime Shortcuts prompt. Do not embed the credential in the Shortcut/header configuration: use Ask for Input and its variable, avoiding a saved credential in a possibly synced Shortcut. Dialog starts masked, needs explicit reveal, closes automatically, checks private folders/regular file and never reads Cloudflare credentials. No real-key display/decryption by agent; owner runs it explicitly. No new firewall/listener settings, uploads or Phase 2 work. Apple Get Contents of URL documentation reviewed for POST/JSON configuration.

## S01 phone-test tools verification (2026-10-29)

Added credential-dialog.ps1 and view-ingest-credential.ps1 with -Show opt-in, private folder and regular-file guards, local masked native dialog, explicit reveal and three-minute timeout. No clipboard/file/network/console credential output; actual key remains unaccessed by agent. SECURE_SETUP.md now documents runtime-input Shortcut, fixed URL (never the input credential), auth variable, synthetic JSON, wrong/correct runs and cleanup.

Ruff PASS for new test; security suite PASS 29 tests including real synthetic TLS tests and two viewer guard tests (explicit action required; invalid format rejected before UI initialization). All scripts PowerShell parse PASS; source scan PASS 88 source files/no findings. Native visual dialog/timer operation and phone field labels have not yet been manually tested; no real phone POST claimed. Full suite not repeated because only the isolated owner helper and its guard tests changed. Owner next builds the three-action Shortcut; only after configuration should they invoke the viewer and manually enter the token during execution. Documentation/diff checks complete.

## P16 owner declines optional Shortcut (2026-10-29)

Owner explicitly declines the test Shortcut and asks to focus on useful product work, accepting the proposed authenticated phone test deferral to Health Auto Export after the importer is ready. Record P16, retain earlier preparation as historical evidence only and stop that owner workflow. No credential viewer invoked, key disclosed or phone POST pass claimed. Keep the real exporter authentication/delivery gate and renewal integration required before routine real ingestion. No permission for Phase 2 entry, real-data access, new infrastructure or scope expansion is inferred. Final Phase 1 foundation regression/exit review in progress.

## Phase 1 exit review (2026-10-29)

- F01/D01/B01/E01 foundation gates satisfied with existing evidence: isolated locked runtime; additive empty-store migrations; launcher/loopback UI; synthetic persistence/backup scheduling/rotation; owner-created empty snapshot and independent isolated restore; sanitized export-shape report with explicit delivery/correction unknowns.
- S01 foundation spike satisfied: approved bounded infrastructure owner-operated; iPhone accepted production HTTPS health; owner live PC verifier passed authenticated and unauthenticated/hostile-origin/route checks; automated auth/rotation/request guards and real synthetic TLS positive/negative cases passed. P16 removes only the redundant test Shortcut. No authenticated phone/exporter POST pass is claimed.
- Final powershell -File scripts/check.ps1 -Suite Foundation: PASS 72 backend tests, 13 frontend tests, Ruff, Mypy, TypeScript and production build. Post-review source scan PASS 88 files/no findings; git diff --check PASS. Dependency versions unchanged since the owner-run Python/npm audits; no remote CI execution claimed.
- Mark Phase 1 and S01 foundation done. Remaining integration limits are explicit: real Health Auto Export auth/delivery/retry/backfill, source granularity/corrections and operational certificate renewal integration not demonstrated; must be handled before routine real ingestion, with actual private-data/infrastructure approval where required. Router reservation remains deferred by P12. Receiver stop not confirmed; owner can Ctrl+C if still running. No health import, live migration, AI spend or public exposure authorized.
- Request explicit Phase 2 approval for I01/D02/C01: synthetic importer, deduplication/recovery, sleep-domain derivation and approved versioned scoring, plus the necessary operational integration before real use. Unresolved substantive domain rules require a grouped owner checkpoint before affected implementation. Phase 2 remains planned/unapproved; this update does not start it.

## Phase 1 source-control checkpoint preparation (2026-10-29)

Owner asks whether checks and commit were completed. Checks passed as recorded above, but Git still has only original commit 479f957; no implementation commit has been made. Preparing one local foundation checkpoint including the approved documentation relocation, phase decisions, source, synthetic fixtures, scripts, locks and CI. Exclude unreviewed screenshots and inaccessible pytest scratch directories; private data/secrets/build dependencies remain ignored. Corrected an obsolete SETUP.md reference to a future background controller to match F01's approved foreground launcher. Commit is not a push/deployment or Phase 2 authorization. Record staging/commit result after execution; do not claim success in advance.

- Post-review source scan PASS 88 source files/no findings; git diff --check PASS. No runtime code changed; earlier final 72 backend/13 frontend regression remains applicable.
- Both scoped git add commands FAILED creating .git/index.lock with Permission denied. No staging/commit succeeded. Session filesystem controls deny Git metadata writes; do not bypass them or seek the same blocked escalation. Owner normal PowerShell must stage the named source directories/files and tracked documentation deletions, then create the local commit. Do not stage screenshots, inaccessible scratch directories, ignored dependencies/outputs, credentials or health exports. No push attempted. Phase 1 implementation/verification complete; source-control checkpoint remains pending owner execution and confirmation.

## P17 phase-end commit policy and permission guidance (2026-10-29)

Owner requests standing commit permission and checked commits at every phase end. Added P17 and synchronized AGENTS.md/DEVELOPMENT_PLAN.md. Phase 1 implementation remains verified; its new explicit phase-end commit criterion is pending, not a successful commit. Existing 72 backend/13 frontend/static/build evidence remains applicable because this task changes policy documentation only. Run documentation consistency/diff and current source secret scan for these edits; no runtime tests need repeating for prose-only changes.

OpenAI Docs skill used to verify official permission guidance. Current session explicitly protects .git as read-only and disables sandbox-approval/rule prompts; no repo edit can override that policy. Do not change global config, ACLs, sandbox settings or protected files from this session. Owner must select supported narrow Git access/approval in the launching client, subject to any managed policy, or perform the commit in their normal terminal. Ask which client they use before providing client-specific steps; do not recommend full unrestricted access merely to commit. No new git-write attempt, commit, push or Phase 2 work occurred.

Verification for this documentation-only change: Python assertions PASS for P17 routing, checked-commit rule and pending phase status across the four affected documents; source scan PASS 88 files/no findings; git diff --check PASS. No runtime/dependency changes and no new application-suite execution claimed.

## Git permission handoff: VS Code terminal (2026-10-29)

Owner identifies VS Code terminal as the client. Local Get-Command confirms a Codex CLI shim; codex resume --help succeeds and confirms --sandbox workspace-write, --ask-for-approval on-request, --last and session picker support. Official OpenAI approvals documentation confirms protected .git remains read-only inside the sandbox, with eligible explicit approval requests available under on-request. Guide owner to exit and resume the correct SleepIQ session from this project directory using workspace-write/on-request (picker avoids resuming an unrelated most-recent session). This enables requests, not unrestricted Git writes; managed policy may still prevent it. Do not claim permissions changed until a resumed session verifies them. No global/project configuration, sandbox, ACL or Git metadata changed by agent. Source checkpoint remains pending; Phase 2 unapproved.

## Git permission recheck (2026-10-29)

Owner asks whether the permission change/commit is now done. Rechecked Git: HEAD is still original 479f957. Retried the scoped git add of approved phase source directories/files: FAILED creating .git/index.lock (Permission denied). No files staged, no commit or push. Current session still denies Git metadata writes and sandbox/rule approval requests. Do not claim the resumed-session settings took effect here or attempt blocked escalation. Phase 1 implementation/checks remain verified; P17 commit still pending in a suitably authorized session or owner's normal terminal.

## Phase 2 entry and domain checkpoint (2026-10-29)

Phase 1 is committed locally (fb23f79 "1st phase complete"; working tree clean at Phase 2 start). Owner instructed: "Read agents.md and the relevant docs. Complete phase 2. Some of it will require my input, stop and ask for my input when required. Stop after phase 2 is complete." Recorded as Phase 2 entry approval for I01/D02/C01 on synthetic data only. This does not authorize real-data access, real uploads, live migration, or Phase 3.

Read AGENTS.md, DATA_PIPELINE.md, SCORING.md, DECISIONS.md, TESTING.md, ARCHITECTURE.md and the existing db/transport code. Remaining domain contracts (record identity/conflicts, nap-only/tie/completion, HR weighting, daily-metric attribution, ingest wiring) are presented to the owner as one grouped checkpoint before dependent implementation. No Phase 2 code written before the answers.

## Phase 2 owner decisions P18 (2026-10-29)

Owner answered the grouped checkpoint: 1.A (keep first-received, flag revisions); 2 "go with most logical" = recommended 3 h minimum night, earlier block wins ties, "may be incomplete" flag; 3.A (labelled simple-mean HR only; time-weighting deferred until interval-style HR data exists); 4 physiology counts for a night only inside its sleep window, otherwise it is a general daily metric; 5 build the importer for real data rather than synthetic only, resolved as a wired-but-default-off `/api/ingest` plus an owner-run local import command (the agent never reads real exports; synthetic data only in tests/Git); 6 yes (baseline eligibility, circular mean, undefined-baseline rule, wall-clock DST). Recorded in DECISIONS.md as P18.

## Phase 2 implementation and verification evidence (2026-10-29)

Built (backend/app; synthetic builders in backend/tests/factories.py):
- Migration `0002_health`: import_batches, observations (UTC integer instants + offsets, unique content fingerprint, active/conflicting), nightly_metrics, general_metrics, nightly_scores. Fresh stores initialise at this head; the owner's existing Phase 1 store (0001) is migrated only by the explicit `--migrate` flag after a verified snapshot.
- `ingest/parse.py` (per-metric JSON v2 validation, plausibility limits, fixed-vocabulary rejection reasons that never echo input), `ingest/store.py` (content-addressed raw file + observations + derived rebuild in one transaction under the shared writer gate), `ingest/cli.py` + `scripts/import-export.ps1` (owner-run, counts only), `ingest/service.py` and `transport/probe.py` (`/api/ingest` returns 503 unless a handler is supplied; `transport/serve.py` supplies one only when `SLEEPIQ_INGEST_DATA` is set).
- `domain/sessions.py` (gap chaining, overlap resolution, trimming, nap threshold, source preference, wake date), `domain/scoring.py` (P2 curves, circular consistency, neutral components, S4/S16 withholding), `domain/rebuild.py` (nights, general metrics, scores; incremental = rebuild from the earlier of touched date minus two days and the latest stored night), `domain/config.py` (versions derive-1 / pilot-1, config hash).

Checks actually run:
- `powershell -File scripts/check.ps1 -Suite Foundation`: PASS, exit 0: Ruff, Mypy (29 source files), 132 backend tests, 13 frontend tests, strict TypeScript and Vite build. Phase 2 added 60 backend tests: parse adapter (10), session/DST domain (10), scoring functions (10), importer including four injected crash points (12), rebuild pipeline equivalence/leakage/missingness (11), route/CLI/year-scale (7).
- Key evidence: repeat/overlap/reorder imports stable; crash at raw publish, mid-insert, rebuild and batch-summary leaves zero rows and no raw file, and the retry equals a clean import; incremental import (with gaps and backfill) equals a clean rebuild; adding later nights never changes earlier scores; backfill updates later baselines; worked scores 92.5 and 80.25 plus hand-calculated 88.75 and 86.25 nights; UK fall-back interval 1,442 s and an 8 h elapsed night across the clock change; spring-forward; a synthetic year (365 nights, 5,000+ observations) imports in about 1.4 s (smoke guard only, not a calibrated budget).
- `.venv/Scripts/python.exe scripts/scan_source.py`: PASS, 107 source files, no findings. `ruff format` initially rewrote four unrelated Phase 1 test files (moving a secret-scan allowlist line); they were restored with `git checkout` and are unchanged.
- Dependencies unchanged; pip-audit/npm audit not rerun. PowerShell parser check on scripts/import-export.ps1: PASS.

Bug found by tests and fixed: timestamp parse errors echoed the offending input into rejection reasons; reasons now come from a fixed vocabulary.

Not done / limits (explicit): no real export has been read or imported; the owner-run import (`scripts/import-export.ps1 -ExportPath <file> -Migrate`) migrates the live store 0001 -> 0002 and is pending the owner. Real Health Auto Export authentication/delivery/retry, certificate renewal integration and enabling `/api/ingest` on the LAN remain required before routine syncing. Deep/REM descriptive target categories and all UI are Phase 3. Weighted HR deferred (P18). Floats with 1e-9 test tolerance rather than exact decimals. Defaults chosen without separate approval: plausibility limits, provisional below 14 baseline nights, circular resultant threshold 0.1, qty cross-check 120 s, completion lookahead 30 min (3 h nap threshold was approved via "most logical").

## Phase 2 checkpoint commit and handoff (2026-10-29)

Local commit 45eddae "Phase 2: ingest, sleep-session domain and versioned scoring" created after all checks above passed (staged list reviewed: source, tests, docs, scripts/import-export.ps1 only; no data, secrets, builds or screenshots). Not pushed. I01, D02 and C01 are done on synthetic data. Phase 3 (UI/analytics) is NOT approved; the owner-run real-export import and enabling `/api/ingest` remain separate owner steps. Awaiting explicit Phase 3 approval.

## Phase 2 post-commit real-import verification (2026-10-29)

Owner ran `scripts/import-export.ps1 -Migrate` on one real 30-day export (path outside the repo; contents never seen by the agent) and the counts-only report. Reported counts: status imported; 13,091 new observations; 2 exact duplicates; 7 flagged conflicts (all `heart_rate`, outside any sleep window, so no night flagged revised); 7 rejected `sleep_analysis` rows with the unspecified "Asleep" label (unused by design); no unmapped metrics. Derived: 31 nights (2026-09-29 to 2026-10-29), 24 scored, 7 insufficient (fewer than 7 prior nights, expected); no night missing HR or HRV. Live store migrated 0001 -> 0002 after a verified snapshot.

Finding: all nights were flagged `non_preferred_source` because the single sleep source label contains "watch" but not "apple watch". Default `preferred_source` changed to "watch" (flag only; no metric or score changed). Added `scripts/import-report.ps1` (counts-only summary, anonymous source breakdown) and `scripts/rebuild-derived.ps1` (verified snapshot, then clean rebuild of derived data from stored observations). Foundation suite rerun: PASS, 134 backend + 13 frontend tests, Ruff, Mypy, build; secret scan PASS (113 files). Owner still needs to run the rebuild script to refresh the stored flags. Phase 3 and live auto-sync remain unapproved.

## Historical backfill tooling (2026-10-29)

Owner has one 74 MB export of all history, above the importer's 64 MiB per-file limit, and asked whether an LLM could split it. Declined: sending health data to a model is outside policy and unnecessary. Added local-only `scripts/split-export.ps1` (`app/ingest/split.py`): monthly files by source-local start date, rows copied unchanged, unmapped blocks and unparseable rows kept in `export-other.json`, refuses non-empty destinations, counts-only output. Test shows importing the pieces (in reverse order) equals importing the whole. Foundation suite PASS: 136 backend + 13 frontend tests, Ruff, Mypy, build; secret scan PASS (116 files). Auto-sync (`-EnableIngest`) still awaits owner approval; Phase 3 unapproved.

## Historical backfill completed by owner (2026-10-29)

Owner split the 74 MB all-history export locally (14 monthly files, 179,637 rows) and imported each with `scripts/import-export.ps1`; agent saw counts only. Report: 15 batches; 179,582 stored observations (heart_rate 144,734 active + 30 conflicting; respiratory 20,080; sleep 12,050; HRV 1,998; wrist temperature 388; RHR 302). Sum of per-file `new_observations` plus the earlier 13,091 equals 179,582 exactly; the 13,093 rows overlapping the earlier 30-day import were skipped as exact duplicates. 393 nights, 2025-09-29 to 2026-10-29; 386 scored, 7 insufficient (earliest); no night missing HR/HRV; 6 nights flagged `revised` (from the 30 same-slot heart-rate disagreements, excluded from baselines but still scored). 59 unspecified "Asleep" rows rejected by design. `non_preferred_source` flag gone (preference loosened to "watch"). Owner should delete the Downloads originals and split folder; the agent deleted nothing. Open question for later: whether same-timestamp heart-rate disagreements inside one upload deserve the "revised" label (currently yes per P18 Q1). Auto-sync (`-EnableIngest`) still awaits explicit owner approval; Phase 3 unapproved.

## Auto-sync enablement P19 (2026-10-29)

Owner approved `-EnableIngest` (P19). Added the switch to `scripts/start-probe.ps1` (sets `SLEEPIQ_INGEST_DATA` only when passed, restored in `finally`; private-folder checks first) and 3 tests: a multi-hundred-KB upload is 413 when disabled and imports through the authenticated boundary when enabled, server configuration accepts a handler with TLS-only/no proxy trust/no access log, and the launcher sets the variable only under the switch. PowerShell parser check PASS. Documented phone setup in SECURE_SETUP.md. Pending owner-run: start the receiver with `-Activate -EnableIngest`, configure Health Auto Export, supervised first run. First real exporter authentication, delivery, retry and batching behaviour are NOT yet demonstrated; nothing is claimed until the owner reports a run. Phase 3 unapproved.

## Auto-sync first real exporter run (2026-10-29)

Owner configured the Health Auto Export REST API automation (URL https://sync.mgilham.online:8443/api/ingest, Authorization header, JSON v2) against the receiver started with `start-probe.ps1 -Activate -EnableIngest`. Owner reports the export "was successful" and the counts-only report's `batches` rose from 15 to 16. Owner-observed evidence closing the P16 gate for exporter TLS + authentication + delivery on one manual run. Not yet verified: scheduled/unattended runs, retry after the PC or receiver was off, whether "previous 7 days" re-sends overlap cleanly over several days (importer tests say yes), and the new batch's detailed counts (not reported). Known limits unchanged: receiver must be running with the PC on; PC address 192.168.1.190 not reserved (P12); certificate expires 2027-01-27 with renewal not yet integrated; the receiver does not run the backup scheduler (dashboard launcher does). Phase 3 still unapproved.
