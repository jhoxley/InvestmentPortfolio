# Implementation Plan: Risk Page (Return Histogram)

**Branch**: `024-risk-return-histogram-page` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/024-risk-return-histogram-page/spec.md`

## Summary

Add a new "Risk" page reusing the existing shared Account/From/To/shortcut-button controls
(`src/components/date_range_controls.py`) and the same default-range/account-switch/shortcut/error
patterns already used by `performance.py`, but with a page-local shortcut mapping that adds a new
"10Y" trailing-window option in place of "YtD"/"ITD" (1Y/3Y/5Y/10Y/ALL per the spec, not
1Y/3Y/5Y/ALL+YTD). A new `HttpPortfolioAnalysisClient.get_return_histogram()` call hits the
already-shipped `GET /v1/accounts/{account}/risk/return-histogram` endpoint; the page renders one
`dcc.Graph` bar chart (basis-point bucket → count) and one `dash_table.DataTable` (statistic/value,
excluding `std_dev_bands`) side by side in a single row, refreshed together by one callback keyed
off account/from-date/to-date, mirroring `performance.py`'s `_render_chart`.

## Technical Context

**Language/Version**: Python 3.11+ (existing project)
**Primary Dependencies**: Dash, dash-bootstrap-components, pydantic, plotly, httpx, structlog (all existing; no new dependencies)
**Storage**: N/A (no persistence; per-page `dcc.Store` for fetched accounts only, mirroring Performance)
**Testing**: pytest; pytest-bdd + Selenium/Chrome for BDD (existing `tests/bdd`), plain pytest for `tests/unit`
**Target Platform**: Desktop/tablet browsers via the existing Dash app
**Project Type**: Web application (Dash UI over `portfolio-analysis-service`)
**Performance Goals**: One fetch per user action (account/date/shortcut change); loading feedback within 100ms per constitution UX standard
**Constraints**: Must pass `ruff` and `mypy`; no callback id collisions with other pages' shared-control callbacks (`tests/unit/test_callback_registration.py`); reuses, not forks, the shared date-range component
**Scale/Scope**: 1 page, 1 new nav entry, 1 new client method + 2 new response models, 1 chart helper, 1 table helper, ~5 callbacks, 3 BDD feature files (one per user story)

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 — still passing.*

| Principle | Assessment |
|-----------|------------|
| I. API-sourced data, no local business logic | PASS. The page only calls the existing `/risk/return-histogram` endpoint and renders its `histogram`/`statistics` fields verbatim (a chart mapping and a table row list) — no return calculation, bucketing, or statistics math happens client-side. |
| II. Layered API architecture | PASS / N/A. UI-only change; the risk endpoint's own data-access/calculation/transport layering already exists in portfolio-analysis-service (spec 011) and is untouched here. |
| III. Test-first BDD | PASS. Each user story's Gherkin from spec.md becomes an executable `tests/bdd/features/risk_*.feature` file, seen failing before implementation (see tasks.md). |
| IV. Configuration over hard-coding | PASS. The new nav entry and the new "10Y" shortcut label live in `config/content.yaml`, not inline strings — mirroring how `projection.horizons` and `nav_sections` are already externalized. |
| V. Standard libraries / SOLID / static analysis | PASS. Reuses `date_range_controls.py`, `plotly.graph_objects`, and the existing `dash_table.DataTable` pattern (`_positions_chart.py`/`_overview_position_widgets.py`) rather than introducing a new charting/table library. `ruff` + `mypy` must stay clean. |
| UX standards | PASS. Loading state via `dcc.Loading` (existing pattern); controls disable during refresh (`running=[...]`, existing pattern); 60/40 single-row layout is a static, always-usable-width split at desktop/tablet widths. |

No violations, so the Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/024-risk-return-histogram-page/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── ui-contract.md    # Phase 1 output
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks (not this command)
```

### Source Code (repository root: `portfolio-browser/`)

```text
config/
├── content.py            # add RiskConfig? NO — no new config model needed; only
│                          # nav_sections gets a new entry (existing NavigationSection shape)
└── content.yaml           # add `risk` nav_sections entry; extend shared shortcut set
                            # (new "10y" key) alongside existing projection.horizons block

src/
├── components/
│   └── date_range_controls.py   # add SHORTCUT_10Y + its year-offset entry (additive;
│                                 # existing SHORTCUT_YTD/1Y/3Y/5Y/ALL behavior unchanged)
├── layout/
│   └── shell.py                 # add _RISK_PATH + _build_risk_parameters_bar()
│                                 # (build_account_date_controls(first_shortcut_label="10Y"))
├── models/
│   └── portfolio_analysis.py    # add HistogramStatistics, StdDevBand, ReturnHistogramResponse
├── services/
│   └── portfolio_analysis_client.py  # add get_return_histogram() to Protocol + Http impl
└── pages/
    ├── risk.py                  # new page: layout + callbacks (mirrors performance.py)
    ├── _risk_chart.py           # new: pure histogram -> go.Figure bar-chart builder
    └── _risk_table.py           # new: pure statistics -> dash_table.DataTable builder

tests/
├── bdd/features/
│   ├── risk_view_histogram.feature       # User Story 1
│   ├── risk_shortcut_buttons.feature     # User Story 2
│   └── risk_manual_date_range.feature    # User Story 3
├── bdd/steps/test_risk_steps.py
└── unit/
    ├── test_risk_chart.py
    ├── test_risk_table.py
    └── test_risk_page.py
```

