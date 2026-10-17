# Implementation Plan: Risk Page Cosmetic Cleanup

**Branch**: `027-risk-page-cleanup` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/027-risk-page-cleanup/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Collapse the Risk page's two `dbc.Tabs` panels (return histogram, Value at Risk) into one
continuous page with the histogram first; fix the histogram statistics table so return-based
rows display in percent (matching the chart's x-axis) instead of raw unlabeled basis points;
drop the chart's median reference line, keeping only the mean; confirm/lock in that the chart's
x-axis already represents absolute return values (not deviation from the mean) with a
regression-proof test; replace the Value at Risk section's own "Look-back" dropdown with the
page's single shared date-range control (shortcut buttons extended with a page-local "2Y"
button to cover the server's VaR look-back codes), falling back to the VaR section's existing
empty state when the active shared range has no matching VaR look-back; and restyle the Value at
Risk backtest panel as a `dash_table.DataTable` so it visually matches the histogram's statistics
table. Pure presentation-layer and control-wiring change — no new calculations, consistent with
Constitution Principle I.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Dash 2.17+, dash-bootstrap-components 1.5+, Plotly 5+ (existing stack;
no new dependencies)
**Storage**: N/A (UI consumes `portfolio-analysis-service` over HTTP; no local persistence)
**Testing**: pytest (unit, in `tests/unit/`) + pytest-bdd (Gherkin, in `tests/bdd/`), matching
every prior Risk-page feature (024/025/026)
**Target Platform**: Browser, served by the existing Dash app (`app.py`)
**Project Type**: Single-project web UI (Dash) — no frontend/backend split within this repo
**Performance Goals**: No new performance requirement; must not add extra network round-trips
beyond what 024/026 already perform (changing range/account still triggers exactly one refetch
per changed input, as today)
**Constraints**: No change to `portfolio-analysis-service` contracts or calculations (Constitution
Principle I); existing VaR look-back codes (`1y`/`2y`/`5y`, server-reported via
`GET /v1/risk/var/methods`) are authoritative and not hard-coded
**Scale/Scope**: One page (`src/pages/risk.py` and its four helper modules
`_risk_chart.py`/`_risk_table.py`/`_var_controls.py`/`_var_backtest_panel.py`), plus the shared
`src/components/date_range_controls.py` date range component and the affected unit/BDD tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. API-Sourced Data, No Local Business Logic** — PASS. All values displayed (histogram
  statistics, VaR series/backtest figures) already come from `portfolio-analysis-service`
  responses. The only "calculation" this feature adds client-side is unit conversion for
  *display* (basis points → percent, already done for the chart in 025; extending the same
  conversion to the table is a formatting change, not a new financial calculation) and mapping a
  UI shortcut code to a server-reported look-back code (a presentation/control-wiring lookup, not
  a derived financial fact).
- **II. Layered API Architecture** — PASS. No API service code changes; this feature is entirely
  within the UI's presentation layer (`src/pages/`, `src/components/`).
- **III. Test-First with BDD (NON-NEGOTIABLE)** — PASS, with action required: existing Gherkin
  coverage (`var_risk_tab_shell.feature` et al.) asserts the tabbed structure and will be rewritten
  before implementation (Phase 2) to assert the merged single-page structure, the unit-matched
  table, the single reference line, and the single range control, per Red-Green-Refactor.
- **IV. Configuration Over Hard-Coding** — PASS. No new environment-specific constants; the VaR
  look-back codes continue to come from the API (`GET /v1/risk/var/methods`), not a hard-coded
  list, including for the new "2Y" shortcut (its *date-math offset* is a generic shared helper,
  already used for 1Y/3Y/5Y/10Y, not a one-off literal).
- **V. Standard Libraries and SOLID Design** — PASS. Reuses existing `dash_table.DataTable`,
  `dbc.ButtonGroup`, and Plotly `add_vline` patterns already established on this page; no bespoke
  UI primitives introduced. `ruff`/`mypy` must still run clean.

## Project Structure

### Documentation (this feature)

```text
specs/027-risk-page-cleanup/
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
├── components/
│   └── date_range_controls.py   # Shared account/date/shortcut controls (extend: +2Y shortcut)
└── pages/
    ├── risk.py                  # Risk page layout + callbacks (merge tabs; rewire range control)
    ├── _risk_chart.py           # Histogram chart (drop median vline; keep mean vline)
    ├── _risk_table.py           # Histogram statistics table (format return rows as percent)
    ├── _var_controls.py         # VaR controls block (remove Look-back dbc.Select)
    └── _var_backtest_panel.py   # VaR backtest summary (restyle to match DataTable look)

tests/
├── unit/
│   ├── test_risk_chart.py       # Mean-only vline; axis-scale regression assertion
│   ├── test_risk_table.py       # Percent-formatted return rows
│   ├── test_risk_page.py        # Merged single-page layout; no dbc.Tabs
│   ├── test_var_controls.py     # Look-back dropdown removed
│   ├── test_var_backtest_panel.py  # DataTable-style rendering
│   ├── test_var_risk_page.py    # Shared range control drives VaR fetch/empty-state
│   └── test_date_range_controls.py  # New 2Y shortcut date-math
└── bdd/
    ├── features/
    │   ├── risk_view_histogram.feature     # Update: percent-formatted table assertions
    │   ├── risk_shortcut_buttons.feature   # Update: +2Y button, drives both sections
    │   ├── var_risk_tab_shell.feature       # Replace: single-page shell, not a tab
    │   ├── var_risk_chart.feature            # Update: no separate look-back input
    │   └── var_risk_refetch_controls.feature # Update: shared range control triggers refetch
    └── steps/
        ├── test_risk_steps.py
        └── test_var_risk_steps.py
```

**Structure Decision**: Single-project Dash application (no frontend/backend split — this repo
*is* the UI, calling `portfolio-analysis-service` over HTTP). All changes are confined to the
existing Risk-page module family under `src/pages/` plus the shared `date_range_controls.py`
component (one additive shortcut), with matching updates to the existing unit and BDD tests under
`tests/`. No new modules, files, or directories are introduced beyond what the tree above lists.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
