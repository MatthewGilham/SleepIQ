# SleepIQ — Testing and Quality Gates

**Status:** Complete v1.0. **Audience:** all coding agents, reviewer and CI author. **Principle:** tests protect data integrity, reproducibility, privacy and user-visible behavior; they are written alongside the feature, not at project end.

## 1. Test strategy and commands
- **Backend:** `pytest` for pure parser, session grouping, statistics, scoring, DB integration, HTTP auth and backup flows. Include timezone-aware property/table-driven tests.
- **Frontend:** Vitest + React Testing Library for formatters, chart selection, presets, missing/loading/error states and accessibility-oriented interactions.
- **Browser:** Playwright against a locally launched test backend and frontend for complete workflows; run screenshot comparisons when design changes matter.
- **Static/quality:** Python formatter/linter/type checks (choose one coherent toolchain), TypeScript strict mode, ESLint, dependency/security and secret scanning; GitHub Actions on pushes/PRs using **only synthetic health data**.
- Every agent task ships executable commands, updated tests, actual outcomes and limitations. Never say “all tests pass” without running them.

## 2. Required fixtures
Create anonymized **synthetic** JSON-v2-shaped data with realistic stage intervals and heart-rate variants (`Avg`, `Min`, `Max` vs `qty`), multiple weeks of records, missing days, no heart-rate sample during sleep, duplicate overlapping exports, corrected observations, competing sources, and wrist-temperature intervals. Include cases matching the *structure*—not identifying source metadata—of the observed autumn DST switch. Keep original user export out of commits, snapshots and CI artifacts.

## 3. Domain acceptance matrix
| Area | Mandatory checks |
|---|---|
| Validation/import | Valid payload accepted; invalid/malformed/oversized rejected safely; no partial commit; unknown noncritical fields don't corrupt data |
| Idempotency | Same file twice and overlapping files don't duplicate observations; late corrections replace/update according to documented identity policy |
| Session construction | Sleep spans midnight, DST fall-back and spring-forward, missing gaps, multiple sessions, nap exclusion, Apple Watch priority; deterministic wake-date assignment |
| Sleep metrics | Core/Deep/REM/Awake durations, awake handling, stage-based efficiency, onset and wake timestamps, timestamp/quantity units and source resolution |
| Physiology | Correct night-window filtering, sampling durations and weighted-HR method, explicit unweighted fallback, overnight mean SDNN HRV, missing readings stay missing |
| Consistency | 30 calendar days lookback, >=7 prior eligible nights, circular time, 20-min penalty, no future leakage, DST offset interpretation, missing-day gaps |
| Score | Owner-approved weights, anchors, neutral stage/physiology pilot, required HR and HRV present, 0–100 bound, versioned pure functions, deterministic backfill |
| Analytics | Range selection, nightly paired samples, rolling means with missing-date gaps, correlation coefficient and sample size, actual/normalized overlay modes |
| Persistence | SQLite transaction/uniqueness, schema migrations, saved chart preset CRUD/default, backups rotation/catchup and **isolated restore test** |
| Security | Auth missing/incorrect, token rotation, request limits, TLS/iPhone trust spike, no private data in logs, frontend bound locally, secret scanner |
| UI | Latest-night state, missing/insufficient/provisional, stage chart, preset round-trip, custom range, export actions, keyboard and narrower screen |

## 4. Key edge-case definitions
- UK 2026 autumn clock change: a timestamp with `+0100` followed by a lower wall-clock timestamp at `+0000` can represent **positive elapsed time**. Always compare timezone-aware instants for duration; separate wall-clock circular math for consistency.
- Wake date refers to **local** date at sleep end, not UTC date. Handle crossing midnight/offset changes and document any travel-time-zone rule.
- Missing measurements are not zeros. Missing **required** HR/HRV blocks overall score under S16 even with neutral contribution. A lack of prior seven qualifying nights blocks consistency and overall score. Unscored nights still appear in graphs.
- Scoring historical night N must not change merely because N+1 data arrives, unless input data for N or approved formula version changes; baselines use preceding nights only.
- Importing old observations must re-evaluate affected nights and subsequent rolling baselines where appropriate, without silently rewriting user-approved formulas.

## 5. CI and completion gates
Define a small, stable command (`make check` alternative or Windows-friendly `scripts/check.ps1`) that runs formatting/static checks, backend tests, frontend tests and build, then Playwright smoke tests in an integration workflow. CI must fail on relevant test/scan failures; never skip security checks without explicit owner decision. Keep tests fast enough for each PR; label slower full suites. Record coverage trend but prioritize meaningful edge cases, not a vanity percentage.

