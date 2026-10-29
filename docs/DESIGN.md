# SleepIQ — Interface and Interaction Design

**Status:** Complete v1.0 design brief; detailed visual choices are agent proposals requiring owner approval at the design checkpoint. **Audience:** frontend designer/agent, reviewer, Playwright author. **Read with:** `PRODUCT.md` relevant sections and approved API contracts; not the entire repository.

## 1. Experience
Build a **premium, dark, desktop-first local web application** for a single user. It should feel precise, fast and calm: generous spacing, subtle contrast, restrained accent color, strong typographic hierarchy, and readable charts. Avoid a generic admin dashboard, overwhelming neon, gamification, clinical claims, or crowded cards. Responsive at laptop/tablet widths, usable on mobile but desktop is primary. Respect reduced-motion and keyboard accessibility.

**Layout:** Persistent left navigation (Dashboard / Analytics / Correlations / Data & Settings), compact top status bar (last successful sync, backup health, active score version). The first viewport answers “how was my latest recorded night?”; advanced exploration comes lower on the page or through Analytics. No daily logging or editable diary.

## 2. Dashboard — latest recorded night
- Date label uses the **wake-up calendar date**, with local sleep onset and wake time prominently shown.
- Large **SleepIQ /100** hero showing score, version and provisional status. If required data is missing, show **Insufficient data**, never a fabricated score.
- Separate **Consistency /100** with 30-day lookback and count of qualifying previous nights (minimum 7); mark early baseline provisional.
- Metric cards: total asleep, recorded awake, Core, Deep, REM, sleep efficiency (explicitly **stage-based**), sleeping HR, overnight HRV (**mean of overnight SDNN samples**, ms), resting HR, respiratory rate, sleeping wrist temperature. Cards only appear for configured/available metrics; missing values display **Missing data**.
- Stage timeline (hypnogram), aligned by real timestamps, clear stage legend and hover details; DST/midnight must not distort elapsed durations. Distinguish timestamps from durations.
- A concise breakdown of each score component with weight, contribution and pilot-neutral indicators for Deep/REM and HR/HRV (unless the owner approves activation later). Do not imply clinically validated thresholds.
- Approved 7/30-calendar-day rolling trends (no period-versus-period comparisons) only if defensible data exists; no invented improvement narrative.

## 3. Analytics — one graph per metric, plus multi-metric exploration
- Every supported metric has an individual time-series chart. Accept new configured metrics without inventing a manual redesign; unknown shapes remain retained and visibly unsupported until validated.
- **Multi-metric overlay:** choose any available metrics and compare using **actual units** (clearly separated axes/labels) or **normalized trend** mode; avoid misleading same-axis comparisons between beats/min, hours, milliseconds and °C. Show normalization method and baseline in chart details.
- Date range controls: **7 / 30 / 90 days / All / Custom**. Missing nights create gaps, not zeroes. Time axes represent actual calendar intervals.
- Optional rolling **7-day / 30-day** averages; show minimum coverage and sample counts; use calendar-day windows with observed-night counts (P6).
- Interactions: accessible hover/focus tooltips with exact date, value, units and source/method when relevant; legends for toggling series; zoom without losing selected dates.
- **Saved chart presets**: save, name, load, rename/edit, delete, choose default. Persist per-user settings in SQLite. Protect against accidental overwrite; require confirmation for destructive actions.
- **AI investigator embedded in Analytics, not a separate general chatbot.** A deliberately scoped question input (e.g., “Is my sleeping HR correlated with deep sleep?”), selected range/metrics context, explicit **Analyze** action, traceable numeric evidence from backend statistics, clear uncertainty and API-use disclosure. No unsolicited calls or medical instructions.

## 4. Correlation explorer
Select any two eligible numerical nightly metrics, choose date range, render scatterplot and line of best fit only when data supports it. Display coefficient type, value, paired-night **n**, missing-data exclusions and a short reminder that correlation is not causation. Make comparison with mismatched observations explicit. Treat time trend/confounding as limitations; do not pretend inference is causal. Reject insufficient paired samples cleanly.

