# Phase 1 Data Model: Risk Page Cosmetic Cleanup

No new API entities. This feature changes only presentation-layer formatting and page-local UI
state over data already modeled by `portfolio-analysis-service` responses (see
`specs/024-risk-return-histogram-page/data-model.md` for `HistogramStatistics` and
`specs/026-var-risk-view/data-model.md` for the VaR series/backtest/methods entities, both
unchanged by this feature).

## Shared Range Selection (page-local UI state, new)

Replaces the Value at Risk section's own "Look-back" selection as the single control governing
both the histogram's displayed date window and (where supported) the VaR section's estimation
look-back.

| Field | Type | Notes |
|---|---|---|
| `code` | `"1y" \| "2y" \| "3y" \| "5y" \| "10y" \| "all" \| None` | The active shortcut code, or `None` when the from/to dates were set by hand rather than a shortcut button (including the account's initial default full-history view) |

Stored in a new `dcc.Store(id="risk-range-code-store")`. Written whenever a shortcut button
(including the new "2Y" button) is clicked; cleared to `None` on manual date-picker edits and on
account switch (mirroring the existing default-to-full-history behavior).

**Derivation rule** (used by `_fetch_var_data`, replacing its old `risk-var-lookback` Input):
`code` is passed to the VaR endpoints as the `lookback` parameter only if it appears in the
already-fetched `risk-var-methods-store`'s list of server-reported look-back codes; otherwise the
VaR section renders its existing empty state and no VaR fetch is made for that range.

## HistogramStatistics table row (presentation change only)

Existing entity (`specs/024-risk-return-histogram-page/data-model.md`), unchanged in the API
model. Only the **rendered string** for `mean`, `median`, `minimum`, `maximum`, and `std_dev`
changes: previously the raw basis-point number as a bare string (e.g. `"808"`), now
`f"{value / 100:.2f}%"` (e.g. `"8.08%"`) — the identical conversion `_risk_chart.py` already
applies for the chart's x-axis and mean reference line. `count`, `skewness`, and `kurtosis`
rows are unchanged (no unit).

## VaR backtest panel row (presentation change only)

Existing figures from `specs/026-var-risk-view/data-model.md`'s backtest entity (exceptions
observed/expected, Kupiec/conditional-coverage p-values, zone, mean VaR, VaR stability) — no
new or removed fields. Only the **container component** changes, from stacked
`html.H6`/`html.P` blocks to a `dash_table.DataTable`-style grid matching the histogram's
`risk-statistics-table`.