**Definition of done for a task:** acceptance criteria met; targeted and regression tests passed; no new security issue; relevant docs/decisions updated; user gets 3–6 lines explaining what changed, what it does, how to verify, and what decision or risk remains. If a command couldn't run, say exactly why and stop short of claiming completion.

## 6. Human acceptance and teaching
At high-impact milestones, agent shows short before/after screenshots or a tiny sample JSON-to-metrics example and describes the design trade-off in plain English. Ask owner only for consequential choices or unresolved contradictions, grouped into one decision checkpoint whenever possible. User tests manually when necessary; automation handles routine regressions.

## Approved checkpoint acceptance additions
- P2: neutral Deep/REM/physiology = 75, ceiling 92.5; duration below six hours max(0,40+35*(hours-6)); efficiency interpolation through (0%,0),(80%,60),(90%,85),(95%,100). Full calculation precision, one-decimal overall display. Reference nights score 92.5 and 80.25 before display rounding; missing HRV remains Insufficient data.
- P3/P4: 30-minute gap boundary and greatest-recorded-sleep candidate; gaps not sleep/awake; source-local wake date and latest unscored/partial visibility. Test nap-only/tie/mixed-offset rules after contract approval. Exact repeats deduplicate, ambiguous corrections never silently overwrite. SDNN mean requires >=1 valid sample and visible n.
- P1: public-certificate HTTPS via DNS validation, valid iPhone test and invalid chain/expiry/hostname rejection; no private-root setup or plaintext fallback. LAN cannot reach browser/admin routes. Test hostile origin/host as well as credential/limit failures.
- P5: isolated restore before routine real use; 14 successful daily snapshots; one catch-up snapshot after downtime; disk-full/corrupt failures preserve valid copies; verify raw recovery rather than treating a manifest as a backup.
- P6: paired Pearson unavailable below three pairs or for constant inputs; z-scores and calendar rolling windows use approved missing/coverage contracts; no invented values or causal claims.
- Store actual commands/results/limitations and phase approval history in docs/PLAN.md only. Planned commands are not verification evidence. Documentation tasks use link/consistency checks and independent synthetic arithmetic where relevant; do not claim application tests before code exists.

## Phase 2 test commands

`python -m pytest backend/tests/ingest backend/tests/domain backend/tests/scoring -q` (also part of `scripts/check.ps1 -Suite Foundation`). Synthetic builders live in `backend/tests/factories.py`; never place real exports in the repository. The 365-night timing test is a smoke guard, not a performance budget.

## Current foundation command

Run `powershell -File scripts/check.ps1 -Suite Foundation` on Windows. It checks Ruff, Mypy, backend tests, frontend health-response tests, strict TypeScript and the production build. Pytest caching is disabled because this session cannot access its cache directories; static-server tests use a committed synthetic fixture and require no writable temporary directory. Vitest uses thread workers for compatibility with process restrictions. These are execution adaptations, not skipped assertions. Full browser/security/release gates remain required later; `-Suite Full` deliberately fails until implemented. Results and unfinished foundation scope live only in PLAN.md.

## Source security and CI execution

`scripts/security.ps1` scans only Git source candidates (including untracked, nonignored source), refuses private-file candidates, runs detect-secrets detectors serially without multiprocessing and fails on findings; only filenames are printed, secret values are withheld. Do not paste private credentials into chat. Dependency audits query package vulnerability services using package metadata; they do not include health data. Unreachable services count as an unavailable gate, never a pass. Required development tools: detect-secrets and pip-audit. Windows CI runs foundation and security commands from locked installs with read-only repository permissions; execution evidence is recorded in PLAN.md. No remote execution is claimed merely because a workflow exists.

The serial scanner validates private-file, symlink and workspace-escape guards before any file content reads. Synthetic credential detection and path-guard tests run in the backend suite. pip-audit uses the project interpreter and workspace-local cache. An advisory-network failure remains a failing/unavailable gate; use an owner-run normal terminal when the session cannot connect, never disable audits to complete a ticket.

## Synthetic TLS handshakes

P16 removes the optional owner-operated Shortcuts test. Phone authentication and exporter TLS/delivery must instead be demonstrated through Health Auto Export after the importer exists and before routine real ingestion. Do not claim that the existing iPhone health GET or PC authenticated POST establishes that integrated result. This deferral allows synthetic importer development after explicit Phase 2 approval; it does not authorize real-data access or waive the eventual device gate.

