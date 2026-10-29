# SleepIQ — Incremental Development Plan

**Status:** v1.0 implementation brief, not a blanket authorization to build. **Planning owner:** user. **Lead planner:** strong reasoning model (preferred Astra if available). **Execution:** coding agents matched to task complexity. **Constraint:** user wants to learn and approve consequential decisions, but **not** endure repeated minor questionnaires.

## 1. Operating model
1. Read `AGENTS.md` and `PRODUCT.md`, then only docs necessary for current task. Treat approved choices as fixed; inspect actual code before promising changes.
2. Lead planner audits dependencies, missing/contradictory requirements, security exposure and opportunities to simplify. **Ask the owner one grouped set of high-impact questions** with options/pros/cons/recommendation before irreversible choices. It may ask about *any* unclear or improvable aspect; don't reopen settled decisions without new evidence.
3. Break work into narrow tickets: ID, intent, owner decision if needed, relevant docs/sections, touched paths, dependencies, acceptance tests, implementation risk, suggested agent/model/effort, deliverables and rollback.
4. Owner approves the plan or current phase. Agent implements one small ticket, runs checks, explains the change to the owner in beginner-friendly language and offers a brief verification step.
5. On significant deviations, stop, explain implications and ask permission. Update `DECISIONS.md`, relevant spec, tests and plan. Never hide assumptions or silently alter product scope.

## 2. Canonical implementation plan

[PLAN.md](PLAN.md) is the sole phase/task progress, dependency, approval and verification record. Do not duplicate its roadmap or statuses here. Historic feasibility is reported evidence, not completed secure implementation.

Owner P1-P7 choices are recorded in DECISIONS.md; P8 requires explicit owner approval before every phase transition, including entry into Phase 1. At each boundary present exit evidence, unresolved risks and the next scope, then wait. Passing tests or overall plan approval does not authorize advancement. Update the plan when work starts, checks run, scope changes or tasks complete. Synchronize affected specifications.

Backup/isolated restore is foundation work before routine real-data ingestion. Manual startup remains approved; no Windows autostart.

P17 requires a local Git checkpoint at each phase end after all required checks pass, the staged changes are reviewed, and specifications/PLAN evidence are synchronized. Scoped staging and local commits are pre-authorized; pushing and history rewriting are not. Failed/unavailable required checks or blocked Git writes leave the phase-end checkpoint pending. Follow AGENTS.md for the commit gate, record actual results in PLAN.md, and obtain next-phase approval separately.

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

## 5. High-impact checkpoints

Do not reopen approved P1-P7 choices without new evidence. Remaining phase-specific questions and authorization boundaries are maintained in docs/PLAN.md, including concrete DNS/certificate/firewall setup, evidence-dependent data rules, coherent visual approval, AI disclosure/budget and final operational readiness.

Agents explain consequential unresolved choices with alternatives and trade-offs. Work within an approved phase can proceed on routine details; advancement between phases always requires explicit owner approval. Design approval is not blanket infrastructure or spending permission.

## 6. Progress report format
After a ticket: `Built / Why it works / Tests actually run / One concept explained / Any owner decision needed`. Keep it short. Maintain statuses and verification evidence only in docs/PLAN.md so a session can resume without rereading all docs. No promise of background work outside a running task.

## 7. Exit deliverables
Working local source repo, launcher, install README, migration/backup/restore scripts, synthetic test fixtures, documented real-iPhone sync configuration, reproducible tests/CI, screenshots, and a `DECISIONS.md` showing owner-approved choices. No real health export, credentials or full AI prompt logs committed.
