# SleepIQ — Shared Coding-Agent Instructions

**Applies to Codex, Claude Code and other coding agents.** Read this file first. It is the **routing index**, not a dump of the whole project. Do **not** create a redundant `CLAUDE.md` by default.

## Mission
Build a secure, local-first Windows sleep analytics web app: Apple Watch / Apple Health → Health Auto Export → authenticated encrypted LAN ingestion → FastAPI → SQLite → React/TypeScript dashboard, charts, versioned scoring and on-demand AI analysis. The **owner learns and makes meaningful decisions**; the agent designs, implements, tests and explains.

## Hard constraints
- No scope creep: **no nocturia, manual daily log, notes, training, official Apple Sleep Score, general chatbot**, or excluded extras. Missing readings remain missing. Support configured Health Auto Export metrics, not the entire Health catalog.
- **Never ship proof-of-concept HTTP+8-character-token receiver.** Permanent syncing requires encrypted authenticated trusted-LAN solution and owner approval. No public exposure, silent cloud sync, health-data telemetry or secret leakage.
- Owner-approved choices in `DECISIONS.md` are authoritative. Preserve individual readings, idempotent imports, time-zone/DST correctness, score versioning, 14 successful daily backups, manually launched shortcut, AI only when invoked.
- Changes involving data deletion, real records, API spend, infrastructure/certificate/firewall permissions, security policy, irreversible migration, architecture or significant UX require owner approval.
- **Tests are part of every task.** Never fake test results, bypass security gates, fabricate data/statistics, or commit user health exports or secrets.

## Ask and teach — without wasting the owner's time
**Proactively flag contradictions, uncertainty, risk and meaningful improvements.** When an important decision is needed: explain what it means in accessible language, 2–3 options with pros/cons, your recommendation, then **wait for the owner's choice**. Group closely related choices into one short checkpoint. Don't repeatedly ask about minor constants or reopen resolved matters without new evidence. A practical implementation must explain what was built, why, tests actually run and a concept the owner learned. The user prefers numbered answers, not forms.

## Progressive context routing
Read **only** relevant docs and target files after this index:
| Work | Minimum additional context |
|---|---|
| Scope/feature interpretation | `PRODUCT.md` relevant section + `DECISIONS.md` |
| Repo structure, runtime, API contracts | `ARCHITECTURE.md` section(s) |
| JSON ingest, sleep session, time zones, metrics | `DATA_PIPELINE.md` + chosen architecture interfaces |
| Score, consistency, history | `SCORING.md` + nightly schema in `DATA_PIPELINE.md` |
| UI, charts, presets, accessibility | `DESIGN.md` + API shapes |
| Auth, TLS, privacy, AI egress, backups | `SECURITY.md` + relevant architecture section |
| Test plan or review | `TESTING.md` + specific requirement |
| Phase/ticket planning and model allocation | `DEVELOPMENT_PLAN.md` + `DECISIONS.md` |

Do not dump every doc into a task prompt. Cite file paths/section anchors; inspect narrow code ranges and expand only as needed. Maintain task notes/decisions for handoffs. Minimize unneeded tokens **without compromising correctness**.

## Before editing
1. Identify the task's acceptance criteria, constraints and files. Check `DECISIONS.md` for approved vs provisional choices.
2. If consequential ambiguity remains, propose grouped alternatives and request approval. **Explicit known scoring checkpoint:** fixed Deep/REM personal targets exist, but their score remains neutral in pilot; neutral numerical constants/tails are proposals awaiting owner sign-off.
3. Plan smallest safe change, note security/migration risk and test coverage. Don't change adjacent systems unrequested.

## After editing
Run relevant checks from `TESTING.md`, report precise results (or why tests weren't run), update docs for changed behavior and append new owner-approved decisions to `DECISIONS.md`. Summarize briefly: **Built / Why / Tests / How to verify / What needs owner input**.

## No surprise actions
No installation of privileged tools, network/public exposure, certificate/firewall changes, billable model calls, sensitive-file exfiltration, destructive operations or production migrations without authorization. Local synthetic fixtures only in Git and CI. Use secrets from ignored environment/secure storage, never print or commit them.
