# SleepIQ — Scoring Engine and Consistency Specification

**Status: v1.0 — complete planning specification (owner-approved decisions plus explicitly provisional implementation defaults).**

**Status:** Draft v0.6 — S1–S20 decisions recorded; Deep/REM target activation and final numerical curves pending owner approval (28 October 2026)  
**Depends on:** `PRODUCT.md` v1.0; `ARCHITECTURE.md` v1.0; `DATA_PIPELINE.md` v1.0  
**Audience:** Owner, scoring implementation agents, test authors  
**Scope:** Deterministic, reproducible nightly SleepIQ score, sleep consistency and score evolution. **Component weights are approved, as are smooth duration scoring, 20-minute consistency steps and a neutral physiological pilot contribution. Duration anchor points, consistency penalty, Deep/REM owner-defined target thresholds, neutral pilot treatment, and neutral HR/HRV required-input policy are recorded; further numeric mappings and target activation remain open.**

> **Owner in control:** Before implementing meaningful scoring or data interpretation decisions, agents explain 2–3 choices in beginner-friendly language with advantages, limitations, recommendation and a request for approval. Keep the formula in an isolated Python module/configuration for v1. Teach the owner how to change, test and recalculate it. Do not silently choose weights or claim a placeholder is scientifically validated.

## 1. Approved product requirements

- Overall **SleepIQ score is 0–100**, calculated locally using transparent deterministic Python code.
- **Sleep consistency must be an overall-score component**, and also have its own separate **0–100 consistency score**.
- Compare actual sleep onset and final wake times with **preceding 30 calendar days**, not the current scored night or later data. A missing day must not count as a zero-quality night.
- Begin implementation with a **simple, explicitly provisional scoring formula**. Refine and owner-approve changes later.
- Source metrics include sleep duration, Core/Deep/REM/Awake, stage-based efficiency, sleeping HR, overnight HRV (recorded SDNN summary), respiratory rate, resting HR, wrist temperature and relevant future enabled metrics. Not every graphable metric has to be a score input without owner approval.
- Genuine absent values remain **Missing data**, not backfilled or estimated. **S4 approved: withhold overall score as “Insufficient data” whenever a required component is absent; do not impute.**
- Score definitions, coefficients, baselines and nightly calculations are versioned so all historical nights can be recalculated consistently. Changing a scoring definition never overwrites raw input data.
- Scores are explanatory self-tracking estimates, **not diagnostic or clinically validated indicators**.

## 2. Design boundaries

```text
Canonical Apple Health readings (DATA_PIPELINE.md)
  → versioned nightly metrics / quality and missing flags
  → versioned scoring-component functions
  → versioned consistency calculation (uses only preceding 30 calendar days)
  → versioned composition / missing-data rule
  → SleepIQ score + component explanations + method/version IDs
  → stored/rebuildable historical scores → dashboard, charts and AI context
```

Keep pure Python functions (input → output), tests, and configuration separate from FastAPI routes and UI. Configuration changes require explicit version bump and recomputation. Avoid formula settings hidden in frontend code or mutable, unversioned database fields.

## 3. Approved pilot scoring scope and open numerical parameters

### Approved S1: use duration, consistency, efficiency, sleep stages and physiology in the pilot

1. **Sleep duration**: approved qualitative bands: **<7 hours = poor; 7 to <8 hours = satisfactory; ≥8 hours = good**. Approved duration anchors are specified below; extrapolation below six hours is a provisional implementation default. Avoid rewarding unlimited duration blindly.
2. **Sleep consistency**: evaluate timing of sleep onset and waking relative to prior-night timing baselines; use circular time-of-day distance, not ordinary subtraction around midnight.
3. **Sleep continuity/efficiency**: use the explicitly labelled stage-based efficiency from D5, subject to its known limitations.
4. **Sleep stages**: include Deep/REM as visible measures and neutral pilot components per S18; owner-defined duration targets are descriptive until activated in a subsequent version. Avoid unintended double-counting.
5. **Physiology (approved S1):** include sleeping HR and overnight HRV in the pilot. Use a fixed neutral 10% contribution during the pilot per S12, while retaining HR and HRV presence requirements per S16. Do not silently assert population-optimal HR/HRV thresholds. RHR, temperature and respiratory rate remain graphable and need not influence the score until separately approved.

**Approved S2/S9:** prioritize **sleep duration and consistency** over other inputs; exact component percentages were approved in S9. Approved constants and baseline minimums are specified later; remaining minor details are explicitly provisional. The first algorithm is a **simple, consistent software prototype**, not an assertion about ideal sleep or health.

