# UI Contract: Value at Risk View (Risk Page)

This feature consumes four existing external contracts verbatim — no new backend contract is
introduced:

- `portfolio-analysis-service/specs/013-var-series-backtest-api/contracts/openapi.yaml`
  — `GET /v1/accounts/{account_name}/risk/var`, `GET .../risk/var/backtest`,
  `GET /v1/risk/var/methods`
- `portfolio-analysis-service/specs/012-var-calculation-runs/contracts/openapi.yaml`
  — `GET /v1/accounts/{account_name}/risk/var/status` (only `computed_range`/`missing_dates`/
  `_links` are consumed; see data-model.md's `VarStatusSummary`)

This document specifies the Dash layout and callback graph, at the same level of detail
024/025's own `ui-contract.md` files provide.

## Route

Still `/risk` (no new route). The existing `dash.register_page` call is unchanged.

## Layout

```
dbc.Tabs(id="risk-tabs", [
    dbc.Tab(label="Return Histogram", tab_id="risk-tab-histogram", children=[
        <<the existing 024/025 histogram+table row, unchanged>>
    ]),
    dbc.Tab(label="Value at Risk", tab_id="risk-tab-var", children=[
        dcc.Store(id="risk-var-store"),
        dcc.Store(id="risk-var-methods-store"),
        html.Div(id="risk-var-stale-banner"),                 # FR-014
        _var_controls.build_controls_placeholder(),           # populated once methods load
        dcc.Loading(html.Div(id="risk-var-chart-container")), # FR-004-FR-008, or empty/error state
        dbc.Row([
            dbc.Col(..., width=9),   # chart container above
            dbc.Col(dcc.Loading(html.Div(id="risk-var-backtest-panel")), width=3),  # FR-009
        ]),
    ]),
])
```

The account selector, date range and shortcut buttons are **not** inside either `dbc.Tab` — they
remain in `shell.py`'s shared parameters bar above the tabs, exactly as today (FR-001).
`risk-mount-trigger` and `risk-accounts-store` are also unchanged and shared by both tabs.

## Callback graph (additions only — the existing six 024/025 callbacks are unchanged)

1. **`_fetch_var_methods`** — `Input("risk-mount-trigger", "n_intervals")` →
   `client.get_var_methods()` → writes `risk-var-methods-store.data`, and (via a second Output)
   populates the confidence multi-select's `options` and default `value` (every level) and the
   look-back select's `options` (default `"2y"`, or whichever `is_headline` the response marks).
   Mirrors `_fetch_accounts`, but account-independent (research.md #2).

2. **`_fetch_var_data`** — `Input("app-parameters-account", "value")`,
   `Input("app-parameters-from-date", "date")`, `Input("app-parameters-to-date", "date")`,
   `Input("risk-var-lookback", "value")` → concurrently (research.md #6) calls
   `get_var_series(...)` once and `get_var_backtest(..., pnl_basis, min_quality)` for all four
   combinations, plus `get_var_status(...)`; writes the combined payload (data-model.md) to
   `risk-var-store.data`, or `{"fetch_error": ...}` on any failure. `running=[...]` disables the
   shared account/date/shortcut controls **and** the look-back select during the fetch.

3. **`_render_var_view`** — `Input("risk-var-store", "data")`,
   `Input("risk-var-confidence", "value")` (multi-select), `Input("risk-var-units", "value")`,
   `Input("risk-var-pnl-basis", "value")`, `Input("risk-var-hide-degraded", "value")`,
   `Input("risk-var-show-es", "value")` → **no I/O**. Branches on the store's `fetch_error` /
   `series.series == []` (empty state, FR-013) vs. populated data: calls
   `_var_chart.build_figures(...)` for the chart `dcc.Graph` and
   `_var_backtest_panel.build_panel(...)` for the side panel, selecting the one of four fetched
   backtest results matching the current `pnl_basis`/hide-degraded state (research.md #1, #4).
   This is the callback FR-010/FR-012 require to make zero network calls.

4. **`_render_stale_banner`** — `Input("risk-var-store", "data")` → reads `status.missing_dates`;
   renders the banner `html.Div` when `> 0`, else an empty `html.Div` (FR-014). Separate from
   callback 3 because the banner's content never depends on the "instant" controls.

## Empty / error states (FR-013)

When `risk-var-store.data.fetch_error` is set, or `series.series == []` **and**
`status.computed_range is None`: the chart container and backtest panel are replaced by one
centered `_empty_state(message)` (same helper `risk.py` already defines), whose message names the
`status.links` (or a fixed instructional string if that account has genuinely nothing — e.g. "Run
a VaR calculation for this account via the portfolio-analysis-service API, then reload this
page.") rather than a button, per spec.md's Assumptions (no in-browser trigger in this feature).

When `series.series == []` but `status.computed_range is not None` (a date range with no overlap,
rather than "never computed"): the chart renders empty axes with its own narrower
"No data for the selected range" message, distinct from the account-level empty state.
