# Implementation Plan: Positions Page

**Branch**: `018-positions-page` | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/018-positions-page/spec.md`

## Summary

Replace the Positions page's placeholder content with a real,
position-scoped view driven by `portfolio-analysis-service`'s
`005-position-timeseries-api` endpoints: an Account/From/To/shortcut
control set identical to Overview's, a per-position attribute toggle panel
(shared rendering with Overview's own toggles, different data source), a
new position multi-select filter, a "Stacked area graph" toggle (with the
single-attribute constraint clarified in `/speckit-clarify`), a
high-contrast/stable-colored multi-series chart, and a from/to comparison
table with pastel up/down/flat shading below it.

Technical approach: extract the Account/From/To/shortcut-button controls
and their pure date-math helpers (currently Overview-only, in
`src/layout/shell.py` and `src/pages/_overview_chart.py`) into a new shared
module, `src/components/date_range_controls.py`, and extract the
attribute-toggle renderer into `src/components/attribute_toggles.py` —
both now called by *both* `overview.py` and the new `positions.py`, per the
spec's own "share the same implementation" assumption and confirmed by
`/speckit-clarify`'s finding that both pages' shortcut/clamp behavior is
already identical (research.md #1, #2). The client
(`src/services/portfolio_analysis_client.py`) gains three new methods
(`list_account_positions`, `list_position_attributes`,
`get_position_timeseries`) reusing the existing `AttributeDefinition` model
and adding `PositionSummary`/`PositionTimeSeriesEntry`/
`PositionTimeSeriesResponse` to `src/models/portfolio_analysis.py`. A new
pure-function module, `src/pages/_positions_chart.py`, holds the
stable/deterministic per-position color assignment (`hashlib`-based, not
Python's salted `hash()`), line/stacked-area figure building
(`go.Scatter(stackgroup=...)`, no new chart-library dependency), and the
comparison-table row/shading derivation (feeding
`dash_table.DataTable.style_data_conditional`). `src/pages/positions.py`
replaces the placeholder with a layout + callback set that mirrors
`overview.py`'s existing structure (mount-trigger fetch, default selection,
account-switch reset, one combined chart+table refresh callback,
`running=` for in-flight disabling). `shell.py` gains
`_build_positions_parameters_bar()` (shared controls +
Positions-only Stacked-area toggle and position multi-select) and a new
branch in `_render_parameters_bar()`. The pre-existing
`shell_parameters_bar_unchanged.feature` test is updated since Positions
intentionally stops using the static placeholder bar (research.md #7).

## Technical Context

**Language/Version**: Python 3.11 (unchanged from 015/016/017)
**Primary Dependencies**: None added. Reuses `dash>=2.17`,
`dash-bootstrap-components>=1.5` (new `dcc.Dropdown(multi=True)`,
`dbc.Switch`, and `dash.dash_table.DataTable` are all already bundled with
the existing `dash` package — no new PyPI dependency), `httpx`, `plotly`
(`go.Scatter(stackgroup=...)` is a built-in parameter, not a new trace
type), `structlog` — plus stdlib `hashlib`/`colorsys` for the new color
palette (research.md #5). Zero new third-party dependencies.
**Storage**: N/A — unchanged from 016/017 (stateless proxy; `dcc.Store` for
in-session caching, extended with three new Positions-scoped stores per
research.md's UI contract, not shared in-memory with Overview's own stores)
**Testing**: pytest + pytest-bdd + `dash[testing]` (unchanged). New pure
functions (`_color_for_position`, figure builders, comparison-row/shading
derivation) get failing unit tests first
(`tests/unit/test_positions_chart_shaping.py`, new); the extracted shared
date-shortcut helpers get their existing tests moved/kept green
(`tests/unit/test_date_range_controls.py`, new — relocated from
`test_overview_chart_shaping.py`); the five user stories get failing BDD
scenarios first (`tests/bdd/features/positions_*.feature`, new); the
now-incorrect placeholder-bar regression guard for `/positions` is updated
(`tests/bdd/features/shell_parameters_bar_unchanged.feature`, modified;
research.md #7)
**Target Platform**: Web browser (desktop and tablet widths), Dash/Flask
dev server locally — unchanged
**Project Type**: Single-project web UI (unchanged)
**Performance Goals**: No new performance goal beyond 016's existing 100ms
loading-feedback requirement — `running=` (reused from 017) satisfies it by
construction for every Positions control, same as Overview's shortcuts
**Constraints**: No client-side financial calculation (constitution
Principle I) — the comparison table's up/down/flat shading and each
column's value are both read verbatim from `entries[].{attribute}` at two
already-known dates (`from_date`/`to_date`), never computed from raw
transaction/price data; the color-assignment hash and the stacked-area
cumulative sum are presentational transforms (color, draw order), not new
financial facts (data-model.md's Position Comparison Row / Position Color
Assignment sections make this derivation explicit)
**Scale/Scope**: 1 page replaced (Positions, placeholder → real), 2 shared
modules extracted from Overview-only code (`date_range_controls.py`,
`attribute_toggles.py`) and now used by both pages, 3 new
`portfolio-analysis-service` endpoints integrated, 1 new pure-function
module (`_positions_chart.py`), up to 50 concurrently plotted/tabulated
positions (FR-005/FR-015), 5 user stories (P1: default view; P2: explore,
filter, comparison table; P3: stacked-area)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. API-Sourced Data, No Local Business Logic | **Pass.** All plotted/tabulated values are read verbatim from `GET /v1/accounts/{account}/position`'s `entries[]` — no PnL, return, or aggregate is computed client-side. The comparison table's "up/down/flat" and each cell's value are a direct read of two already-returned entries (matching `from_date`/`to_date`), not a derived financial fact (data-model.md's Position Comparison Row). Color assignment and stacked-area cumulative summing are presentational only (chart draw order / hue selection), the same carve-out 016/017 already relied on. |
| II. Layered API Architecture | **Pass.** New client methods (`list_account_positions`, `list_position_attributes`, `get_position_timeseries`) are pure data-access additions to the existing `PortfolioAnalysisClient` Protocol/implementation — no calculation logic added there. The new pure-function module (`_positions_chart.py`) contains only presentational transforms (color, figure shape, table shading), mirroring `_overview_chart.py`'s existing separation from `overview.py`'s callback/transport layer. |
| III. Test-First with BDD (NON-NEGOTIABLE) | **Pass (planned).** Each of the 5 user stories gets its own `.feature` file exercised via `pytest-bdd` + `dash_duo`, written and confirmed failing before the corresponding component/callback code, matching 015/016/017's discipline. New pure functions (color assignment, figure building, comparison-row shading) get failing unit tests first, including the 50-position high-contrast/stability property and the from==to "flat/unshaded" edge case. |
| IV. Configuration Over Hard-Coding | **Pass.** No new environment-specific value is introduced — the three new endpoint paths are literals in the same place existing endpoint paths already live (the client module), consistent with how 016 treated `/v1/accounts`/`/v1/timeseries/attributes` as source, not config. Control labels ("Stacked area graph") are fixed UI copy, consistent with existing shortcut-button-label precedent (017). |
| V. Standard Libraries and SOLID Design | **Pass.** Every new UI capability (multi-select, stacked-area, per-cell shading) uses a built-in mechanism of an already-installed library (`dcc.Dropdown(multi=True)`, `go.Scatter(stackgroup=...)`, `dash_table.DataTable.style_data_conditional`) rather than a new dependency or hand-rolled equivalent (research.md #3, #4, #6) — the same "prefer the library's own mechanism" discipline 017 established for `running=`. The color-palette function uses stdlib `hashlib`/`colorsys` only (research.md #5). Extracting the shared control/toggle builders (research.md #1, #2) is a direct application of single-responsibility/DRY once two pages need identical behavior, not a speculative abstraction — it's justified by the concrete second caller this feature introduces, not built ahead of need. |
| User Experience Standards | **Pass (planned).** `running=` (reused pattern from 017) gives ≤100ms loading feedback for every Positions control. The comparison table adds a drill-down-adjacent capability (compare start vs. current value per position) without requiring extra navigation — consistent with the constitution's "explain a number" mandate. Positions remains reachable in one click from any screen via the existing sidebar (unchanged). |

No violations requiring justification — Complexity Tracking table is empty.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (`data-model.md`, `contracts/`, `quickstart.md`):

- **Principle I**: Confirmed — `data-model.md`'s Position Comparison Row and
  Position Color Assignment sections show every table/chart value traces
  back to a verbatim `entries[]` field or a presentational-only
  transform; no new financial fact is derived anywhere in this feature.
- **Principle II**: Confirmed — `contracts/portfolio-analysis-api.md`'s
  three new client methods are data-access only; calculation-shaped logic
  (color, figure/table shaping) stays in the new pure `_positions_chart.py`
  module, mirroring `_overview_chart.py`'s existing layering.
- **Principle III**: Confirmed — `contracts/ui-contract.md`'s callback
  table maps directly onto the 5 user stories' BDD scenarios, planned to be
  written and failing before implementation.
- **Principle IV**: Confirmed — no new config surfaced during design; the
  new endpoint paths and control labels remain source-level constants,
  consistent with existing precedent.
- **Principle V**: Confirmed by research.md #1–#6 — every new capability
  maps to a specific, already-installed library mechanism, and the two
  shared-code extractions (research.md #1, #2) are traced to the concrete
  requirement (spec's Assumptions + `/speckit-clarify`) that made them
  necessary, not spec-speculative.
- **User Experience Standards**: Confirmed — `contracts/ui-contract.md`'s
  `running=` clause covers every Positions control that triggers a refresh,
  satisfying the 100ms feedback requirement by construction.

All rows still hold. **Gate: Pass.** No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/018-positions-page/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
│   ├── portfolio-analysis-api.md
│   └── ui-contract.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
portfolio-browser/
├── src/
│   ├── components/
│   │   ├── date_range_controls.py     # NEW — shared Account/From/To/shortcut builder +
│   │   │                               #   _earliest_from_date/_last_business_day/_shortcut_from_date/
│   │   │                               #   SHORTCUT_* (moved out of _overview_chart.py)
│   │   └── attribute_toggles.py       # NEW — shared build_attribute_toggle()/build_attribute_toggles()
│   │                                   #   (moved out of overview.py's private _attribute_toggle())
│   ├── layout/
│   │   └── shell.py                   # MODIFIED — _build_overview_parameters_bar() calls the shared
│   │                                   #   builder; + _build_positions_parameters_bar(); +
│   │                                   #   _render_parameters_bar() branch for "/positions"
│   ├── models/
│   │   └── portfolio_analysis.py      # MODIFIED — + PositionSummary, PositionsResponse,
│   │                                   #   PositionTimeSeriesEntry, PositionTimeSeriesResponse
│   ├── services/
│   │   └── portfolio_analysis_client.py  # MODIFIED — + list_account_positions(),
│   │                                   #   list_position_attributes(), get_position_timeseries()
│   │                                   #   (Protocol + Http implementation)
│   └── pages/
│       ├── _overview_chart.py         # MODIFIED — shortcut/date-math functions removed (now
│       │                               #   imported from src/components/date_range_controls.py);
│       │                               #   ATTRIBUTE_COLORS/_build_figure (Overview-specific) unchanged
│       ├── overview.py                # MODIFIED — imports shared controls/toggle builders instead
│       │                               #   of its own private copies; behavior unchanged
│       ├── _positions_chart.py        # NEW — _color_for_position(), 50-color palette generator,
│       │                               #   _build_figure() (line + stacked-area modes), comparison-row
│       │                               #   derivation + DataTable style_data_conditional builder
│       └── positions.py               # MODIFIED (replaces placeholder) — layout + callbacks mirroring
│                                       #   overview.py's structure for the position-scoped data
├── tests/
│   ├── bdd/
│   │   ├── features/
│   │   │   ├── positions_default_view.feature                 # NEW — US1
│   │   │   ├── positions_account_and_date_controls.feature     # NEW — US2
│   │   │   ├── positions_attribute_and_position_filters.feature # NEW — US3
│   │   │   ├── positions_comparison_table.feature               # NEW — US4
│   │   │   ├── positions_stacked_area_toggle.feature            # NEW — US5
│   │   │   └── shell_parameters_bar_unchanged.feature            # MODIFIED — Positions removed from
│   │   │                                                        #   the static-placeholder Examples;
│   │   │                                                        #   + "Positions shows real controls"
│   │   │                                                        #   scenario (research.md #7)
│   │   └── steps/
│   │       └── test_positions_steps.py                          # NEW — step definitions for the 5
│   │                                                             #   feature files above
│   └── unit/
│       ├── test_date_range_controls.py                          # NEW — relocated shortcut/date-math
│       │                                                         #   tests (from test_overview_chart_shaping.py)
│       ├── test_positions_chart_shaping.py                       # NEW — color stability/contrast,
│       │                                                         #   figure building, comparison-row shading
│       └── test_portfolio_analysis_client.py                     # MODIFIED — + tests for the 3 new
│                                                                  #   client methods
└── CLAUDE.md                                                     # MODIFIED — plan reference updated
```

**Structure Decision**: Two small shared modules
(`src/components/date_range_controls.py`, `src/components/attribute_toggles.py`)
are extracted from Overview-only code because this feature is the first
concrete second caller of that logic — not a speculative abstraction, but
a direct response to the spec's own "share the same implementation"
requirement, confirmed necessary (not just similar-looking) by
`/speckit-clarify`'s finding that both pages' date/shortcut behavior is
identical. Everything else follows the established
`016`/`017` pattern exactly: a placeholder page becomes real via a
layout+callbacks module in `src/pages/`, paired with a pure
presentational-transform module (`_positions_chart.py`, mirroring
`_overview_chart.py`) and client/model extensions for the new endpoints —
no new architectural layer, package, or project is introduced.

## Complexity Tracking

No violations — table intentionally empty.