## 5. Data and Settings
- Health Auto Export receiver status, last successful import, counts, errors **without raw health payloads or secrets**.
- CSV exports for selected time range and metrics (Excel/XLSX not built, P22); the panel states the output is computed nightly metrics, not raw readings. Version labels are included and spreadsheet formulas are neutralised.
- Database status, daily backup (14 retained successful days), last restore verification, backup folder, restore instructions and caution.
- Score configuration version and a link to the Python scoring config documentation; **no dashboard formula editor in v1**.
- Basic retained-JSON policy (indefinite during development, configurable), privacy warning, local-only service status, manually launched app controls.

## 6. Visual system — defaults to show owner before UI polish
- Dark near-charcoal background, slightly lighter elevated surfaces, muted grid lines, restrained blue/teal accent; avoid color as the sole signal of health/quality.
- 8px spacing rhythm, consistent radius, one sensible sans-serif family with fallback fonts, readable numbers with tabular alignment, clear focus outlines. Design tokens centralized in CSS variables/Tailwind theme.
- Charts have legible grids and accessible contrast; stage colors remain consistent everywhere. Prefer SVG/vector charts for sharpness, tooltips and interaction.
- Empty, loading, failed import, no-history, partial-metric, baseline-provisional, AI-unavailable and offline states all need intentional copy and tested UI.
- Micro-interactions should be subtle and disabled/reduced for motion preferences.

## 7. Implementation guidance and acceptance
**Candidate stack:** React + TypeScript + Tailwind + Recharts, with accessible component primitives as needed. Treat library choice as a proposal if it constrains design. Define small reusable components: `MetricCard`, `ScoreHero`, `StageTimeline`, `MetricSeriesChart`, `MetricPicker`, `ChartPresetMenu`, `CorrelationPanel`, `InvestigatorPanel`, and status indicators. Keep business calculation in Python; UI formats results, never reimplements scoring rules.

Acceptance: latest night readable in first viewport; individual and overlay charts operate with real/mock API; presets round-trip through SQLite; missing values never become zero; custom range and normalized view work; AI only on click; keyboard and accessibility checks pass; Playwright captures desktop and narrow-width screenshots. Never add nocturia, training, notes, or daily manual forms.

## 8. Owner-in-the-loop design checkpoint
The implementing agent should present **one compact visual proposal** (wireframe/screenshot plus 1–3 meaningful options) and explain trade-offs (density, navigation, chart complexity, accessibility/performance). Ask for owner approval before locking in the look and any materially different layout. Routine icon, padding and component implementation choices do not need approval. Offer improvements, identify contradictions and allow owner to decide. Log accepted design changes in `DECISIONS.md`.

## Approved planning refinements P2/P3/P6
- Latest selected night remains visible if unscored, with separate partial/conflicted status; do not silently substitute an older scored night.
- Deep, REM and combined physiology each neutral at 75. Disclose pilot ceiling 92.5; overall display one decimal, calculations retain precision.
- Pearson correlation on paired nights; unavailable for <3 pairs or constant series. Show n, exclusions and exploratory limitations, not significance/causation.
- Normalize each series using z-scores over the selected range. Zero-variance behavior, clock-metric eligibility and low-coverage rolling display are now defined by P21 (see DECISIONS.md and "A01 implemented interactions" below).
- Approve one coherent visual proposal before material UI implementation; track approval only in docs/PLAN.md.

## Initial working proposal (Phase 3, 2026-10-29)
The initial dashboard preview implements a charcoal/mint visual direction with lavender/blue sleep stages, persistent navigation, a three-panel latest-night overview, stage timeline, metric grid and score breakdown. It uses labelled synthetic fixtures only and provides complete, missing-HRV and empty-history states. Operational status explicitly says not connected. SVG charts and native controls require no added dependencies. This is a review proposal; visual approval remains pending in PLAN.md. Analytics, correlations and settings destinations show their future scope, not implemented workflows (historical: Analytics was implemented in U02 and Correlations in A01). Score fixtures are precomputed; production scoring remains in Python.

Colour-only review alternatives: `?theme=iris` (Midnight Iris: inky violet surfaces, lavender accents, lilac/periwinkle stages) and `?theme=ember` (Ember: warm graphite surfaces, champagne/copper accents, rose/clay stages). No query parameter retains original mint. All alternatives share identical structure, dimensions, typography and interactions; CSS colour tokens also drive SVG stage fills and matching legends. Owner requested layout preservation; final palette remains undecided.