### Approved pilot component weights (S9)

| Component | Weight |
| --- | ---: |
| Sleep duration | 30% |
| Sleep consistency | 25% |
| Stage-based sleep efficiency | 15% |
| Deep sleep | 10% |
| REM sleep | 10% |
| Sleeping HR + overnight HRV (shared) | 10% |
| **Total** | **100%** |

Do not interpret the weights as clinically calibrated. **S12:** during the pilot, give the shared HR/HRV component a *neutral* contribution rather than scoring physiological values against targets. The neutral numerical subscore remains to be chosen; **S16 explicitly requires both sleeping HR and overnight HRV measurements to be present to issue any overall SleepIQ score, even while they have a neutral contribution**. If either is missing, show “Insufficient data”; the actual metrics remain marked “Missing data” as applicable. This is an intentionally strict owner preference. Display HR and HRV as their actual measurements in analytics, clearly disclose that they do not currently differentiate nightly scores, and retain the 10% weight for future versioned activation.

**S20 approved C:** use the 100-point plateau for all durations ≥8 h in the pilot (including beyond 9 h), and revisit unusually long durations later. This is an intentional simple pilot convention, not evidence that arbitrarily long sleep is optimal. For durations below 6 h, extrapolation and floor remain an owner-approval item.

**S10:** use a *smooth duration curve*, not discrete jumps at 7 and 8 hours. Preserve the owner's qualitative intention: below seven hours is poor, seven to less than eight is satisfactory, and eight or more is good. Approved anchor scores: **6 h = 40/100, 7 h = 75/100, 8 h = 100/100, 9 h = 100/100**; use interpolation between the anchors. Below-6 h behaviour remains for approval; for ≥8 h keep the plateau at 100 under S20, without additional increases.

**S11:** implement consistency deductions as a function of time deviation, parameterised in **20-minute units** (not the previously proposed 15 minutes). Approved penalty: **10 points per 20 minutes of absolute clock-time deviation**, interpolated continuously, deducted separately from bedtime and wake scores, clamped to 0–100; no unapproved grace window. Equal weighting of onset and wake time still applies.

## 4. Consistency score — required behaviour; formula unresolved

- Calculate separately for sleep onset and wake time using the **preceding 30 calendar dates** with valid, eligible overnight sessions; exclude target night and all future nights.
- Model times-of-day **circularly**: 23:50 and 00:10 are 20 minutes apart, not 23 hours 40 minutes. Prefer circular statistics or a mathematically equivalent, tested approach.
- Use source-record offsets and properly interpreted time zones across UK fall-back/spring-forward; avoid confusing actual elapsed time with clock time.
- Do not fill missing nights. Track and disclose eligible-history count and whether result is provisional.
- Baselines should not shift after adding future nights when recalculating older dates; test causality/no future leakage.
- Clarify travel-time-zone rules and minimum history requirements before implementation.

## 5. Versioning and auditability

Each calculated nightly score should store or be reproducible from: `sleep_date`, `score_version`, component values and weights, applicable configuration snapshot/hash, input nightly-calculation version, eligible sample counts, missing components, consistency baseline window/date IDs, computation timestamp and method flags. Provide a single owner-invoked or automated re-score routine after an approved formula change. Keep previous formula definitions and optionally their historical outputs for comparison; the current dashboard defaults to the selected active version.

## 6. Missing-data and early-history safeguards (S4 approved)

Never turn missing physiological readings into zeros. Do not manufacture historical dates to create a 30-day consistency baseline. Label insufficient-history or incomplete scores distinctly in the UI; preserve available metrics and other component values. **S4 decision:** withhold the overall score if any required input is missing and say “Insufficient data”. Display other available metrics separately; no partial scores, fallback formula or invented values. This could mean some nights have no score; user explicitly accepts gaps. Keep source nightly data intact.

## 7. Tests and acceptance criteria

- Deterministic repeated runs; bounded [0,100] output, stable rounding policy; no divide-by-zero.
- Midnight clock-distance tests, DST transitions, leap days, nonconsecutive dates and travel-offset cases.
- Baselines never contain current/future nights; reproducible historic results after later data imports.
- No scores fabricated for truly missing nights; consistent handling of naps (D2 excludes them).
- Version bump and historical recalculation match a from-scratch rebuild; original readings unchanged.
- Source-derived missing values remain missing; exactly the owner-approved fallback/partial-scoring policy.
- Clear explanations and component breakdown for owner verification, without medical claims.
- Tests for formula changes are run before an agent declares a completed task.

## 8. Owner decisions: S1–S16 (approved; remaining numerical details pending)

