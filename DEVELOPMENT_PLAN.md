# SleepIQ — Incremental Development Plan

**Status:** v1.0 implementation brief, not a blanket authorization to build. **Planning owner:** user. **Lead planner:** strong reasoning model (preferred Astra if available). **Execution:** coding agents matched to task complexity. **Constraint:** user wants to learn and approve consequential decisions, but **not** endure repeated minor questionnaires.

## 1. Operating model
1. Read `AGENTS.md` and `PRODUCT.md`, then only docs necessary for current task. Treat approved choices as fixed; inspect actual code before promising changes.
2. Lead planner audits dependencies, missing/contradictory requirements, security exposure and opportunities to simplify. **Ask the owner one grouped set of high-impact questions** with options/pros/cons/recommendation before irreversible choices. It may ask about *any* unclear or improvable aspect; don't reopen settled decisions without new evidence.
3. Break work into narrow tickets: ID, intent, owner decision if needed, relevant docs/sections, touched paths, dependencies, acceptance tests, implementation risk, suggested agent/model/effort, deliverables and rollback.
4. Owner approves the plan or current phase. Agent implements one small ticket, runs checks, explains the change to the owner in beginner-friendly language and offers a brief verification step.
5. On significant deviations, stop, explain implications and ask permission. Update `DECISIONS.md`, relevant spec, tests and plan. Never hide assumptions or silently alter product scope.

## 2. Phase plan and exit criteria
| Phase | Scope and deliverable | Gate |
|---|---|---|
| **0 — Feasibility (DONE)** | Apple Watch → Health Auto Export JSON → iPhone REST POST → local Windows FastAPI; real records examined | Manual ingestion confirmed; unattended background reliability not formally verified, but **not a blocker** |
| **1 — Foundation** | Repository structure, local developer startup script/shortcut, FastAPI/React skeleton, SQLite schema/migrations, auth/TLS spike, importer with retention/logging | Secure iPhone upload verified; DB idempotency, recoverable invalid batches; owner approves certificate/firewall implications |
| **2 — Domain and scoring** | Night-session grouping, weighted sleeping HR and fallback, overnight SDNN, 30-day circular consistency, score v1 and historical recomputation, source-based tests | Correct synthetic DST/midnight, missing data and duplicates; owner approves bundled provisional formula details with worked-night examples |
| **3 — Product UI/analytics** | Premium dark dashboard, individual charts, overlays/normalization, date ranges/averages, chart presets in SQLite, correlations, CSV/Excel export | Owner reviews one coherent design; Playwright dashboard/preset/analytics tests pass |
| **4 — AI investigator** | In-Analytics question flow, local statistics, scoped provider API call only on request, transparent calculations and limits | Owner approves provider/budget/data scope; tests prove no automatic calls, computed evidence and safe failure |
| **5 — Hardening and delivery** | Backup scheduling on manual launches, restore drill, performance, accessibility, security scans, Windows setup guide, documentation cleanup and regression suite | Complete test gate + real secure ingest test, no short-token receiver exposed; owner acceptance |

Security and test requirements apply **in every phase**, not solely Phase 5. The app opens manually from a shortcut, not automatically at Windows startup. Daily backup should catch up at next launch, acknowledging that backups do not happen while app is stopped.

## 3. Model and effort assignment policy
**Do not hard-code model availability or prices.** Planner checks currently accessible coding models and usage limits at planning time. Prefer:
- **Fast/economical model (e.g., Luna)** for bounded file edits, component scaffolding, straightforward tests and documentation, after requirements are settled.
- **Mid-tier reasoning model (e.g., Sol)** for multi-module backend/frontend features, integration debugging and medium-risk refactors.
- **Highest-capability reasoning model (e.g., Astra)** for architecture reviews, scoring/data semantics, security-critical workflows, deep debugging, phase breakdown and final risk reviews.

Assign reasoning effort by *risk and uncertainty*, not only LOC. Minimize premium-model tokens by providing task-specific file paths/acceptance criteria and small relevant excerpts; use expensive reviews at architectural boundaries, not every commit. Validate the actual model names/levels currently available to the owner before assigning.

## 4. Ticket template
```text
ID / title:
User-visible objective:
Approved constraints / unresolved choices:
Relevant context: AGENTS.md + [named document headings only]
Owned files / excluded files:
Dependencies:
Complexity / risk / uncertainty: low | medium | high, with one-line reason
Suggested model / effort, alternative cheaper model:
Acceptance checks: exact unit/integration/UI/security tests
Verification demo to owner:
Rollback / migration safety:
```

## 5. High-impact checkpoints (group questions, no question treadmill)
- Phase 1: certificate trust, permanent auth, personal-health-data folders and database migration approach.
- Phase 2: Deep/REM target activation conflict (fixed personal targets vs neutral pilot S18), neutral score values, duration/efficiency tail handling, example-night outcomes, travel timezone edge cases.
- Phase 3: one screenshot/wireframe approval and chart normalization clarity, not 20 individual spacing/color choices.
- Phase 4: provider/model, estimated cost, data sent, AI retention policy.
- Phase 5: production readiness and restoration test.

Agents **may and should ask** on any ambiguity, contradiction, suspected improvement, unsupported assumption or risk. Present a recommended choice and 1–2 credible alternatives, with concise pros/cons; receive the owner's choice before implementing consequential differences. Routine internal implementation details can proceed without asking.

## 6. Progress report format
After a ticket: `Built / Why it works / Tests actually run / One concept explained / Any owner decision needed`. Keep it short. Maintain a durable tasks/checkpoint log so an agent session can resume without rereading all docs. No promise of background work outside a running task.

## 7. Exit deliverables
Working local source repo, launcher, install README, migration/backup/restore scripts, synthetic test fixtures, documented real-iPhone sync configuration, reproducible tests/CI, screenshots, and a `DECISIONS.md` showing owner-approved choices. No real health export, credentials or full AI prompt logs committed.
