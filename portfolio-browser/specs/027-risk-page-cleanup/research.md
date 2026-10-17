# Research: Risk Page Cosmetic Cleanup

## 1. Single page vs. tabs

**Decision**: Replace the `dbc.Tabs`/`dbc.Tab` wrapper in `risk.py`'s `layout` with a plain
`html.Div` stack: histogram chart + table row first, then the VaR controls/chart/backtest-panel
block below it, both always mounted.

**Rationale**: `dbc.Tabs` only toggles which child is *visible*; both children are already in the
DOM and already fetch independently (histogram via `_render_histogram_and_table`, VaR via
`_fetch_var_methods`/`_fetch_var_data`/`_render_var_view`). Removing the `dbc.Tabs` wrapper and
stacking both `children` blocks vertically requires no change to any callback's `Output` targets
— `risk-chart-container`, `risk-table-container`, `risk-var-controls-container`,
`risk-var-chart-container`, and `risk-var-backtest-panel` all keep their existing ids.

**Alternatives considered**: Keep tabs but reorder them (rejected — user explicitly asked for the
tab control itself to be removed, not reordered) and collapsible accordion sections (rejected —
spec requires the histogram "first" and VaR "below", i.e. always visible via scroll, not
disclosure-gated).

## 2. Unit-matching the statistics table to the chart

**Decision**: In `_risk_table.py::build_rows`, format `mean`, `median`, `minimum`, `maximum`, and
`std_dev` (all currently raw basis-point floats per `HistogramStatistics`) as
`f"{value / 100:.2f}%"`, matching the exact `center_bp / 100` conversion `_risk_chart.py` already
applies for its x-axis and vline positions. Leave `count`, `skewness`, and `kurtosis` unformatted
(they are not return values).

**Rationale**: `_risk_chart.py` already performs this exact `/100` conversion for the chart; reusing
the identical divisor in the table guarantees the two displays can never drift apart again. A
small shared formatting helper (e.g. `_format_pct_bp(value_bp: float) -> str`) should live beside
`build_rows` so both call sites that need it (table rows; any future export) share one
implementation rather than duplicating the `/100` literal.

