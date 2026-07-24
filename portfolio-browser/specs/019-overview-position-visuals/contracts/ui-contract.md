# UI Contract: Overview Position Visualizations

No new external API contract — this feature is a consumer of
`GET /v1/accounts/{account_name}/position`, already documented in
`specs/018-positions-page/contracts/portfolio-analysis-api.md` (verified
against the same `005-position-timeseries-api` OpenAPI source). This file
covers only the new UI structure and callback.

## New stable component element IDs (Overview page body)

Rendered by `src/pages/overview.py`, in a new row below the existing
`overview-chart-loading`/`overview-chart-container`:

| Element ID | Component | Purpose |
|---|---|---|
| `overview-position-widgets-row` | `dbc.Row` | Wraps both new halves; `dbc.Col(xs=12, lg=6)` on each child controls the responsive stacking (research.md #5) |
| `overview-pie-loading` | `dcc.Loading` | Wraps the pie container, matching the existing chart's own loading-spinner pattern |
| `overview-pie-container` | `html.Div` | Holds the rendered pie `dcc.Graph` / empty-state / error-state |
| `overview-winners-losers-loading` | `dcc.Loading` | Wraps the table container |
| `overview-winners-losers-container` | `html.Div` | Holds the rendered winners/losers table / empty-state / error-state |

## Callback contract

| Trigger | Inputs | Output | Behavior |
|---|---|---|---|
| Account or "To" date changes | `app-parameters-account.value`, `app-parameters-to-date.date` | `overview-pie-container.children`, `overview-winners-losers-container.children` | Fetches `get_position_timeseries(account_name, positions=[], attributes=["market_value","pnl","book_cost"], start=to_date, end=to_date)` once; builds the pie chart and the winners/losers table from the same response (FR-004, FR-009, SC-002); guard clauses for a data-less account/empty response (both containers → empty-state) and any client error (both containers → error-state, FR-014). Deliberately does **not** list `app-parameters-from-date.date` or any `{"type": "overview-attribute-toggle", ...}` prop as an Input (FR-010) — unaffected by either. |

## Contract guarantees

- The pie chart and the winners/losers table are always rendered by the
  same callback from the same single fetch — there is no code path where
  one refreshes without the other (SC-002), mirroring `018`'s own
  chart+table atomicity guarantee applied here to a point-in-time snapshot.
- This callback is entirely independent of `_render_chart` (the existing
  performance-chart callback) — no shared `Output`, no shared `running=`
  target (research.md #6), so the two can run concurrently without any
  Dash duplicate-`Output` conflict.
- Because `app-parameters-account`/`app-parameters-to-date` are the same
  component IDs the existing chart already reads, no new parameters-bar
  changes are needed in `src/layout/shell.py` — this feature only adds to
  `overview.py`'s own page body.