The foundation suite includes real OpenSSL-backed Python TLS handshakes over MemoryBIO, using the transport server configuration and ephemeral synthetic Windows-generated certificates. Windows PowerShell/.NET CertificateRequest and explicitly ephemeral RSA providers generate a test root, valid leaf and expired leaf into ignored scratch folders; no system certificate store, DNS, listener, firewall or real credential is accessed. A root trusted only by the test client proves the positive control. Separate clients reject unknown issuers, hostname mismatches and expired certificates without disabling verification. These checks do not replace iPhone/exporter compatibility evidence. The single-line secret-scan exception in test_tls_handshake.py covers literal PEM delimiters only, with no embedded key material; all keys are generated during tests and the actual-secret detection tests remain enabled.

## U02 browser/chart checks
Run `npm --prefix frontend run test:e2e` after building. Playwright uses installed Microsoft Edge, launches a fresh synthetic preview server on 127.0.0.1:8766, and refuses an existing server on that port. It never opens the live store. Screenshots and browser outputs stay under ignored `.cache/`; `scripts/preview-charts.py` without `--fresh` is the persistent synthetic manual preview. Unit tests intentionally include only `src/**/*.test.{ts,tsx}`; Playwright specs run separately.

`python -m pytest backend/tests/analytics -q -p no:cacheprovider` covers calendar ranges/gaps/DST offsets, unit conversions, normalization references, constants/missingness, input validation, preset persistence across app re-creation, optimistic conflicts/default exclusivity and local origin/request boundaries. A01 adds `backend/tests/analytics/test_stats.py`: hand-calculated rolling references (missing days, 4/7 and 15/30 minimums, zero kept), Pearson exact/±1 cases and agreement with `statistics.correlation`, <3 pairs/constant inputs, rolling windows before range start, normalized rolling, clock exclusion, correlation pairing/exclusion counts and endpoint boundaries. `npm --prefix frontend run test:e2e -- analytics` runs `e2e/analytics.spec.ts`: rolling display/coverage/preset persistence and correlation n/exclusions/scatter/unavailable cases, with expected values derived independently from `scripts/preview-charts.py`. The full Playwright run covers both U02 and A01 specs. `analytics.spec.ts` also guards against layout shift: it records scroll position and page height every frame while options reload, and fails if either drops.

## Phase 3 UI/analytics/export commands
`python -m pytest backend/tests/analytics backend/tests/export -q` (dashboard read model, charts, statistics, CSV export); `npm --prefix frontend test` (unit/server-render); `npm --prefix frontend run test:e2e` (Edge against an isolated synthetic store; port 8766 must be free; filter with `-- dashboard`, `-- night-nav`, `-- analytics-redesign`, `-- export`, `-- analytics`, `-- charts presets`). All run synthetic data only. `scripts/check.ps1 -Suite Foundation` covers lint, types, backend, unit tests and the build; browser tests are run separately.

## Retired AI tests
Removed in P28. `backend/tests/persistence/test_retired_settings.py` (start-up cleanup of `ai.usage.v1`, no `/api/v1/analysis` route) and `frontend/e2e/no-ai.spec.ts` (no AI panel, no analysis request) guard the removal.

## Desktop launcher tests (L01)
The cold-start stand-in keeps a single pending `HttpListener.GetContextAsync()` across polling waits, sets the response content length, and closes its listener in `finally`. It verifies no browser hook before readiness and stays alive until that hook appears (20-second bound), avoiding abandoned accepts and a fixed server-lifetime assumption on CI runners.

`backend/tests/test_desktop_launcher.py` runs the PowerShell launcher against throwaway loopback servers on ephemeral ports (about 30 s): the running check accepts only a `{"status":"ok"}` health answer; the wait succeeds when the server appears late and gives up on time otherwise; with SleepIQ already running the browser opens and no second copy starts; on a cold start the browser opens only after the stand-in app answers; a failing start reports the error and opens nothing; the shortcut targets `powershell.exe` with `-NoProfile -File .../launch.ps1`, the project as working directory, no execution-policy flags, refuses silent overwrite and removes cleanly (created in a temp folder, never the real Desktop); the scripts parse. The browser step is replaced by a log line through the `SLEEPIQ_TEST_BROWSER_LOG` test hook. **Not agent-tested:** the real Chrome launch and the real Desktop shortcut (owner check in OPERATIONS.md).