**Alternatives considered**: Converting the API response itself to percent before it reaches the
table (rejected — out of scope per Constitution Principle I/II; the API's basis-point contract is
unchanged, only this page's display formatting changes) and showing both bp and % side-by-side
(rejected — spec FR-003 asks for one unambiguous percent value, not two numbers to reconcile).

## 3. Median reference line removal

**Decision**: Delete the second `fig.add_vline()` call (median) in `_risk_chart.py::build_figure`
lines ~135-141; keep the first (mean) call unchanged, including its existing dashed styling and
"Mean" annotation.

**Rationale**: Smallest possible diff that satisfies FR-005; no other chart behavior (bucket
coloring, x-axis ticks) depends on the median vline's presence.

**Alternatives considered**: Keeping both lines but restyling them to be more distinguishable
(rejected — spec explicitly asks for the median line's removal, not better styling, since the bar
shape already conveys the median visually).

## 4. Confirming axis-scale consistency

**Decision**: No chart/bucketing code change is needed — `bucket_histogram()` already buckets by
absolute return value (10bp-wide buckets aligned to absolute multiples of 10bp), and
`build_figure()` converts both bucket centers and the mean vline through the same `/100` divisor.
The action here is to add a unit test asserting this invariant explicitly (e.g. a bucket whose
raw center is `-150` bp must render at x=`-1.5`, independent of whatever the mean/median happen to
be for that dataset), so a future change cannot silently reintroduce a mean-relative axis without
a test failing.

**Rationale**: The user's question ("are the -1%/-2%/-3% marks absolute, or offsets from the
mean?") is already answered "absolute" by the current code, per the Explore agent's findings
confirmed against `_risk_chart.py::bucket_histogram` (lines 55-74) and `build_figure` (lines
97-99). Spec FR-006 asks for this to be guaranteed, not just true today — a regression test is the
correct way to guarantee a UI *behavior* without adding new product logic.

**Alternatives considered**: Adding a visible axis-scale label/caption (rejected — spec's intent is
correctness/consistency, not additional on-screen text; FR-006 is satisfied by the existing
absolute-value behavior plus a regression test).

## 5. Unifying the range controls (1Y/3Y/5Y histogram shortcuts vs. 1y/2y/5y VaR look-back)

**Decision** (confirmed with user — see spec Assumptions and the clarifying question answered
during planning): present the union of both option sets — 1Y, 2Y, 3Y, 5Y, 10Y, ALL — as a single
shared control. Concretely:

- Add one new, Risk-page-local shortcut button, "2Y", alongside the existing shared
  1Y/3Y/5Y/10Y/ALL shortcut buttons rendered by `src/components/date_range_controls.py`
  (`build_account_date_controls`). Its date math reuses the existing generic `_years_before(today,
  2)` helper already used for 1Y/3Y/5Y/10Y — purely additive, no change to any other page using
  that shared component (Overview/Positions/Performance keep their existing five-button layout
  untouched). Its code is the lowercase string `"2y"`, matching the server's own lowercase
  look-back code convention (`"1y"`/`"2y"`/`"5y"`, confirmed against
  `tests/unit/test_var_controls.py`'s `MethodLookback` fixtures) rather than the shared
  component's own uppercase-labelled-but-lowercase-valued `SHORTCUT_*` constants' casing — both
  already agree, but this is worth a direct assertion in `test_date_range_controls.py` so the two
  conventions cannot silently drift apart.
- Introduce a page-local `dcc.Store` (`risk-range-code-store`) on the Risk page holding the
  shortcut code that the *current* from/to dates correspond to (`"1y"`, `"2y"`, `"3y"`, `"5y"`,
  `"10y"`, `"all"`, or `None` for a hand-edited/custom range, including the account's default
  full-history view). **Correction from the original design** (flagged by `/speckit-analyze`,
  finding F2): rather than having two separate callbacks race to write this store — one on a
  shortcut click, one reacting to date-field changes to detect "manual" edits, with no reliable
  way for the second callback to tell *why* the date fields changed — this store is instead
  **derived**, by one new callback, `_derive_range_code`, from whichever of the two date fields'
  *current values* happen to match a shortcut's own computed date range for the selected account:

  ```text
  _derive_range_code(from_date, to_date; State: account, accounts_data) ->
      for each code in (1y, 2y, 3y, 5y, 10y, all):
          if _shortcut_from_date(code, account, today) == from_date
             and _last_business_day(today) == to_date:
              return code
      return None
  ```

  `Input`s are the two shared date-picker fields only (`app-parameters-from-date`/`to-date`); it
  fires identically regardless of whether those fields changed via a shortcut click, the
  account-switch default, or a direct hand-edit, and always recomputes the correct answer from
  current state — there is nothing to race against, because only one callback ever writes this
  store. `_apply_date_range_shortcut` itself needs **no** new `Output` for this store; it keeps
  only its existing from/to date Outputs (plus the new 2Y button's `Input`).
- `_fetch_var_data`'s `Input("risk-var-lookback", "value")` is replaced with
  `Input("risk-range-code-store", "data")`, plus a new `State("risk-var-methods-store", "data")`
  to check the code against the server-reported list. When the code is one of those look-back
  codes (`"1y"`, `"2y"`, `"5y"` today, but checked against the fetched list, not hard-coded), it
  is passed straight through as the `lookback` argument, preserving today's
  `get_var_series`/`get_var_backtest` calls unchanged. When it is `"3y"`, `"10y"`, `"all"`, or
  `None` (custom range, or the account's default full-history view before any shortcut is
  clicked), **`_fetch_var_data` still calls `get_var_status` (account-level, independent of the
  look-back) but skips the `get_var_series`/`get_var_backtest` calls entirely**, and returns a
  well-formed payload with an *empty* series (`{"series": []}`) and empty backtest dict rather
  than `None`. **Correction from the original design** (finding F1): the original plan had this
  callback `raise PreventUpdate` while *also* trying to clear the store via an Output — those are
  mutually exclusive in Dash (a raised `PreventUpdate` discards every Output of that invocation),
  and even if the store were cleared to `None`, `_render_var_view`'s existing
  `if not store_data: raise PreventUpdate` guard would then leave whatever was previously
  rendered on screen (stale data), not the empty state. Returning a non-`None`, empty-series
  payload instead means `_render_var_view`'s *already-existing* `if not series:` branch fires
  exactly as it does today for a genuinely empty API response, rendering "No Value at Risk data is
  available for the selected range" (since `status.computed_range` will typically not be `None`
  for an account with any completed calculation) with zero changes to `_render_var_view` itself.
  The histogram section continues to render normally for that same range throughout.
- `_var_controls.py::build_controls()` drops the "Look-back" `dbc.Label`/`dbc.Select` entirely
  (and the now-unused `headline` lookup); it still receives `methods` (for the confidence-level
  checklist) and gains no new responsibility — the methods→code validation lives in `risk.py`'s
  callback, not in this pure builder, consistent with its existing separation of concerns.

**Rationale**: This satisfies "one set of controls, no overlap" (every option, including the
VaR-only "2Y", is selectable from exactly one visible control) without inventing a fictitious
date range for the histogram or silently dropping the VaR server's own headline look-back value,
and without hard-coding VaR's valid codes (Constitution Principle IV) — the mapping is checked
against the already-fetched `/v1/risk/var/methods` response at render time.

**Alternatives considered**: Dropping 2Y (rejected by user — loses the VaR server's headline
default with no UI path back to it) and dropping 3Y/10Y/ALL (rejected by user — regresses the
histogram's existing range options, which have no dependency on VaR at all).

## 6. Consistent visual style for the two statistics summaries

**Decision**: Rebuild `_var_backtest_panel.py::build_panel`/`_level_block` to render each
confidence level's figures as rows of a `dash_table.DataTable` (same `style_cell`/`style_header`
pattern as `risk-statistics-table` in `risk.py`), rather than stacked `html.H6`/`html.P` prose.
Where today's panel shows one block per confidence level, each becomes its own labelled
`DataTable` instance (or one table with a "confidence level" column, consolidated into a single
grid) — the exact layout is an implementation detail for Phase 1/implementation, not a new data
requirement.

**Rationale**: Reusing the same Dash component type and the same `style_cell`/`style_header`
dictionary as the histogram's own table is the smallest change that makes the two "look like part
of the same page" (spec FR-010/SC-005), and avoids introducing a third, bespoke styling approach.

**Alternatives considered**: Keeping the prose layout but adding borders/typography CSS to
approximate a table look (rejected — more fragile/harder to keep in sync than reusing the existing
`dash_table.DataTable` component directly) and building a shared custom "stat block" component
used by both (rejected as unnecessary scope for a cosmetic fix — Constitution Principle V favors
the standard library component already in use over a new bespoke abstraction).