**Structure Decision**: Existing single Dash project, following the exact file-per-concern split
`performance.py` (page/callbacks) + `_performance_chart.py` (pure chart builder) already
established, plus one additional pure-function module (`_risk_table.py`) for the statistics table
since this page has two rendered outputs instead of one. No new top-level directories.

## Design Notes

- **Shared controls, page-local shortcut mapping**: `risk.py` calls
  `build_account_date_controls(first_shortcut_label="10Y")` exactly like `performance.py` calls it
  with `"ITD"`. The only shared-component change is additive: `date_range_controls.py` gains
  `SHORTCUT_10Y = "10y"` and a `10: SHORTCUT_10Y` entry in `_SHORTCUT_YEAR_OFFSETS`, so
  `_shortcut_from_date` already knows how to resolve it via the existing `_years_before` helper —
  no new date-math code. `risk.py`'s own `_SHORTCUT_CODE_BY_BUTTON_ID` maps the shared first-button
  DOM id (`overview-shortcut-ytd`) to `SHORTCUT_10Y` instead of `SHORTCUT_YTD`/`SHORTCUT_ALL`, the
  same page-local-remapping pattern `performance.py` already uses (research.md #1).
- **Default range**: reuses `_earliest_from_date`/`_last_business_day` directly — same "full
  recorded history" default as Overview/Performance (spec Assumptions), via a
  `_sync_date_range_to_selected_account` callback copied from `performance.py`.
- **New client call**: `get_return_histogram(account_name, start, end) -> ReturnHistogramResponse`
  added to the `PortfolioAnalysisClient` Protocol and `HttpPortfolioAnalysisClient`, following the
  exact `_get(...)` + `model_validate(...)` shape every other method already uses. `start`/`end`
  are sent as-is (both optional server-side per the endpoint's contract, but this page always has
  a resolved date-range value once an account is selected, so both are always sent).
- **New models**: `StdDevBand`, `HistogramStatistics`, `ReturnHistogramResponse` added to
  `src/models/portfolio_analysis.py`, field-for-field matching
  `portfolio-analysis-service/app/models/risk.py` (verified against source, not assumed) — `histogram`
  is typed as `list[tuple[int, int]]`, matching the service's own field type.
- **Chart builder** (`_risk_chart.py`): one `go.Bar` trace, `x` = each pair's first element, `y` =
  each pair's second element, mirroring `_performance_chart.py`'s pure-function/no-side-effects
  shape so it stays unit-testable without Dash running.
- **Table builder** (`_risk_table.py`): builds rows from `HistogramStatistics.model_dump()` with
  `std_dev_bands` popped/excluded before iterating, in the field declaration order (count, mean,
  median, mode, minimum, maximum, std_dev, skewness, kurtosis — spec FR-010's required row order).
  A `None` value renders as a fixed "not available" placeholder string (spec FR-012), read from
  content config rather than hardcoded inline in more than one place if it turns out to be needed
  in a second location — for a single-use string, an inline module constant is sufficient
  (Principle IV targets environment-variable-shaped values and multi-use literals, not a single
  presentational string with no other definition site).
- **Layout (60/40 single row)**: one `dbc.Row` containing two `dbc.Col`s, `width=7` (chart) and
  `width=5` (table) — the closest exact 12-column split to 60/40 (58.3%/41.7%), avoiding a
  non-standard CSS percentage override so the page stays consistent with every other page's use of
  Bootstrap's grid.
- **Refresh/disable/error/empty states**: copied verbatim from `performance.py`'s
  `_render_performance`/`_empty_state`/`_error_state`/`_REFRESH_DISABLED_IDS` pattern, adapted to
  render two outputs (chart + table) from one callback instead of one.

## Risks

- `date_range_controls.py` is shared by Overview/Positions/Performance; adding `SHORTCUT_10Y` is
  additive and covered by that module's own existing unit tests plus this feature's new BDD
  coverage, but `tests/unit/test_callback_registration.py` must still be re-run to confirm no
  cross-page callback id collision (same risk class as spec 023's plan).
- The risk endpoint's `histogram` can be empty or very sparse for short/volatile-free windows
  (edge case in spec.md) — `_risk_chart.py` must render a valid (if visually sparse) bar chart
  rather than erroring on an empty list, distinct from the page-level "no data" state which covers
  a `count: 0` response entirely.
