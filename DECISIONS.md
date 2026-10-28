# SleepIQ — Decision Register

**Status:** v1.0 consolidated from owner answers through 28 October 2026. **Authority:** explicit owner approval in conversation; in case of conflicting documents, ask owner and update the relevant source. Do **not** silently elevate defaults to approved requirements. New approvals are appended here with date, rationale, changed files, and any superseded decision.

## Product and workflow
- Local Windows browser-based, premium dark personal sleep analytics app; Apple Watch → Apple Health → Health Auto Export → FastAPI → SQLite; React/TypeScript UI. Initial ingestion proof succeeded via manual HTTP POST; secure permanent ingress still to build.
- Owner makes consequential decisions; agents teach concepts in concise plain language, offer options/pros/cons/recommendation, ask whenever ambiguity/contradiction/improvement affects behavior or security. **Avoid excessive granular questions.** Prefer one grouped checkpoint per phase. Task-specific progressive disclosure and economical prompts/agent usage.
- Latest-night overview, custom 0–100 SleepIQ + consistency, individual charts for configured metrics, arbitrary metric overlay in real/normalized view, 7/30/90/all/custom range, rolling 7/30 trend, presets/default persisted SQLite, paired correlation explorer, AI analyst embedded in Analytics only on request, exports, backups.
- Include **all configured Health Auto Export metrics** (currently Sleep Analysis, Heart Rate, Heart Rate Variability, Respiratory Rate, Resting Heart Rate, Sleeping Wrist Temperature) and relevant future additions; **not** the entire Apple Health catalog.
- No nocturia features, daily manual entry, training logs, notes, Apple official Sleep Score, general chatbot, heatmap, period-vs-period comparison, anomaly detection or personal records.
- Configurable scoring initially via Python code; first algorithm deliberately simple and replaceable; historical rescore after approved formula changes. Import as much historical Apple Health data as possible; Excel may contribute underlying measurements only.

## Architecture A1–A7 (all approved)
| ID | Approved decision |
|---|---|
| A1 | FastAPI backend plus React/TypeScript frontend |
| A2 | Store individual readings **and** nightly summaries in SQLite |
| A3 | Retain raw JSON exports with configurable retention |
| A4 | Secure authenticated **encrypted direct LAN connection first**, not the temporary HTTP receiver |
| A5 | **Manually launch** application with shortcut/script; no automatic Windows startup |
| A6 | AI analysis **only on user request** |
| A7 | Daily SQLite backups on PC, keep latest **14 successful daily backups**; catch up on next launch |

## Data semantics D1–D9 (all approved)
| ID | Approved decision |
|---|---|
| D1 | Attribute overnight sleep to **wake-up local date** |
| D2 | Ignore naps in nightly analytics and scoring; preserve raw input |
| D3 | Join nearby sleep intervals via **configurable gap threshold**; exact value proposed by agent for approval |
| D4 | Apple Watch authoritative for sleep stages; avoid unnecessary multi-device complexity |
| D5 | Initially label/calculates **stage-based** efficiency; modular replacement |
| D6 | Prefer **time-weighted sleeping HR** when defensible; otherwise simple mean and visible limitation; overnight HRV uses SDNN samples |
| D7 | Missing measurements appear as **Missing data**, no estimates; no expectation of daily coverage |
| D8 | Idempotent upload merging, corrections and historical backfill |
| D9 | Preserve raw JSON **indefinitely during development**, with future configurable retention |

## Score decisions S1–S20 (approved details)
- S1: initially include duration, consistency, efficiency, Deep, REM and sleeping HR/HRV components; pilot is not clinically calibrated.
- S2/S9: weights **duration 30%, consistency 25%, efficiency 15%, Deep 10%, REM 10%, combined HR/HRV 10%**.
- S3/S10/S14/S20: duration <7 h poor, 7–<8 h satisfactory, ≥8 h good. **Smooth** duration anchors: 6 h →40/100; **7 h →75/100**; 8 h →100/100; ≥8 h remains at 100 in pilot. Lower-tail extrapolation is a provisional proposal.
- S4: if a **required input** is missing, show **Insufficient data**, no partial/estimated overall score.
- S5/S11/S13: consistency is equal bedtime/wake weighting; **10 points penalty per 20 minutes** circular-clock deviation on each part (continuous), 0–100 bounded.
- S6/S7: preceding **30 calendar days**, at least **7 prior eligible nights**, no future leakage, use historical sleep-onset and wake-time baselines separately, provisional until history expands.
- S8: separate editable Python config/module, versioning and historical recalculation.
- S12/S16: physiological component **neutral in pilot**, but **sleeping HR AND overnight HRV must both be present** for an overall score; no physiological target calibration initially.
- S15 initially favored personal baselines for stage scoring, **superseded by later S17 custom targets and S18 neutral pilot**.
- S17: personally defined stage targets for descriptive classification: **Deep 1 h adequate, 1 h 30 min+ great; REM 2 h adequate/good, below two hours progressively poor**. These targets exist in config but **do not activate in pilot overall score** without new owner approval.
- S18: **Deep and REM are neutral pilot contributions** (currently fixed placeholders); this is the later, controlling instruction pending phase-2 grouped check.
- S19: smooth efficiency scoring example selected: **80% →60, 90% →85, ≥95% →100**; tails are provisional.
- S20: ≥8 h duration scores 100, even when unusually long, until owner requests refinement.

**Provisional, not approved:** neutral Deep/REM/physiology subscore number (candidate 75), duration below 6 h tail (candidate −35 points/hour), efficiency lower tail/interpolation, gap threshold, transport/cert specifics, date travel policy, scoring example-night results. All are **agent proposals** to bundle for owner review, not reasons to ask another long questionnaire now.

## Required agent follow-up behavior
Planner reviews decisions for contradictions, risky assumptions, opportunities to improve. It is expressly allowed and encouraged to ask owner **any relevant high-impact question** with alternatives/pros/cons. It must not implement unresolved alternatives without approval. When approved, append `YYYY-MM-DD | decision | options/rationale | impacts | owner approval` and update relevant docs/tests. Don't reopen settled rules just to ask questions.

## Change log
- 2026-10-28 — Consolidated decisions above into a single register; outstanding scoring numeric parameters kept provisional for coding-agent planning rather than delaying doc completion.
