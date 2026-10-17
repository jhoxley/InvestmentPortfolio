# Implementation Plan: Overview Position Visualizations

**Branch**: `019-overview-position-visuals` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/019-overview-position-visuals/spec.md`

## Summary

Add two new visualizations to the Overview page, in a row below the
existing account performance chart: a pie chart of position weights (by
market value, as of the selected "To" date) on the left, and a "Biggest
winners and losers" table (top-5/bottom-5 by profit/loss, with book cost
shown alongside) on the right, with a green→pale→pale-blue→blue gradient
across the table's rows. Both stack vertically below tablet width.

Technical approach: this is a thin, additive extension of `018`'s existing
data layer — both widgets are served by one call to the
already-implemented `PortfolioAnalysisClient.get_position_timeseries()`
(`attributes=["market_value","pnl","book_cost"]`, `positions=[]`,
`start=end=<"To" date>`), so no new client method, model, or upstream
endpoint is needed. A new pure-function module,
`src/pages/_overview_position_widgets.py`, builds the pie
(`plotly.graph_objects.Pie`, per-slice label only ≥5% share, hover on
every slice) and the winners/losers table (ranked, tie-broken, gradient
via linear RGB interpolation anchored so the single worst position is
always the brightest blue regardless of how many losers exist).
`_positions_chart.py`'s `_format_attribute_value()`/monetary-attribute set
moves to a new shared module, `src/components/value_formatting.py`, since
this feature is a concrete second caller (`market_value`/`pnl`/`book_cost`
are all monetary). `src/pages/overview.py` gains one new, fully
independent callback (Inputs: account + "To" date only — never "From" or
the attribute toggles, per FR-010) and two new containers in its layout,
each in its own `dcc.Loading`. `src/layout/shell.py` is untouched — the
new callback reads the same `app-parameters-account`/`app-parameters-to-date`
IDs the existing chart already uses.

## Technical Context

**Language/Version**: Python 3.11 (unchanged from 015-018)
**Primary Dependencies**: None added. Reuses `plotly` (`go.Pie` is a
built-in trace type), `dash-bootstrap-components` (`dbc.Col(xs=, lg=)` is
a native responsive-breakpoint prop, not previously used in this codebase
but requires no new package), `httpx`/`structlog` (unchanged, no new
client method). Zero new third-party dependencies.
**Storage**: N/A — unchanged; no new `dcc.Store` needed (the new
callback's output is only two rendered component trees, not cached data
another callback reads back)
**Testing**: pytest + pytest-bdd + `dash[testing]` (unchanged). New pure
functions (pie-slice shaping, ranking/tie-break, gradient interpolation)
get failing unit tests first (`tests/unit/test_overview_position_widgets.py`,
new); the relocated `_format_attribute_value`/monetary-set tests move to
`tests/unit/test_value_formatting.py` (new); the two user stories get
failing BDD scenarios first (`tests/bdd/features/overview_position_pie_chart.feature`,
`overview_winners_losers_table.feature`, both new, steps added to the
existing `tests/bdd/steps/test_overview_steps.py`)
**Target Platform**: Web browser (desktop and tablet widths), Dash/Flask
dev server locally — unchanged
**Project Type**: Single-project web UI (unchanged)
**Performance Goals**: No new performance goal beyond the existing ≤100ms
loading-feedback requirement — each new container's own `dcc.Loading`
satisfies it by construction (research.md #6), independent of the existing
chart's own `running=`-based mechanism
**Constraints**: No client-side financial calculation (constitution
Principle I) — every plotted/tabulated value (`market_value`, `pnl`,
`book_cost`, percentage share) is read verbatim from a single already-fetched
response or derived by a purely presentational transform (sorting,
percentage-of-total, color interpolation), never computed from raw
transaction/price data; ranking and grouping are selection/ordering logic,
not new financial facts (data-model.md's Ranking algorithm makes this
explicit)
**Scale/Scope**: 1 page modified (Overview, already real from 016/017), 0
new API integration points (reuses 018's endpoint as-is), 1 new
pure-function module, 1 new shared formatting module (extracted, not
newly invented logic), 1 new callback, 2 new user stories (P1: pie chart;
P2: winners/losers table), up to ~50 positions per account (018's own
established scale) feeding into the pie chart's slice count and the
table's ranking pool

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. API-Sourced Data, No Local Business Logic | **Pass.** All values plotted/tabulated (`market_value`, `pnl`, `book_cost`) are read verbatim from `GET /v1/accounts/{account}/position`'s single-date response. Percentage share, ranking, tie-breaking, and gradient color are presentational transforms (division, sort, color interpolation) — not new financial facts — the same carve-out `016`-`018` already relied on. |
| II. Layered API Architecture | **Pass.** No data-access or calculation-layer change at all — this feature adds zero new client methods (research.md #1). The new pure-function module (`_overview_position_widgets.py`) contains only presentational transforms, mirroring `_overview_chart.py`/`_positions_chart.py`'s existing separation from callback/transport code. |
| III. Test-First with BDD (NON-NEGOTIABLE) | **Pass (planned).** Both user stories get their own `.feature` file, written and confirmed failing before the corresponding component/callback code, matching 015-018's discipline. New pure functions (slice shaping, ranking/tie-break, gradient interpolation) get failing unit tests first, including the fewer-than-10-positions and single-loser edge cases. |
| IV. Configuration Over Hard-Coding | **Pass.** No new environment-specific value introduced — the reused endpoint path is already a client-module constant from 018; the 5% labeling threshold and the gradient's hex endpoints are fixed, spec-defined UI constants (not environment-dependent), consistent with how 017 treated shortcut button labels as source, not config. |
| V. Standard Libraries and SOLID Design | **Pass.** Every new capability uses a built-in mechanism of an already-installed library (`go.Pie`'s own `text`/`hovertemplate`, `dbc.Col`'s own responsive breakpoint props, `dcc.Loading`'s own spinner) rather than a new dependency or hand-rolled equivalent (research.md #3, #5, #6). The shared-formatting extraction (research.md #2) is justified by a concrete second caller this feature introduces, not a speculative abstraction — same bar `018` applied to its own two extractions. |
| User Experience Standards | **Pass (planned).** `dcc.Loading` gives ≤100ms loading feedback for both new widgets. The pie chart + table together are themselves a drill-down-adjacent capability (composition and winners/losers without leaving Overview) consistent with the constitution's "explain a number" mandate; both already sit at position-level granularity (not a further-hidden aggregate), so no additional navigation target is required. Responsive stacking (FR-001a) keeps the page usable at the project's own established tablet width. |

No violations requiring justification — Complexity Tracking table is empty.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (`data-model.md`, `contracts/ui-contract.md`,
`quickstart.md`):

- **Principle I**: Confirmed — `data-model.md`'s Position Weight Slice and
  Position Performance Rank Row sections show every displayed value traces
  back to a verbatim response field or a presentational-only transform
  (percentage, sort/rank, tie-break, color); no new financial fact is
  derived anywhere in this feature.
- **Principle II**: Confirmed — `contracts/ui-contract.md`'s single
  callback is transport + calls into the new pure module only;
  `get_position_timeseries` (data access) is unchanged and untouched.
- **Principle III**: Confirmed — `contracts/ui-contract.md`'s callback
  table maps directly onto the 2 user stories' BDD scenarios, planned to
  be written and failing before implementation.
- **Principle IV**: Confirmed — no new config surfaced during design; the
  5% threshold and gradient endpoints remain source-level constants.
- **Principle V**: Confirmed by research.md #1-#6 — every new capability
  maps to a specific, already-installed library mechanism, and the one
  shared-code extraction (research.md #2) is traced to the concrete second
  caller this feature introduces.
- **User Experience Standards**: Confirmed — `contracts/ui-contract.md`'s
  `dcc.Loading` wrapping covers both new containers' loading feedback, and
  research.md #5's breakpoint choice was verified against this project's
  own existing tablet-width test constant (800px), not assumed from
  Bootstrap's default naming.

All rows still hold. **Gate: Pass.** No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/019-overview-position-visuals/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
│   └── ui-contract.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
portfolio-browser/
├── src/
│   ├── components/
│   │   └── value_formatting.py        # NEW — _format_attribute_value()/_PLAIN_NUMERIC_ATTRIBUTES
│   │                                   #   (moved out of _positions_chart.py; second-caller extraction)
│   ├── pages/
│   │   ├── _positions_chart.py        # MODIFIED — imports _format_attribute_value from the new
│   │   │                               #   shared module instead of defining it locally
│   │   ├── _overview_position_widgets.py  # NEW — _build_pie_figure(), rank/tie-break/split
│   │   │                               #   algorithm, _gradient_color(), _build_winners_losers_table()
│   │   └── overview.py                # MODIFIED — new layout row (two dcc.Loading-wrapped
│   │                                   #   containers) + one new independent callback
│   └── layout/
│       └── shell.py                   # UNCHANGED — no new parameters-bar controls needed
├── tests/
│   ├── bdd/
│   │   ├── features/
│   │   │   ├── overview_position_pie_chart.feature       # NEW — US1
│   │   │   └── overview_winners_losers_table.feature      # NEW — US2
│   │   └── steps/
│   │       └── test_overview_steps.py                     # MODIFIED — + step definitions for the
│   │                                                       #   2 feature files above
│   └── unit/
│       ├── test_value_formatting.py                       # NEW — relocated formatting tests
│       │                                                   #   (from test_positions_chart_shaping.py)
│       ├── test_positions_chart_shaping.py                 # MODIFIED — formatting-specific tests
│       │                                                   #   removed (relocated), rest unchanged
│       └── test_overview_position_widgets.py                # NEW — pie-slice shaping, ranking/
│                                                             #   tie-break/group-split, gradient
│                                                             #   interpolation (incl. n<10, n=1 edge cases)
└── CLAUDE.md                                                 # MODIFIED — plan reference updated
```

**Structure Decision**: One small shared module
(`src/components/value_formatting.py`) is extracted from Positions-only
code because this feature is the first concrete second caller of that
specific formatting logic — the same bar `018` applied to its own two
extractions, not a speculative abstraction. Everything else follows the
established `016`-`018` pattern exactly: new page content is added via a
pure presentational-transform module (`_overview_position_widgets.py`,
mirroring `_overview_chart.py`/`_positions_chart.py`) paired with a new,
independent callback in the already-real `overview.py` — no new
architectural layer, package, project, or API integration is introduced.

## Complexity Tracking

No violations — table intentionally empty.
