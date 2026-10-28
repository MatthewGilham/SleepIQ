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
| AI | No call before explicit Analyze, local statistics not fabricated, minimal sent context, clear uncertainty, API failure handled, cost limits |
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
