# UI Contract: Risk Page

This page consumes an existing external contract
(`portfolio-analysis-service/specs/011-risk-return-histogram/contracts/openapi.yaml`,
`GET /v1/accounts/{account_name}/risk/return-histogram`) verbatim — no new backend contract is
introduced by this feature. This document instead specifies the Dash callback graph, mirroring the
level of detail `specs/020-performance-page-chart/contracts/ui-contract.md` and `performance.py`'s
own module docstring already provide.

## Route

`/risk`, registered via `dash.register_page(__name__, path="/risk", name="Risk")`.

## Layout

```
dcc.Interval(id="risk-mount-trigger", interval=200, max_intervals=1)
dcc.Store(id="risk-accounts-store")
dbc.Row([
    dbc.Col(dcc.Loading(dcc.Graph(id="risk-histogram-chart")), width=7),
    dbc.Col(dcc.Loading(dash_table.DataTable(id="risk-statistics-table")), width=5),
])
```

Parameters bar (rendered by `shell.py`'s `_render_parameters_bar` for pathname `/risk`):
`build_account_date_controls(first_shortcut_label="10Y")` — Account select, From/To date pickers,
and the five shortcut buttons (labelled 10Y/1Y/3Y/5Y/All).

## Callback graph

1. **`_fetch_accounts`** — `Input("risk-mount-trigger", "n_intervals")` →
   `list_accounts()` → populates `risk-accounts-store` and `app-parameters-account.options`.
   Mirrors `performance.py::_fetch_accounts_and_attributes` minus the attributes fetch (this page
   has no toggleable measures).

2. **`_apply_default_account`** — `Input("risk-accounts-store", "data")` +
   page-scope input → selects the alphabetically-first account into
   `app-parameters-account.value`. Identical to every other page's copy.

3. **`_sync_date_range_to_selected_account`** — `Input("app-parameters-account", "value")` +
   page-scope input, `State("risk-accounts-store", "data")` → resets
   `app-parameters-from-date`/`app-parameters-to-date` to the selected account's full recorded
   history. Identical to `performance.py`'s copy.

4. **`_sync_from_date_max_to_to_date`** — `Input("app-parameters-to-date", "date")` →
   keeps the "from" picker's `max_date_allowed` in sync. Identical to every other page's copy.

5. **`_apply_date_range_shortcut`** — five `n_clicks` Inputs (shared shortcut button ids) +
   page-scope input, `State("app-parameters-account", "value")`,
   `State("risk-accounts-store", "data")` → this page's own
   `_SHORTCUT_CODE_BY_BUTTON_ID` maps the first button (labelled "10Y") to the new
   `SHORTCUT_10Y`, and the remaining four to their existing `SHORTCUT_1Y`/`SHORTCUT_3Y`/
   `SHORTCUT_5Y`/`SHORTCUT_ALL` codes unchanged.

6. **`_render_histogram_and_table`** — `Input("app-parameters-account", "value")`,
   `Input("app-parameters-from-date", "date")`, `Input("app-parameters-to-date", "date")` →
   calls `get_return_histogram(account, start, end)`; on success, Outputs both
   `risk-histogram-chart.figure` (via `_risk_chart.build_figure`) and
   `risk-statistics-table` props (via `_risk_table.build_table`); on failure, both outputs switch
   to the shared error-state treatment; on an empty histogram (`count == 0`), both outputs switch
   to the shared empty-state treatment (no chart, no table rendered side by side with nothing in
   it). `running=[...]` disables the account/date/shortcut controls during the fetch, matching
   `_REFRESH_DISABLED_IDS` on every other page.

## Error / empty states

Reuses the same `_empty_state(message)` / `_error_state(message)` `html.Div` helper shape already
defined per-page (e.g. `performance.py`), with page-scoped ids (`risk-empty-state`,
`risk-error-state`) replacing both the chart and the table with a single centered message spanning
the full row width, per spec Edge Cases ("the statistics table is not shown alongside an empty
chart").
