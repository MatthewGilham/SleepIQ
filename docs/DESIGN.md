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
- CSV/Excel exports for selected time range and metrics; state whether output is raw readings or computed nightly metrics. Respect formulas/version labels.
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
- Normalize each series using z-scores over the selected range. Define zero-variance behavior, eligible clock metrics and low-coverage rolling display before implementation.
- Approve one coherent visual proposal before material UI implementation; track approval only in docs/PLAN.md.
