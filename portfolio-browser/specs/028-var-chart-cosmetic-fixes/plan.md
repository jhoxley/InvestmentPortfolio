# Implementation Plan: Value at Risk Chart Cosmetic Fixes

**Branch**: `028-var-chart-cosmetic-fixes` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-var-chart-cosmetic-fixes/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Move the Value at Risk chart's legend to below the whole figure (currently it sits inside
the plot area and pushes the backtest panel off-screen); collapse the backtest summary's
up-to-three per-confidence-level `DataTable`s into one table with one column per selected
confidence level; hide the realised-PnL bar trace when the chart's units are percentage
(no percentage-equivalent PnL field exists in the data model, so hiding — not rescaling —
is the correct fallback, confirmed against `src/models/portfolio_analysis.py`); and add a
caption above each of the chart's two subplot rows via Plotly's native `subplot_titles`,
preserving the existing shared-x-axis zoom/pan link between the main and linked charts
rather than splitting them into two separate `dcc.Graph` components. Pure presentation
change — no calculation, contract, or data-model change (Constitution Principle I).

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Dash 2.17+, dash-bootstrap-components 1.5+, Plotly 5+ (existing
stack; no new dependencies)
**Storage**: N/A (UI consumes `portfolio-analysis-service` over HTTP; no local persistence)
**Testing**: pytest (unit, in `tests/unit/`) + pytest-bdd (Gherkin, in `tests/bdd/`),
matching every prior Risk-page feature (024/025/026/027)
**Target Platform**: Browser, served by the existing Dash app (`app.py`)
**Project Type**: Single-project web UI (Dash) — no frontend/backend split within this repo
**Performance Goals**: No new performance requirement; this remains the existing
zero-network-call "instant controls" callback (`_render_var_view`) — units, confidence
selection, and PnL basis continue to re-render from already-fetched data only
**Constraints**: No change to `portfolio-analysis-service` contracts or calculations
(Constitution Principle I); the combined backtest table and hidden-PnL-in-percent-mode
behavior must not alter any VaR/backtest figure's own value, only its layout/visibility
**Scale/Scope**: Two helper modules (`src/pages/_var_chart.py`,
`src/pages/_var_backtest_panel.py`) plus their existing unit/BDD tests; `risk.py` itself is
expected to need no change (it already just calls `build_figures`/`build_panel` and renders
their results verbatim)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. API-Sourced Data, No Local Business Logic** — PASS. Every value plotted or tabulated
  already comes from the already-fetched `risk-var-store` payload (series, backtest,
  methods). Hiding a trace, repositioning a legend, restructuring a table's columns, and
  adding static caption text are presentation choices, not new financial facts.
- **II. Layered API Architecture** — PASS. No API service code changes; entirely within
  `src/pages/_var_chart.py` and `src/pages/_var_backtest_panel.py`.
- **III. Test-First with BDD (NON-NEGOTIABLE)** — PASS, with action required: existing
  Gherkin coverage (`var_risk_chart.feature`, `var_risk_backtest_panel.feature`,
  `var_risk_instant_controls.feature`) asserts the pre-change table/legend/units behavior
  and will be extended before implementation, per Red-Green-Refactor.
- **IV. Configuration Over Hard-Coding** — PASS. No new environment-specific constants;
  confidence levels and their column count continue to come from already-fetched data
  (`selected_confidence_bp`), not a hard-coded count.
- **V. Standard Libraries and SOLID Design** — PASS. Reuses Plotly's own `subplot_titles`
  and legend-positioning options and the existing `dash_table.DataTable` component; no new
  bespoke UI primitives. Chosen specifically *because* it avoids introducing a second
  `dcc.Graph` component and the extra zoom/pan-sync wiring that would otherwise be needed
  to keep the two chart rows linked (research.md #4). `ruff`/`mypy` must still run clean.

## Project Structure

### Documentation (this feature)

```text
specs/028-var-chart-cosmetic-fixes/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── pages/
    ├── _var_chart.py            # Legend position; hide PnL bar in pct mode; subplot captions
    └── _var_backtest_panel.py   # Single combined DataTable (one column per confidence level)

tests/
├── unit/
│   ├── test_var_chart.py            # Legend position; pct-mode bar hidden; subplot_titles present
│   └── test_var_backtest_panel.py   # Single table, columns tracking selected confidence levels
└── bdd/
    ├── features/
    │   ├── var_risk_chart.feature             # Update: captions; pct-mode PnL hidden
    │   ├── var_risk_backtest_panel.feature     # Update: one combined table, not per-level tables
    │   └── var_risk_instant_controls.feature   # Update: switching units toggles PnL visibility
    └── steps/
        └── test_var_risk_steps.py
```

**Structure Decision**: Single-project Dash application (unchanged from 024–027). Every
change is confined to the two existing VaR-chart/panel helper modules under
`src/pages/` and their matching unit/BDD tests; `risk.py`'s own layout and callbacks need
no change, since it already renders `build_figures()`'s and `build_panel()`'s output
verbatim without inspecting their internal structure.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
