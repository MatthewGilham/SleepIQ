# SleepIQ — Shared Coding-Agent Instructions

**Applies to Codex, Claude Code and other coding agents.** Read this file first. It is the **routing index**, not a dump of the whole project. Do **not** create a redundant `CLAUDE.md` by default.

## Mission
Build a secure, local-first Windows sleep analytics web app: Apple Watch / Apple Health → Health Auto Export → authenticated encrypted LAN ingestion → FastAPI → SQLite → React/TypeScript dashboard, charts, and versioned scoring. The **owner learns and makes meaningful decisions**; the agent designs, implements, tests and explains.

## Hard constraints
- No scope creep: **no nocturia, manual daily log, notes, training, official Apple Sleep Score, general chatbot**, or excluded extras. Missing readings remain missing. Support configured Health Auto Export metrics, not the entire Health catalog.
- **Never ship proof-of-concept HTTP+8-character-token receiver.** Permanent syncing requires encrypted authenticated trusted-LAN solution and owner approval. No public exposure, silent cloud sync, health-data telemetry or secret leakage.
- Owner-approved choices in `docs/DECISIONS.md` are authoritative. Preserve individual readings, idempotent imports, time-zone/DST correctness, score versioning, 14 successful daily backups, manually launched shortcut.
- Changes involving data deletion, real records, API spend, infrastructure/certificate/firewall permissions, security policy, irreversible migration, architecture or significant UX require owner approval.
- **Tests are part of every task.** Never fake test results, bypass security gates, fabricate data/statistics, or commit user health exports or secrets.

## Ask and teach — without wasting the owner's time
**Proactively flag contradictions, uncertainty, risk and meaningful improvements.** When an important decision is needed: explain what it means in accessible language, 2–3 options with pros/cons, your recommendation, then **wait for the owner's choice**. Group closely related choices into one short checkpoint. Don't repeatedly ask about minor constants or reopen resolved matters without new evidence. A practical implementation must explain what was built, why, tests actually run and a concept the owner learned. The user prefers numbered answers, not forms.

## Progressive context routing
Read **only** relevant docs and target files after this index:
| Work | Minimum additional context |
|---|---|
| Scope/feature interpretation | `docs/PRODUCT.md` relevant section + `docs/DECISIONS.md` |
| Repo structure, runtime, API contracts | `docs/ARCHITECTURE.md` section(s) |
| JSON ingest, sleep session, time zones, metrics | `docs/DATA_PIPELINE.md` + chosen architecture interfaces |
| Score, consistency, history | `docs/SCORING.md` + nightly schema in `docs/DATA_PIPELINE.md` |
| UI, charts, presets, accessibility | `docs/DESIGN.md` + API shapes |
| Auth, TLS, privacy, backups | `docs/SECURITY.md` + relevant architecture section |
| Test plan or review | `docs/TESTING.md` + specific requirement |
| Phase/ticket planning and model allocation | `docs/PLAN.md` + `docs/DEVELOPMENT_PLAN.md` + relevant `docs/DECISIONS.md` entries |

Do not dump every doc into a task prompt. Cite file paths/section anchors; inspect narrow code ranges and expand only as needed. Maintain task notes/decisions for handoffs. Minimize unneeded tokens **without compromising correctness**.

## Before editing
1. Identify the task's acceptance criteria, constraints and files. Check `docs/DECISIONS.md` for approved vs provisional choices.
2. If consequential ambiguity remains, propose grouped alternatives and request approval. Deep/REM targets remain descriptive; neutral constants and score curves are approved in `docs/DECISIONS.md` P2. Do not reopen them without new evidence.
3. Plan smallest safe change, note security/migration risk and test coverage. Don't change adjacent systems unrequested.

