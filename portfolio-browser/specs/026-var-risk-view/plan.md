# Implementation Plan: Value at Risk View (Risk Page)

**Branch**: `026-var-risk-view` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/026-var-risk-view/spec.md`

## Summary

Add a second `dbc.Tab` ("Value at Risk") to the existing `/risk` page, alongside the current
histogram tab, sharing the page's existing account selector, date range and shortcut buttons
unchanged. The new tab adds its own controls (confidence-level multi-select, look-back select,
units toggle, PnL-basis toggle, "hide degraded" toggle, "show ES" toggle) and renders: a main
chart (daily realised PnL bars with a VaR overlay line per selected confidence level, exceedances
highlighted, optional ES overlay), a smaller linked chart (total market value + proxied/rescaled
share), and a backtest summary panel. All three new `portfolio-analysis-service` read endpoints
(`GET .../risk/var`, `GET .../risk/var/backtest`, `GET /v1/risk/var/methods`) and the existing
`GET .../risk/var/status` are consumed exactly as they are, via new client methods and models —
no change to that service. The key design decision (research.md #1) is a two-callback split: one
callback fetches on account/date/look-back change (the series once, the backtest **four times**
— crossing `pnl_basis` × `min_quality` — since those are server-side parameters that change the
computed statistics, not just their display; and the status once) into a `dcc.Store`; a second,
purely client-side callback re-renders both charts and the panel whenever the already-fetched
store **or** any of confidence/units/PnL-basis/hide-degraded/show-ES changes — satisfying FR-010
("instant, no new request") without ever recomputing a financial figure in the browser
(Constitution Principle I).

## Technical Context

**Language/Version**: Python 3.11+ (existing project)
**Primary Dependencies**: Dash, dash-bootstrap-components (`dbc.Tabs`/`dbc.Tab` — already pinned,
no new dependency), Plotly (`go.Figure`, linked x-axes via a shared-x-axis subplot — existing
`plotly>=5`), Pydantic (existing client-side response models), httpx (existing HTTP client)
**Storage**: N/A (this feature adds no persistence; it reads from `portfolio-analysis-service`)
**Testing**: pytest + pytest-bdd (existing `tests/unit/`, `tests/bdd/`)
**Target Platform**: Desktop/tablet browsers via the existing Dash app
**Project Type**: Web application (Dash UI over `portfolio-analysis-service`)
**Performance Goals**: The account/date/look-back refetch issues up to 6 HTTP calls (1 series + 4
backtest + 1 status); per the UX standard, a loading state must appear within 100ms of the
trigger. Every other control (confidence, units, PnL basis, hide-degraded, show-ES) re-renders
with zero network calls.
**Constraints**: Must not derive new financial facts client-side (Constitution Principle I) — all
VaR/ES/exceedance/backtest-statistic values come from the API exactly as returned; the UI only
selects, filters, negates-for-plotting, and unit-picks (GBP vs already-provided %) already-fetched
values. Must not change `portfolio-analysis-service`.
**Scale/Scope**: 1 existing page extended (`risk.py` + 3 new pure-function modules), 1 models file
extended, 1 client file extended, no new top-level directories.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| I. API-sourced data, no local business logic | PASS. Every VaR/ES/exceedance/backtest-statistic value is read verbatim from the API. The only client-side arithmetic is presentational: negating VaR for the overlay line (a sign flip for charting convention, not a new financial fact — the magnitude is unchanged), and picking which already-returned field (`*_gbp` vs `*_pct`) the units toggle displays. Both mirror feature 025's own precedent (bucketing/coloring are presentational transforms of already-fetched values). |
| II. Layered API architecture | N/A — no `portfolio-analysis-service` change; this feature only adds a client (transport) and pure chart/panel builders (presentation), the same two-layer split `_risk_chart.py`/`_risk_table.py` already use. |
| III. Test-first BDD | PASS. New Gherkin scenarios (one `.feature` file per user story, with a new `test_var_risk_steps.py`) are written before the tab's layout/callbacks; unit tests for the three new pure modules are written before each module. |
| IV. Configuration over hard-coding | PASS. No new environment-specific constants; confidence levels and look-backs are discovered from `GET /v1/risk/var/methods` (FR-002/FR-003), not hard-coded. The small set of fixed UI colors (exceedance red, ES dashed style) are named constants in the relevant pure module, consistent with 025's `std_dev_bands` color constants. |
| V. Standard libraries / SOLID / static analysis | PASS. Uses Plotly's own shared-axis subplot support for the linked chart rather than hand-rolled synchronization; `dbc.Tabs` is the standard dash-bootstrap-components tab control. `ruff` + `mypy --strict` must stay clean. |
| UX standards | PASS. Shared account/date/shortcut controls are untouched (FR-001); the "instant" controls' re-render is the UX standard's loading-feedback requirement made moot for those controls (no network call to wait for); the account/date/look-back refetch still shows a loading state within 100ms, matching every other page's `dcc.Loading`/`running=[...]` pattern. Empty/stale-data states (FR-013/FR-014) are the explicit "explain, don't just fail silently" requirement this constitution calls out. |

No violations, so the Complexity Tracking table is not needed.

**Post-design re-check (after Phase 1)**: data-model.md and the UI contract introduce no further
deviations — the four-backtest-call design is a performance/correctness consequence of the
server's own parameterization, not a constitution concern. All gates still pass.

## Project Structure

### Documentation (this feature)

```text
specs/026-var-risk-view/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── ui-contract.md   # Phase 1 output (consumes 012/013's existing API contracts verbatim)
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks (not this command)
```

### Source Code (repository root: `portfolio-browser/`)

```text
src/
├── models/
│   └── portfolio_analysis.py        # add VarMethodLookback, VarMethodsResponse,
│                                     #   ConfidenceLevelEstimate, VarSeriesEntry,
│                                     #   VarSeriesResponse, RollingExceptionPoint,
│                                     #   BacktestConfidenceResult, VarBacktestResponse,
│                                     #   VarStatusSummary (subset of feature 012's VarStatus:
│                                     #   computed_range, missing_dates, links only)
├── services/
│   └── portfolio_analysis_client.py # add get_var_series(), get_var_backtest(..., pnl_basis,
│                                     #   min_quality), get_var_methods(), get_var_status()
│                                     #   to the Protocol + Http implementation
└── pages/
    ├── risk.py                      # extended: dbc.Tabs wrapping the existing histogram
    │                                 #   content as Tab 1 and the new VaR content as Tab 2;
    │                                 #   new Stores + two new callback groups (fetch, render)
    ├── _var_controls.py             # new: pure builder for the VaR tab's own controls block
    │                                 #   (confidence multi-select, look-back select, units/
    │                                 #   PnL-basis/hide-degraded/show-ES toggles), populated
    │                                 #   from a VarMethodsResponse
    ├── _var_chart.py                # new: pure builder — (series entries, selected confidence
    │                                 #   levels, units, pnl_basis, hide_degraded, show_es) ->
    │                                 #   (main go.Figure, linked market-value go.Figure)
    └── _var_backtest_panel.py       # new: pure builder — (backtest result for the selected
                                      #   pnl_basis/min_quality pair, selected confidence
                                      #   levels) -> html.Div panel content

