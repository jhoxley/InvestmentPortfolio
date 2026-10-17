# UI Contract: Performance Page

Extends `016-link-real-portfolio`'s, `017-chart-date-range-shortcuts`'s, and
`018-positions-page`'s UI contracts for the shared Account/From/To/shortcut
controls (`src/components/date_range_controls.py` — same component IDs,
mostly the same shortcut/clamp behavior, reused by all three routes; see
research.md #3). Two deliberate behavioral differences from Overview/
Positions are covered by research.md #3/#4, not by this shared extraction:
the first shortcut button is labeled "ITD" (not "YtD") and its underlying
code is `SHORTCUT_ALL` (not `SHORTCUT_YTD`); and the default/account-switch
date range is full history (like Overview), not "YtD" (unlike Positions).
This file covers what's new/Performance-specific.

## New stable component element IDs (Performance parameters bar)

Rendered by `src/layout/shell.py::_build_performance_parameters_bar()`
(Performance route only):

| Element ID | Component | Purpose |
|---|---|---|
| `app-parameters-account` | `dbc.Select` | Reused verbatim from Overview/Positions |
| `app-parameters-from-date` | `dcc.DatePickerSingle` | Reused verbatim |
| `app-parameters-to-date` | `dcc.DatePickerSingle` | Reused verbatim |
| `overview-shortcut-ytd` (labeled "ITD" on this route) /`-1y`/`-3y`/`-5y`/`-all` | `dbc.Button` | Reused IDs (same ids; only one route's bar is ever mounted — research.md #3); label text overridden via `build_account_date_controls(first_shortcut_label="ITD")` |

No Performance-only controls are added beyond this — no stacked-area
toggle, no multi-select filter (research.md #7).

## New stable component element IDs (Performance page body)

Rendered by `src/pages/performance.py`:

| Element ID | Component | Purpose |
|---|---|---|
| `performance-mount-trigger` | `dcc.Interval` | Same "fire once shortly after mount" pattern as `overview-mount-trigger`/`positions-mount-trigger` |
| `performance-accounts-store` | `dcc.Store` | Same accounts payload Overview/Positions' own stores hold — fetched independently per page mount |
| `performance-attributes-store` | `dcc.Store` | `/v1/performance/attributes` payload |
| `performance-attribute-toggles` | `html.Div` | Container for measure toggle switches (shared builder, research.md #1/#5) |
| `performance-chart-container` | `html.Div` | Wraps the rendered `dcc.Graph` / empty-state / error-state |
| `{"type": "performance-attribute-toggle", "name": ALL}` | `dbc.Switch` | Pattern-matched measure toggles (mirrors Overview's `overview-attribute-toggle` type) |

## Callback contract

| Trigger | Inputs | State | Output | Behavior |
|---|---|---|---|---|
| Page mount | `performance-mount-trigger.n_intervals` | — | `performance-accounts-store.data`, `performance-attributes-store.data`, `app-parameters-account.options`, `performance-attribute-toggles.children` | Fetches `/v1/accounts` + `/v1/performance/attributes`; mirrors `overview.py::_fetch_accounts_and_attributes`, default-on measure computed as "first returned" (research.md #5), not a hard-coded name |
| Default account selected | `performance-accounts-store.data`, `performance-attributes-store.data` | — | `app-parameters-account.value` | Alphabetically-first account; mirrors `overview.py::_apply_default_account` |
| Account selected/changed | `app-parameters-account.value` | `performance-accounts-store.data` | `app-parameters-from-date.date`, `app-parameters-to-date.date` | Resets date range to full recorded history via the shared `_earliest_from_date(account)` (research.md #4 — same as Overview's own `_sync_date_range_to_selected_account`, NOT Positions' "YtD" default) |
| `From`/`To` sync | `app-parameters-to-date.date` | — | `app-parameters-from-date.max_date_allowed` | Identical shared logic to Overview/Positions |
| Shortcut clicked | 5× `n_clicks` | `app-parameters-account.value`, `performance-accounts-store.data` | `app-parameters-from-date.date`, `app-parameters-to-date.date` | Page-local `_SHORTCUT_CODE_BY_BUTTON_ID` maps `overview-shortcut-ytd` → `SHORTCUT_ALL` (not `SHORTCUT_YTD`) — the only divergence from Overview's/Positions' own copies of this mapping (research.md #3) |
| Chart refresh | `app-parameters-account.value`, `app-parameters-from-date.date`, `app-parameters-to-date.date`, `{"type": "performance-attribute-toggle", "name": ALL}.value` | — | `performance-chart-container.children` | Fetches `/v1/accounts/{account}/performance` and renders via `_performance_chart.py::_build_figure` (percentage formatting, research.md #6); `running=` disables every listed control for its duration (FR-017), mirroring 017's `running=` pattern |

## Contract guarantees

- Because `app-parameters-account`/`-from-date`/`-to-date` and the
  `overview-shortcut-*` buttons are the *same* component IDs across all
  three routes (research.md #3), `_render_parameters_bar()` guarantees only
  one set exists in the DOM at a time — Overview's, Positions', and
  Performance's own chart-refresh callbacks each safely take them as
  `Input`/`State` without cross-page interference.
- `performance-attribute-toggle` uses its own pattern-matching `type`
  string, distinct from `overview-attribute-toggle`/`positions-attribute-toggle`,
  so its callback cannot match another (unmounted) page's toggle components
  (same rationale as 018 research.md #2).
- The chart is always rendered from a single fetch of
  `/v1/accounts/{account}/performance` — no client-side merging of two
  separate calls, so there is no path where the chart shows measures from
  two different requests at once.