## After editing
Run relevant checks from `docs/TESTING.md`, report precise results (or why tests weren't run), update docs for changed behavior and append new owner-approved decisions to `docs/DECISIONS.md`. Summarize briefly: **Built / Why / Tests / How to verify / What needs owner input**.

## Implementation progress and phase approval
- `docs/PLAN.md` is the **single source of truth for implementation progress**: phases, task statuses, dependencies, blockers, approval history and verification evidence. Do not create competing task/status logs. `docs/DECISIONS.md` remains authoritative for owner-approved choices; specialist docs define behavior; `docs/DEVELOPMENT_PLAN.md` defines workflow.
- Before work, read the current phase and relevant task in `docs/PLAN.md`. Update status when work starts, scope changes, a check runs, or work completes. Record commands/checks actually run, outcomes, limitations and evidence references; never present planned tests as executed.
- Keep affected specifications synchronized with approved changes. Record unresolved choices explicitly rather than silently extending approval.
- **Request and receive explicit owner approval before advancing between phases.** Passing tests or approval of the overall plan does not authorize the next phase. At a boundary, summarize deliverables, verification, remaining risks and the next phase's scope; record approval before starting it. Work within an approved phase does not need repeated routine permission.
- Phase approval does not grant unspecified infrastructure changes, real-data migrations or API spend. Existing concrete authorizations persist within their stated scope.

## Phase-end commits (owner authorized)
- At the end of each phase, create a local Git commit of that phase's approved changes **only after all required checks pass** and affected documentation/PLAN verification evidence is synchronized. This is standing authorization for scoped local staging and commits; do not repeatedly ask for commit permission.
- Inspect the file list and staged diff before committing. Include only approved phase changes; exclude unrelated owner work, real health data, secrets, private credentials, generated dependencies/build outputs and unreviewed screenshots. Run the applicable tests, type/lint/build checks, secret scan and phase-specific security/recovery gates. A failed or unavailable required check blocks the commit; never silently skip it. Previously accepted check evidence is valid only if subsequent changes cannot affect that check, with the reason recorded.
- Record deliberate owner-approved test deferrals and their future gates explicitly; a deferral is not a passing test. It cannot waive other required checks. A phase-end checkpoint must include current documentation and describe any outstanding operational limitations.
- Verify commit success and report its hash, scope and checks. Do not report a phase checkpoint complete without a successful commit. If platform permissions block staging/commit, record the exact failure and keep the commit pending; repository instructions do not override the sandbox. Do not alter permissions, ACLs or sandbox controls to bypass the restriction.
- Local commit authorization does not permit pushing/publishing, force operations, history rewriting or committing unrelated work. Explicit owner approval is still required before starting the next phase, even after the commit succeeds.

## No surprise actions
No installation of privileged tools, network/public exposure, certificate/firewall changes, billable model calls, sensitive-file exfiltration, destructive operations or production migrations without authorization. Local synthetic fixtures only in Git and CI. Use secrets from ignored environment/secure storage, never print or commit them.

## Scoped dependency-install permission
Owner authorization (2026-10-29): agents may download, resolve, lock, install and update ordinary project dependencies required for work in an approved phase, without asking again for each terminal command. This includes application libraries, database/migration packages, test/build/type/lint tools and security scanners. Use established package registries (PyPI/files.pythonhosted.org and registry.npmjs.org), SleepIQ's `.venv`, local `node_modules` and workspace caches. Examples: `uv lock`, `uv sync`, project-environment `python -m pip install`, and project-local `npm install`/`npm ci`. Dependency audits may contact package advisory services using package metadata only.

Keep manifests/lockfiles synchronized, prefer locked installs, retain audit/test gates, and inspect unexpected package changes. Keep npm lifecycle scripts disabled unless a specific required build step has been inspected. This permission does not approve global/system installs, administrator privileges, arbitrary downloaded scripts, health-data/secret disclosure, paid services, changes to DNS/firewall/certificate trust, security-policy changes or a new architectural dependency choice. Existing phase-transition approval remains required.

Repository instructions record owner consent; they do not override tool sandbox/network restrictions. Never change proxy, execution policy or sandbox controls to evade a restriction. If downloads are technically blocked, record the exact failure and use the smallest necessary owner-assisted install step; do not ask for consent already granted here.