**S1 — APPROVED: C (all proposed pilot categories).** Include duration, consistency, stage-based efficiency, Deep/REM and physiology (sleeping HR and overnight HRV). Keep the first version simple, consistent and modular; do not attempt clinical calibration. Explain all limitations and uncertainty. Exact physiology component scoring is still pending numerical design approval.

**S2 — APPROVED: B (prioritize duration and consistency).** These two inputs have 55% combined weight under the approved S9 allocation.

**S3 — APPROVED qualitative duration bands.** **Under 7 hours = poor; 7 to under 8 hours = satisfactory; 8 hours or more = good.** This is an owner-defined rubric for the prototype, not medical advice. Exact points, upper-duration handling and smoothing at boundaries remain open, and the formula must be easy to edit.

**S4 — APPROVED: A (no overall score when a required component is missing).** Display **“Insufficient data”**; show available metrics, with no estimates, partial scores or fallback definitions.

**S5 — APPROVED: A (equal bedtime and wake-up influence).** Compute separate circular-clock deviations from each respective preceding-30-calendar-day baseline; combine both equally into a separate 0–100 consistency score. The deviation-to-points curve remains for owner review.

**S6 — APPROVED: A (minimum seven previous valid nights).** Use only valid previous overnight sleep sessions in the preceding 30 **calendar days**, and calculate a consistency score when at least seven qualifying nights exist. Display the sample size and mark the score *provisional* until greater history accrues. Missing calendar days do not count against the person; do not use older records beyond the 30-day window to meet the minimum. With fewer than seven, consistency is unavailable and the overall SleepIQ score is **Insufficient data** under S4.

**S7 — APPROVED: A (personal historical timing baselines).** Use preceding-30-calendar-day circular typical sleep onset and wake-up times, calculated separately without current/future-night information. No fixed target schedule. Preserve timezone and DST correctness.

**S8 — APPROVED: A (isolated Python scoring configuration).** Keep a small Python scoring module and clearly named, owner-editable parameter configuration; version the formula and provide a reproducible historical recomputation command. The dashboard displays per-component explanations. No visual formula editor in the pilot.

**S9 — APPROVED: A.** 30% duration, 25% consistency, 15% stage-based efficiency, 10% Deep, 10% REM, 10% shared sleeping-HR/HRV contribution.

**S10 — APPROVED: B.** Smooth, gradual duration score curve respecting the qualitative sleep-duration bands rather than abrupt jumps. Exact curve points and handling of unusually long duration pending approval.

**S11 — APPROVED: A with amendment.** Consistency penalty is based on **20-minute** clock-time deviations instead of 15-minute increments. Penalty magnitude and grace policy pending approval; preserve equal bedtime/wake influence.

**S12 — APPROVED: C.** HR/HRV have a neutral pilot contribution and are still displayed as actual measurements. They must not be interpreted as genuinely predictive or beneficial until thresholds are designed and approved. Despite being neutral, **S16 specifies HR and HRV are mandatory for issuing an overall score**; this stricter rule is a deliberate owner decision overriding the default logical interpretation.

**S13 — APPROVED: A.** Starting from 100, deduct **10 points for each 20 minutes** of bedtime or wake-up deviation from the preceding-30-day respective typical time, using continuous interpolation and a 0 floor. Average bedtime and wake-up sub-scores equally.

**S14 — APPROVED: customized A.** Sleep duration anchor points: **6 h → 40, 7 h → 75, 8 h → 100, 9 h → 100**, with continuous piecewise-linear interpolation. Exact extrapolation under 6 h and after 9 h requires sign-off.

**S15 — SUPERSEDED BY S17 owner amendment.** Rather than personal historical percentage baselines, use simple **absolute duration targets** for stage scoring when activated: **Deep: 1 hour adequate, less than 1 hour progressively worse, 1 hour 30 minutes or more great; REM: 2 hours adequate, less than 2 hours progressively worse, 2 hours or more good.** These are user-selected pilot preferences, not clinically validated targets. Exactly how “adequate” and “great/good” map to 0–100 remains open. **S18=C keeps both stage contributions neutral during the pilot**, pending explicit owner approval to activate target-based stage scoring.

**S16 — APPROVED: B.** **Both sleeping HR and overnight HRV must be present for a nightly overall score even while the physiological 10% scoring component is neutral.** Missing either makes overall score **“Insufficient data.”** Show genuinely missing metrics as **“Missing data”**. This explicitly overrides the earlier recommendation to treat neutral measurements as optional.