Additional owner-requested bold colour explorations retain the same layout: Acid Bloom (`?theme=bloom`) combines aubergine, acid lime and orchid; Electric Tide (`?theme=tide`) combines deep navy, coral and cyan; Solar Velvet (`?theme=velvet`) combines plum, saffron and turquoise. Secondary colours highlight existing consistency and alternate metric numbers, with two-colour chart fills. Prior themes remain available. These are owner-requested alternatives to the restrained default, pending selection.

Owner-requested darker gaming alternatives: `?theme=blackout` uses graphite/silver; `?theme=terminal` uses black/phosphor green; `?theme=afterburn` uses carbon/red. Mixed options `?theme=reactor` combine gunmetal/orange/ice blue, and `?theme=overdrive` combine black/yellow/cyan. Only colours change; all earlier palettes remain available. Final selection remains pending in PLAN.md.

Terminal and Afterburn follow-up explorations (owner favourites; final palette not yet selected): Terminal Ghost (black/pale phosphor), Venom (acid/chartreuse), Glacier (green/ice cyan), Hazard (green/amber), Mainframe (emerald/steel); Afterburn Inferno (orange-red/gold), Bloodline (black/crimson), Arctic (red/ice blue), Ignition (red/signal yellow), Obsidian (red/silver). URL values are `terminal-ghost`, `terminal-venom`, `terminal-glacier`, `terminal-hazard`, `terminal-mainframe`, `afterburn-inferno`, `afterburn-bloodline`, `afterburn-arctic`, `afterburn-ignition`, `afterburn-obsidian`. All share the existing geometry and typography; the parent themes remain available.

## Selected visual direction (2026-10-29)
Owner approved the original **Afterburn** palette with the existing dashboard layout. This supersedes the initial charcoal/mint default and pending palette-selection statements above. The normal URL now defaults to Afterburn; explicit comparison query parameters retain their palettes for reference. This is visual approval only; production API integration and remaining Phase 3 acceptance work are tracked in PLAN.md.

## U02 implemented interactions
Analytics retains Afterburn and uses selected-metric individual SVG charts plus multi-metric exploration. Actual-unit comparisons group only identical units on a shared axis; different units use vertically aligned panels. Normalized mode shares a z-score axis. Clock metrics are actual-only, displayed as source-local times with offsets in point details. Metrics remain selectable when absent, showing missing data rather than vanishing.

Calendar gaps break lines. Point focus/hover exposes exact dates, values, units/methods, sample counts and flags; expandable tables provide all values. Legend buttons toggle visibility; keyboard-accessible zoom sliders preserve date selection and the selected-range normalization baseline. Presets support new/save-as, load, rename/update, default, confirmed deletion and conflict-safe reload. Rolling averages and correlation were deferred to A01 at that task boundary; both are now implemented (next section).

P21: constant series cannot normalize; clock times excluded from normalization/correlation; future rolling means require 4/7 or 15/30 observed nights, with counts shown.

## A01 implemented interactions
Analytics adds a Rolling average control (Off / 7-day / 30-day), saved with presets. Rolling means draw as a dashed line in the series colour on both overlay and individual charts. They are trailing calendar windows computed in Python, shown only with at least 4 of 7 or 15 of 30 recorded nights (P21). Tooltips and the data table always show coverage, e.g. "7-day mean 7.20 h (5/7 nights recorded)" or "unavailable (3/7 nights recorded; needs 4)". Clock metrics have no rolling mean. In normalized mode the rolling line uses the same z transform as its points.

The Correlations navigation destination is the correlation explorer. It has X/Y pickers limited to non-clock metrics, a range picker matching Analytics, a large Pearson r (or "Unavailable" with the reason), paired-night n, and exclusion counts for missing X, missing Y and neither. It also shows a focusable scatter plot with unit-labelled axes, a paired data table and fixed copy: exploratory only, no significance test, not evidence of cause, unstable with few pairs. There are no strength labels or p-values.

## Loading without layout shift
While analytics or correlation data reloads, the previous results stay in place, dimmed (no fade under reduced motion), with loading text in a reserved toolbar slot. Results are never unmounted for a reload, because collapsing the page made the browser jump the scroll position. Results clear only for errors, invalid ranges or an empty selection.
