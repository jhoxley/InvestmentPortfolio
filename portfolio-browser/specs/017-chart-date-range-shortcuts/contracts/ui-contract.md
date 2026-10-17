# UI Contract: Date Range Shortcut Buttons on Overview

Extends `specs/016-link-real-portfolio/contracts/ui-contract.md`. No
external API contract changes — this feature calls no new
`portfolio-analysis-service` endpoint and sends no new request shape; see
that spec's `contracts/portfolio-analysis-api.md` for the (unchanged)
consumed API contract.

## New stable component element IDs (Overview parameters bar only)

Rendered by `src/layout/shell.py`'s `_build_overview_parameters_bar()`
(Overview route only, same scoping as `app-parameters-from-date`/`to-date`):

| Element ID | Component | Purpose |
|---|---|---|
| `overview-shortcut-ytd` | `dbc.Button` | "YtD" shortcut (FR-002) |
| `overview-shortcut-1y` | `dbc.Button` | "1Y" shortcut (FR-003) |
| `overview-shortcut-3y` | `dbc.Button` | "3Y" shortcut (FR-004) |
| `overview-shortcut-5y` | `dbc.Button` | "5Y" shortcut (FR-005) |
| `overview-shortcut-all` | `dbc.Button` | "All" shortcut (FR-006) |

## Callback contract (additions to 016's table)

| Trigger | Inputs | State | Output | Behavior |
|---|---|---|---|---|
| Shortcut button clicked | `n_clicks` on any of the 5 buttons above | `app-parameters-account.value`, `overview-accounts-store.data` | `app-parameters-from-date.date` (`allow_duplicate=True`), `app-parameters-to-date.date` (`allow_duplicate=True`) | Resolves which button fired via `ctx.triggered_id`; computes + clamps `from_date` (FR-008), sets `to_date` to the existing last-business-day default; no-ops (`PreventUpdate`) if no account is selected yet |

## Modified callback (016's `_render_chart`)

`_render_chart`'s signature is unchanged (same Inputs/Outputs) but gains a
`running=` clause:

```text
running=[
    (Output("overview-shortcut-ytd", "disabled"), True, False),
    (Output("overview-shortcut-1y", "disabled"), True, False),
    (Output("overview-shortcut-3y", "disabled"), True, False),
    (Output("overview-shortcut-5y", "disabled"), True, False),
    (Output("overview-shortcut-all", "disabled"), True, False),
]
```

## Contract guarantees

- The five shortcut buttons only ever change `app-parameters-from-date.date`
  and `app-parameters-to-date.date` — they never write to
  `overview-chart-container` directly (see research.md #3); the chart
  update is always mediated by 016's existing `_render_chart`.
- All five buttons carry `disabled=True` for the exact duration of any
  `_render_chart` execution, regardless of what triggered it (FR-013) —
  enforced by a single `running=` clause, not five independently-maintained
  flags that could drift out of sync.
- Because the shortcut buttons live inside
  `_build_overview_parameters_bar()`, they exist only on the Overview route
  — same scoping guarantee 016 already established for
  `app-parameters-from-date`/`to-date`, requiring no new visibility logic.