**S17 — APPROVED owner amendment (replaces history question).** No separate minimum-history requirement for Deep or REM: use fixed absolute stage-duration thresholds chosen by the owner (as stated under S15) instead of previous-night baselines.

**S18 — APPROVED: C.** Keep the Deep and REM component subscores **neutral** during the pilot while displaying actual stage durations and the owner-defined target categories separately. Do not let current Deep/REM stage amounts influence overall SleepIQ until the owner explicitly approves activation and a numeric mapping. Unlike genuinely missing measurements, neutral is a real fixed placeholder and must be labelled as such.

**S19 — APPROVED: A.** Use a simple, smooth stage-based efficiency curve with illustrative anchors: **80% efficiency → 60/100, 90% → 85/100, ≥95% → 100/100**. These were the proposed example anchors under A; confirm final tails below 80% and interpolation strategy before implementation.

**S20 — APPROVED: C.** Duration component stays capped at 100 for **8 hours or more** for now, revisitable later. For durations below 6 h, choose a deterministic lower-tail rule before coding.

**Consolidated status:** S1–S20 decisions recorded. The small remaining numerical choices are bundled in the provisional implementation defaults and one required owner checkpoint at implementation planning; do not silently promote proposals to approved decisions.

## 9. Remaining questions for later (not permission to implement silently)

- Remaining numeric choices: stage score placeholder(s) versus active owner-defined duration targets; what score counts as “adequate” or “great”; efficiency below 80% and interpolation; duration below 6 h; and neutral HR/HRV constant. Duration ≥8 h is capped at 100 by S20. Review worked example nights before finalizing.
- Final timezone/travel policy and D3 session selection rules. Minimum observations approved as seven valid prior nights within 30 calendar days.
- Whether and how score changes should preserve old-version scores visibly for comparisons.
- Score labels/colors, rounding and how to communicate incomplete scores in `DESIGN.md`.

## 10. Minimal context routing for coding agents

- Scoring code: `AGENTS.md`, this document sections 1–7 and approved S decisions; relevant nightly interface in `DATA_PIPELINE.md`; scoring tests only.
- Consistency code: this document sections 4, 6–7 and approved S5–S7; timezone/session contract in `DATA_PIPELINE.md`.
- Frontend presentation: approved score API contract, `DESIGN.md` scoring component, relevant accessibility tests.
- Never read full genuine health exports unless explicitly necessary and approved, nor paste them into LLM prompts. Use anonymised synthetic fixtures for tests.

**Implementation handoff:** This document is complete as a planning brief. The decisions S1–S20 above are authoritative. The following are **provisional suggestions, not owner approvals**, to make the first build straightforward:

- Neutral Deep subscore = 75/100; neutral REM = 75/100 (S18 overrides activating stage targets in the pilot). Still display owner-defined personal targets independently: Deep 1 h adequate, 1 h 30 min great; REM 2 h adequate/good, below progressively poor. The targets do **not** drive score until a later approved version.
- Neutral sleeping-HR/overnight-HRV combined subscore = 75/100. Under S16 **both actual measurements are mandatory** to issue a score even though physiology is neutral.
- Duration below 6 h: extend the 6→7 h slope (35 score points/hour) downwards, clamped at zero. Duration ≥8 h = 100, per S20. Linear interpolation between approved anchors (6 h→40, 7 h→75, 8 h→100) gives a continuous, easily testable curve.
- Efficiency: linear interpolation through 80%→60, 90%→85, 95%→100; below 80%, continue the nearest slope downwards and clamp to zero; above 95%, cap at 100. Efficiency uses stage-based sleep / (stage-based sleep + recorded Awake), not full time-in-bed efficiency.
- Total score = weighted sum of six bounded component subscores; choose and document a deterministic rounding rule (suggest 1 decimal internally, whole-number display).
- The 20-minute consistency rule means 0.5 points deducted per minute of circular bedtime or waking deviation, with each subscore clamped 0–100, averaged 50/50. The baseline is the circular mean of eligible previous 30-calendar-day clock times; at least seven valid prior nights. Handle ambiguous antipodal circular samples deterministically and flag low confidence rather than fabricate a baseline.

**Mandatory agent planning checkpoint:** Before implementing scoring, present the owner a **short grouped proposal** covering these provisional rules and the S17/S18 fixed-target-versus-neutral tension, with 2–3 worked-night examples and pros/cons of activation now versus later. Ask only consequential questions; do not reopen accepted choices. Approval may be given together in a single decision. Record the result and scoring version in `DECISIONS.md`. The owner asked not to spend time resolving every threshold during documentation creation. This file is finalized as a developer specification; provisional rules are not silently authorized for shipping.
