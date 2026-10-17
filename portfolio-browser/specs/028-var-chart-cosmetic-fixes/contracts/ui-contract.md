# UI Contract: Value at Risk Chart Cosmetic Fixes

This feature consumes the same external contracts as 024/025/026/027, verbatim — no
backend contract changes. It amends only the internal shape of
`_var_chart.py::build_figures()`'s returned figure and
`_var_backtest_panel.py::build_panel()`'s returned component; neither function's
*signature* changes, and `risk.py`'s callback graph is unaffected (it already renders
both functions' output verbatim).

## `_var_chart.py::build_figures(...)` (signature unchanged)

- **Legend**: the returned `go.Figure`'s `layout.legend` is set to
  `{"orientation": "h", "x": 0.5, "xanchor": "center", "y": <below both subplot rows>}`
  (previously unset, defaulting to Plotly's in-plot-area placement).
- **Subplot captions**: `make_subplots(...)` gains `subplot_titles=[<main chart caption>,
  <linked chart caption>]`. `shared_xaxes=True` and `row_heights=[0.7, 0.3]` are unchanged
  — the two rows remain one figure with a linked x-axis, not two separate charts.
- **Realised PnL trace**: the `go.Bar` trace (`name="Realised PnL"`) is only added to the
  figure when `units == "gbp"`. When `units == "pct"`, no bar trace is added at all (not
  added-then-hidden — simply omitted), and the VaR/ES overlay lines and the linked
  market-value subplot are built exactly as before.

## `_var_backtest_panel.py::build_panel(...)` (signature unchanged)

- Previously returned an `html.Div` containing one `html.H6` + `dash_table.DataTable` pair
  per selected confidence level (`_level_block`). Now returns an `html.Div` containing a
  **single** `dash_table.DataTable`:
  - `columns`: `[{"name": "statistic", "id": "statistic"}, ...]` followed by one column
    per currently selected confidence level (`id` e.g. `f"level_{confidence_bp}"` — not
    `pct_`, to avoid confusion with this feature's unrelated `units == "pct"` chart-display
    concept, per `/speckit-analyze` finding F3 — `name` the formatted confidence label e.g.
    `"95%"`), in `selected_confidence_bp`'s own order.
  - `data`: six rows (`Exceptions`, `Kupiec p-value`, `Conditional coverage p-value`,
    `Zone`, `Mean VaR`, `VaR stability`), each a dict with `"statistic"` plus one key per
    confidence-level column, populated from that level's already-selected
    `(pnl_basis, min_quality)` backtest result exactly as `_level_block` read it before.
  - `style_cell`/`style_header`: unchanged — still `STYLE_CELL`/`STYLE_HEADER` from this
    same module (027's single-source-of-truth with `risk.py`'s own histogram table is
    unaffected).

## Caller (`risk.py`) — unchanged

`_render_var_view` continues to call `build_var_figures(...)` and
`build_var_backtest_panel(...)` with the same arguments as today and render their results
into `risk-var-chart-container`/`risk-var-backtest-panel` verbatim. No new `Input`,
`Output`, `State`, or component id is introduced anywhere in `risk.py`.

## Empty / error states — unchanged

26/027's empty-state and error-state behavior (no VaR data, fetch failure, unsupported
range code) is untouched; this feature only changes what the chart/panel look like once
there is data to show.