tests/
├── bdd/features/
│   ├── var_risk_tab_shell.feature        # Foundational (tab exists, shares controls)
│   ├── var_risk_chart.feature            # User Story 1
│   ├── var_risk_backtest_panel.feature   # User Story 2
│   ├── var_risk_instant_controls.feature # User Story 3
│   ├── var_risk_refetch_controls.feature # User Story 4
│   ├── var_risk_empty_and_stale.feature  # User Story 5
│   └── var_risk_hide_degraded.feature    # User Story 6
├── bdd/steps/
│   └── test_var_risk_steps.py            # new steps file (risk.py's VaR tab is a large
│                                          #   enough surface to warrant its own file rather
│                                          #   than extending test_risk_steps.py)
└── unit/
    ├── test_var_risk_page.py             # new: plain-function tests for the two new
    │                                      #   callbacks (_fetch_var_methods, _fetch_var_data)
    │                                      #   and the empty/stale branching logic, mirroring
    │                                      #   test_risk_page.py's existing pattern
    ├── test_var_controls.py
    ├── test_var_chart.py
    └── test_var_backtest_panel.py
```

**Structure Decision**: Existing single Dash project. The VaR tab is additive to the existing
`/risk` route (no new `dash.register_page`) and follows the same file-per-concern split feature
024 established (`risk.py` for layout/callbacks, one pure-function module per rendered output) —
scaled to three pure modules here because this tab renders three distinct outputs (two charts, one
panel) instead of 024's two.

## Design Notes

See research.md for the full rationale; summary:

- **Two-callback split** (research.md #1): a fetch callback (`Input`s: account, from-date,
  to-date, look-back) writes one combined payload — series, the 4-way backtest cross-product, and
  status — into `dcc.Store(id="risk-var-store")`. A render callback (`Input`s: the store, plus
  every "instant" control) is the only thing that touches the chart/panel outputs, and it performs
  no I/O.
- **Backtest fetched four times per refetch, not once** (research.md #1): `pnl_basis` and
  `min_quality` are server-side parameters that change the *computed* Kupiec/Christoffersen/zone
  values, not just their display — Principle I forbids approximating that client-side, so both
  states of both toggles are pre-fetched. `confidence` is never passed to either endpoint (always
  omitted), since omitting it already returns every configured level in one response (013's own
  default-to-all behaviour), so the confidence multi-select needs no analogous multiplication.
- **Methods fetched once per page mount, not per account** (research.md #2): the available
  look-backs/confidence levels are account-independent configuration, so `GET /v1/risk/var/methods`
  is fetched by the existing mount-trigger pattern, mirroring how `risk-accounts-store` is
  populated once per mount, not per render.
- **Linked chart** (research.md #3): implemented as a single Plotly figure with two subplots
  sharing an x-axis (`make_subplots(rows=2, shared_xaxes=True)`), not two separately-synchronized
  `dcc.Graph`s — Plotly's own shared-axis zoom/pan keeps them in lock-step with no custom
  callback wiring.
- **Degraded-date hiding** (research.md #4): for the chart, a client-side filter of the
  already-fetched series list (presentational, not a calculation). For the backtest panel, it
  selects which of the two already-fetched `min_quality` results to display — never a
  recomputation.

## Risks

- Four backtest calls per refetch is more outbound traffic than any existing page issues for one
  render; `portfolio-analysis-service`'s own SC-004 budget (<2s per call) means a worst case of
  four sequential 2s calls. Tasks should issue them concurrently (e.g. a thread pool) rather than
  sequentially, to keep the combined refetch within the UX standard's spirit even though the
  100ms figure is specifically about *feedback*, not total completion time.
- `dbc.Tabs` is new to this codebase; BDD scenarios must assert the shared controls (account/date/
  shortcuts) are the *same* DOM elements across both tabs (FR-001), not duplicated per tab, to
  catch an accidental copy-into-each-tab implementation.
- The methods endpoint's confidence levels are basis points (`9500`/`9750`/`9900`); the UI's
  multi-select must format/parse these as the percentages (`95%`/`97.5%`/`99%`) the spec's own
  language uses, consistently with how the series/backtest query parameters are documented in
  013's own contract (percentages in, basis points internally).
