# UI Contract: Risk Page Cosmetic Cleanup

This feature consumes the same external contracts as 024/025/026, verbatim — no backend contract
changes. It supersedes 026's own `ui-contract.md` layout section (tabbed structure) and amends
024/025/026's callback graphs as described below.

## Route

Still `/risk`. Unchanged.

## Layout (replaces 026's tabbed layout)

```
html.Div([
    dcc.Interval(id="risk-mount-trigger", ...),
    dcc.Store(id="risk-accounts-store"),
    dcc.Store(id="risk-var-store"),
    dcc.Store(id="risk-var-methods-store"),
    dcc.Store(id="risk-var-confidence-last-nonempty"),
    dcc.Store(id="risk-range-code-store"),            # NEW — replaces risk-var-lookback's role

    # -- Return Histogram section (first) --
    dbc.Row([
        dbc.Col(dcc.Loading(html.Div(id="risk-chart-container")), width=7),
        dbc.Col(dcc.Loading(html.Div(id="risk-table-container")), width=5),
    ]),

    # -- Value at Risk section (second) --
    html.Div(id="risk-var-stale-banner"),
    html.Div(id="risk-var-controls-container"),       # no Look-back select (see below)
    dbc.Row([
        dbc.Col(dcc.Loading(html.Div(id="risk-var-chart-container")), width=9),
        dbc.Col(dcc.Loading(html.Div(id="risk-var-backtest-panel")), width=3),  # now a DataTable
    ]),
], className="p-3")
```

`dbc.Tabs`/`dbc.Tab` and `risk-tabs` are removed entirely. The account selector, date range, and
shortcut buttons remain in `shell.py`'s shared parameters bar above both sections, now joined by
one additional page-local "2Y" shortcut button rendered by `risk.py` itself (not by the shared
`build_account_date_controls`, which stays five-button for every other page).

## Callback graph changes

Unchanged from 024/025/026: `_fetch_accounts`, `_apply_default_account`,
`_sync_date_range_to_selected_account`, `_sync_from_date_max_to_to_date`,
`_render_histogram_and_table`, `_validate_date_range`, `_fetch_var_methods`,
`_track_last_nonempty_confidence`, `_guard_confidence_selection`, `_render_stale_banner`.

1. **`_apply_date_range_shortcut`** — gains a sixth `Input("risk-shortcut-2y", "n_clicks")`
   (new page-local button id) alongside the existing five shared-shortcut `n_clicks` Inputs, and
   maps it to the `"2y"` code like every other shortcut. No new `Output` is needed on this
   callback for the range-code store (see point 2) — it keeps only its existing from/to date
   Outputs.

2. **New callback `_derive_range_code`** —
   `Input("app-parameters-from-date", "date")`, `Input("app-parameters-to-date", "date")`,
   `State("app-parameters-account", "value")`, `State("risk-accounts-store", "data")` →
   `Output("risk-range-code-store", "data")`. Recomputes, from the *current* from/to values,
   which (if any) of the six shortcut codes (`"1y"`/`"2y"`/`"3y"`/`"5y"`/`"10y"`/`"all"`) the
   selected account's own `_shortcut_from_date`/`_last_business_day` would produce that exact
   range for `today`; returns the matching code, or `None` if no shortcut matches (a hand-edited
   custom range, or the account's default full-history view). This is a pure derivation from
   current state with a single writer, so it is **not** vulnerable to callback-ordering races
   between a shortcut click and a manual edit (the original design's finding F2 from
   `/speckit-analyze`) — see research.md #5.

3. **`_fetch_var_data`** — `Input("risk-var-lookback", "value")` is **removed**; replaced by
   `Input("risk-range-code-store", "data")` plus a new
   `State("risk-var-methods-store", "data")`. New logic: resolve whether the store's code
   appears in the already-fetched `risk-var-methods-store`'s `lookbacks[].code` list.
   - **Supported** (`"1y"`/`"2y"`/`"5y"` today): unchanged from before — fetches series + four
     backtest combinations + status concurrently, passing the resolved code as `lookback`.
   - **Unsupported** (`"3y"`/`"10y"`/`"all"`, or `None`): still calls `get_var_status` (the
     account-level status call does not depend on `lookback`), but skips the series/backtest
     calls, and returns `{"account_name": ..., "lookback_code": None, "series": {"series": []},
     "backtest": {}, "status": status_data, "fetch_error": None}` — a well-formed, non-`None`
     store value. This corrects the original design (finding F1 from `/speckit-analyze`), which
     tried to both `raise PreventUpdate` and set an `Output` in the same callback invocation
     (mutually exclusive in Dash) and, even if that contradiction were resolved, would have left
     `_render_var_view` showing stale data rather than its empty state (see point 4 and
     research.md #5 for why this shape makes `_render_var_view` need no change at all).

4. **`_render_var_view`** — fully unchanged (no signature or logic change). Its existing
   "No Value at Risk data is available for the selected range" empty-state branch (today reached
   only when the API itself returns an empty series) is now also reached whenever
   `_fetch_var_data` returns its empty-series payload for an unsupported range code (point 3),
   since that payload's `series.series == []` just like a genuinely empty API response — no new
   branch needed.

5. **`_render_chart_and_table`** (and `build_rows`) — no `Input`/`Output` change; `build_rows`'s
   *returned string values* for `mean`/`median`/`minimum`/`maximum`/`std_dev` change from a bare
   number to a percent-formatted string (see data-model.md).

6. **`_var_controls.build_controls`** — no longer renders the `risk-var-lookback` `dbc.Select`
   or its `dbc.Label`; still renders confidence/units/PnL-basis/hide-degraded/show-ES controls
   unchanged. `methods.lookbacks` is still read, but by `_fetch_var_data`'s validation logic in
   `risk.py`, not by this builder.

7. **`_var_backtest_panel.build_panel`** — same inputs (backtest payload, selected confidence
   levels, pnl basis), different output shape: a `dash_table.DataTable` (or one per confidence
   level) using the same `style_cell`/`style_header` dictionaries as `risk-statistics-table`,
   instead of `html.H6`/`html.P` blocks.

8. **`_risk_chart.build_figure`** — drops the median `fig.add_vline()` call; the mean
   `fig.add_vline()` call and all bucket-coloring logic are unchanged.

## Empty / error states

Unchanged from 026, with one addition: the Value at Risk section's existing "No Value at Risk
data is available for the selected range" empty state is now also the correct (and expected, not
erroneous) outcome when the shared range control is set to `"3y"`, `"10y"`, `"all"`, or a
hand-edited custom range — none of which have a corresponding server-reported VaR look-back. The
Return Histogram section is unaffected and continues to render for any of those same ranges.
