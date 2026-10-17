# Implementation Plan: Performance Page

**Branch**: `020-performance-page-chart` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/020-performance-page-chart/spec.md`

## Summary

Replace the Performance page's placeholder content with a real,
account-scoped line chart driven by `portfolio-analysis-service`'s
`007-performance-endpoints` endpoints: an Account/From/To/shortcut control
set that reuses Overview's shared component (with its first button
relabeled "ITD", clarified in `/speckit-specify`), a measure toggle panel
sourced from `/v1/performance/attributes` (shared rendering with Overview/
Positions' own toggles, different data source), and a percentage-formatted
multi-line chart. No stacked-area toggle, no comparison table, no
multi-select filter — per spec Clarifications, the chart and its controls
are this feature's entire scope.

Technical approach: the existing `TimeSeriesResponse`/`TimeSeriesEntry`/
`AttributeDefinition` models (016) are reused as-is for Performance data —
the upstream response shapes are byte-for-byte identical, so no new model is
added (research.md #1). The client
(`src/services/portfolio_analysis_client.py`) gains two new methods
(`get_performance`, `list_performance_attributes`), one method per endpoint
matching the existing `get_timeseries`/`list_attributes` convention exactly
(research.md #2). `src/components/date_range_controls.py::build_account_date_controls()`
gains one new optional parameter, `first_shortcut_label`, so Performance's
parameters bar can relabel the shared first shortcut button "ITD" without
touching its DOM id or the two unaffected callers (research.md #3);
Performance's own page-local shortcut→date mapping points that button's id
at the existing `SHORTCUT_ALL` code rather than `SHORTCUT_YTD` — a
deliberate, spec-accepted redundancy with the neighboring "All" button, not
a new shortcut code. A new pure-function module,
`src/pages/_performance_chart.py`, mirrors `_overview_chart.py`'s figure
builder but formats values as percentages and uses its own
measure→color mapping (research.md #6). `src/pages/performance.py` replaces
the placeholder with a layout + callback set mirroring `overview.py`'s
structure (mount-trigger fetch, default selection, account-switch reset —
using Overview's own full-history default, not Positions' YtD default per
research.md #4 — one combined chart-refresh callback, `running=` for
in-flight disabling), reusing `build_attribute_toggles()` verbatim with a
dynamically-computed default (first measure returned, not a hard-coded
name — research.md #5). `shell.py` gains
`_build_performance_parameters_bar()` and a new branch in
`_render_parameters_bar()`. The pre-existing
`shell_parameters_bar_unchanged.feature` test is updated since Performance
intentionally stops using the static placeholder bar (research.md #8).

## Technical Context

**Language/Version**: Python 3.11 (unchanged from 015/016/017/018)
**Primary Dependencies**: None added. Reuses `dash>=2.17`,
`dash-bootstrap-components>=1.5`, `httpx`, `plotly` (percentage
`tickformat`/hover-format strings are a built-in `d3-format` capability of
the already-used `go.Scatter`/`Layout`, not a new trace type or package),
`structlog`. Zero new third-party dependencies.
**Storage**: N/A — unchanged from 016/017/018 (stateless proxy; `dcc.Store`
for in-session caching, two new Performance-scoped stores per
research.md's UI contract, not shared in-memory with Overview's/Positions'
own stores)
**Testing**: pytest + pytest-bdd + `dash[testing]` (unchanged). The new pure
function (`_build_figure` in `_performance_chart.py`, plus its
color-mapping/percentage-formatting behavior) gets failing unit tests first
(`tests/unit/test_performance_chart_shaping.py`, new); the extended shared
`build_account_date_controls(first_shortcut_label=...)` parameter gets its
own failing unit test first (`tests/unit/test_date_range_controls.py`,
extended); the two new client methods get failing unit tests first
(`tests/unit/test_portfolio_analysis_client.py`, extended); the three user
stories get failing BDD scenarios first
(`tests/bdd/features/performance_*.feature`, new); the now-incorrect
placeholder-bar regression guard for `/performance` is updated
(`tests/bdd/features/shell_parameters_bar_unchanged.feature`, modified;
research.md #8)
**Target Platform**: Web browser (desktop and tablet widths), Dash/Flask
dev server locally — unchanged
**Project Type**: Single-project web UI (unchanged)
**Performance Goals**: No new performance goal beyond 016's existing 100ms
loading-feedback requirement — `running=` (reused from 017/018) satisfies it
by construction for every Performance control
**Constraints**: No client-side financial calculation (constitution
Principle I) — every plotted value is read verbatim from
`entries[].{measure}` at each returned date; a measure absent from an entry
(insufficient history) is simply not plotted for that date, never
backfilled, interpolated, or recomputed client-side (data-model.md's
Performance Entry section makes this explicit); percentage tick/hover
formatting and the fixed measure→color mapping are presentational
transforms only (display formatting, not a new financial fact), the same
carve-out 016/017/018 already relied on
**Scale/Scope**: 1 page replaced (Performance, placeholder → real), 1
shared component extended with one optional parameter
(`date_range_controls.py`), 2 new `portfolio-analysis-service` endpoints
integrated, 1 new pure-function module (`_performance_chart.py`), 0 new
Pydantic models (research.md #1), 3 user stories (P1: default view; P2:
explore accounts/dates; P2: choose measures)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. API-Sourced Data, No Local Business Logic | **Pass.** Every plotted value is read verbatim from `GET /v1/accounts/{account}/performance`'s `entries[]` — no return, PnL, or aggregate is computed client-side; a measure not yet computable is simply omitted, never backfilled or interpolated locally (data-model.md's Performance Entry section). Percentage tick/hover formatting and the fixed measure→color mapping are presentational only (display, not a new financial fact), the same carve-out 016/017/018 already relied on. |
| II. Layered API Architecture | **Pass.** The two new client methods (`get_performance`, `list_performance_attributes`) are pure data-access additions to the existing `PortfolioAnalysisClient` Protocol/implementation — no calculation logic added there. The new pure-function module (`_performance_chart.py`) contains only presentational transforms (color, percentage formatting, figure shape), mirroring `_overview_chart.py`'s/`_positions_chart.py`'s existing separation from each page's own callback/transport layer. |
| III. Test-First with BDD (NON-NEGOTIABLE) | **Pass (planned).** Each of the 3 user stories gets its own `.feature` file exercised via `pytest-bdd` + `dash_duo`, written and confirmed failing before the corresponding component/callback code, matching 015/016/017/018's discipline. The new pure function (figure building/formatting) and the extended client/shared-component code get failing unit tests first. |
| IV. Configuration Over Hard-Coding | **Pass.** No new environment-specific value is introduced — the two new endpoint paths are literals in the same place existing endpoint paths already live (the client module), consistent with 016/018 precedent. The "ITD"/"All" button labels are fixed UI copy, consistent with existing shortcut-button-label precedent (017); the default-toggled-on measure is computed from the API response, not hard-coded (research.md #5), avoiding a client-side assumption about upstream measure names/ordering. |
| V. Standard Libraries and SOLID Design | **Pass.** Percentage formatting uses Plotly's own built-in `d3-format` tick/hover-format mechanism (research.md #6) — no new dependency. Adding one optional parameter to `build_account_date_controls()` (research.md #3) is a direct, minimal response to a concrete second/third caller needing one different label, not a speculative abstraction — it changes nothing for the two existing, unaffected callers. Reusing `TimeSeriesResponse`/`TimeSeriesEntry`/`AttributeDefinition` outright (research.md #1) avoids duplicating an identical shape, directly serving DRY/SOLID single-responsibility (one model, one place it can drift). |
| User Experience Standards | **Pass (planned).** `running=` (reused pattern from 017/018) gives ≤100ms loading feedback for every Performance control. Performance remains reachable in one click from any screen via the existing sidebar (unchanged). |

No violations requiring justification — Complexity Tracking table is empty.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 (`data-model.md`, `contracts/`, `quickstart.md`):

- **Principle I**: Confirmed — `data-model.md`'s Performance Entry/Response
  section shows every chart value traces back to a verbatim `entries[]`
  field; no new financial fact is derived anywhere in this feature, and a
  measure's absence for a given date is passed through as-is (FR-014), not
  synthesized.
- **Principle II**: Confirmed — `contracts/portfolio-analysis-api.md`'s two
  new client methods are data-access only; formatting/color logic stays in
  the new pure `_performance_chart.py` module, mirroring
  `_overview_chart.py`'s/`_positions_chart.py`'s existing layering.
- **Principle III**: Confirmed — `contracts/ui-contract.md`'s callback
  table maps directly onto the 3 user stories' BDD scenarios, planned to be
  written and failing before implementation.
- **Principle IV**: Confirmed — no new config surfaced during design; the
  two new endpoint paths remain source-level constants, and the
  default-measure computation stays API-driven (research.md #5), consistent
  with existing precedent.
- **Principle V**: Confirmed by research.md #1–#8 — reusing existing
  models (#1) and the existing per-endpoint client method convention (#2)
  avoids new abstractions; the one new optional parameter (#3) and the one
  new small pure-function module (#6) are both traced to a concrete,
  spec-required need, not built ahead of it.
- **User Experience Standards**: Confirmed — `contracts/ui-contract.md`'s
  `running=` clause covers every Performance control that triggers a
  refresh, satisfying the 100ms feedback requirement by construction.

All rows still hold. **Gate: Pass.** No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/020-performance-page-chart/
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
│   │   └── date_range_controls.py     # MODIFIED — build_account_date_controls() gains
│   │                                   #   optional `first_shortcut_label: str = "YtD"` param
│   ├── layout/
│   │   └── shell.py                   # MODIFIED — + _build_performance_parameters_bar(); +
│   │                                   #   _render_parameters_bar() branch for "/performance"
│   ├── services/
│   │   └── portfolio_analysis_client.py  # MODIFIED — + get_performance(),
│   │                                   #   list_performance_attributes() (Protocol + Http impl);
│   │                                   #   no model changes (research.md #1)
│   └── pages/
│       ├── _performance_chart.py      # NEW — PERFORMANCE_ATTRIBUTE_COLORS, _build_figure()
│       │                               #   (percentage-formatted line chart)
│       └── performance.py             # MODIFIED (replaces placeholder) — layout + callbacks
│                                       #   mirroring overview.py's structure for performance data
├── tests/
│   ├── bdd/
│   │   ├── features/
│   │   │   ├── performance_default_view.feature           # NEW — US1
│   │   │   ├── performance_account_and_date_controls.feature # NEW — US2
│   │   │   ├── performance_measure_toggles.feature          # NEW — US3
│   │   │   └── shell_parameters_bar_unchanged.feature       # MODIFIED — Performance removed
│   │   │                                                    #   from the static-placeholder
│   │   │                                                    #   Examples; + "Performance shows
│   │   │                                                    #   real controls" scenario
│   │   │                                                    #   (research.md #8)
│   │   └── steps/
│   │       └── test_performance_steps.py                    # NEW — step definitions for the 3
│   │                                                          #   feature files above
│   └── unit/
│       ├── test_date_range_controls.py                       # MODIFIED — + test for
│       │                                                      #   first_shortcut_label param
│       ├── test_performance_chart_shaping.py                 # NEW — percentage formatting,
│       │                                                      #   measure→color mapping, figure
│       │                                                      #   building, missing-measure gap
│       └── test_portfolio_analysis_client.py                 # MODIFIED — + tests for the 2 new
│                                                               #   client methods
└── CLAUDE.md                                                  # MODIFIED — plan reference updated
```

**Structure Decision**: No new architectural layer, package, or shared
module beyond one optional parameter on an already-shared component
(`date_range_controls.py`). This feature follows the established
`016`/`017`/`018` pattern exactly: a placeholder page becomes real via a
layout+callbacks module in `src/pages/`, paired with a pure
presentational-transform module (`_performance_chart.py`, mirroring
`_overview_chart.py`/`_positions_chart.py`) and client extensions for the
two new endpoints — reusing existing models outright (research.md #1) since
this feature, uniquely among 016/018/020, needs zero new data shapes.

## Complexity Tracking

No violations — table intentionally empty.