## Certificate renewal tests (P25)
`backend/tests/security/test_certificate_status.py` covers expiry state thresholds (>30 ok, 30 due, 14 urgent, expired), unreadable or timezone-less status files reported as unknown (never healthy), result text never echoed beyond a fixed vocabulary, the `/api/v1/status` certificate block appearing only when configured, the PowerShell renewal-due decision at 30/31 days and after expiry, a status file written from a synthetic self-signed certificate (keeping the earlier result on a refresh), and a parse check of the renewal, task and launcher scripts. `import-report` certificate output is tested in `test_store_report.py`; the header label in `frontend/src/certificate.test.ts`. **Not tested by the agent:** an actual lego/Cloudflare/Let's Encrypt renewal, the receiver restart and rollback, and the scheduled task; those need the owner's staging dry run (OPERATIONS.md).

## Phase 5 release gate and performance (R01)
`powershell -File scripts/check.ps1 -Suite Full` is the release gate: everything in Foundation, then `npm --prefix frontend run test:e2e`, `scripts/perf-check.py --enforce`, and `scripts/security.ps1` (secret scan, `pip-audit`, `npm audit`). It fails on the first failing or unavailable stage. Operator procedures and the owner's real-device acceptance checklist are in [OPERATIONS.md](OPERATIONS.md); those owner-observed items are not part of any script.

`scripts/perf-check.py` builds a throwaway store (never real data) of 1,826 nights (five years) and about 944,000 physiology and stage observations by direct bulk insert, then times a clean rebuild, an incremental one-night import and the browser API (dashboard, five-year chart, 30-day chart, three repeats each). Budgets, set with roughly ten times headroom over the first calibrated run on the owner's PC (AMD64, Windows 11, Python 3.13.16): dashboard 2 s, chart series 1 s, analytics summary 1 s (U05; all-history and 30-day, measured about 0.03 s), correlation 1 s (U17; single pair about 0.013 s and every-pair grid about 0.043 s over five years), incremental import 5 s, clean rebuild 60 s. The earlier proposal (nightly query under 1 s, dashboard under 2 s) is met. The first calibration exposed a quadratic clean rebuild (280 s for five years; 11 s for one year, 44 s for two) caused by a non-indexable midpoint filter in `domain/rebuild.py`; the fix is guarded by `backend/tests/domain/test_rebuild_windows.py`. Timings depend on the PC, so a failure on a much slower machine means "investigate", not "the data is wrong".

## Layout and average-line browser tests (U07, U08)
`frontend/e2e/refinements.spec.ts` covers round 3 (U09 duration spacing and title alignment, U10 score change, U11 no table, U12 nine tiles with wrist temperature kept elsewhere, U13 years on chart dates, U14 trend hours axis, U15 trend ranges, gaps, hover readout and range kept across nights); filter with `-- refinements`. `frontend/e2e/correlations.spec.ts` covers the U17 Correlations page: A01 counts and unavailable cases carried over, swap keeps r and points glide (same element mid-transition), keyboard and steady hover, Python best-fit line toggle, strip hover and drag-to-narrow checked against the API, every-pair grid against the matrix endpoint, and proportional fit at 1366x768, 1440x900, 1920x1080 and 390 px; filter with `-- correlations`. Backend: `test_stats.py` checks the fit against `statistics.linear_regression` and every grid cell against the single-pair calculation. `backend/tests/analytics/test_dashboard.py::test_trend_reaches_back_to_the_first_stored_night` covers the full-history trend. `frontend/e2e/layout.spec.ts` checks that text stays inside every card on the Dashboard and Analytics at nine widths from 390 to 1920 px, plus mocked worst-case KPI values. `frontend/e2e/averages.spec.ts` checks average-line position against means derived from the synthetic fixture formula, zoom independence, the Show averages toggle, Normalized mode, clock metrics, tooltip text and missing readings. Average elements carry `data-average`, not `data-metric`, so series selectors in older specs stay unambiguous.

P32 average lines follow the zoom: `frontend/e2e/averages.spec.ts` (filter with `-- averages`) derives the expected means independently from the synthetic fixture formula for the unzoomed range, a keyboard-zoomed stretch, a panned window, the end handle and after Reset zoom, checks the tooltip repeats the label, and that Normalized mode keeps one line at 0; `charts.test.ts` covers `visibleMean` and `averageText`. A window with no readings for one metric cannot be produced in the browser (the fixture's unrecorded nights are isolated and the smallest window is two nights), so that case is unit-only.
