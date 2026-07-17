# UI Contract: Positions Page

Extends `016-link-real-portfolio`'s and `017-chart-date-range-shortcuts`'s
UI contracts for the shared Account/From/To/shortcut controls (now
extracted into `src/components/date_range_controls.py` — same component
IDs, same shortcut/clamp behavior, reused by both routes; see research.md
#1). The one deliberate behavioral difference — Positions' own default
date range on account selection/switch is always "YtD," not Overview's
full-history default — is covered by research.md #1a, not by this shared
extraction. This file covers what's new/Positions-specific.

## New stable component element IDs (Positions parameters bar)

Rendered by `src/layout/shell.py::_build_positions_parameters_bar()`
(Positions route only):

| Element ID | Component | Purpose |
|---|---|---|
| `app-parameters-account` | `dbc.Select` | Reused verbatim from Overview (research.md #1) |
| `app-parameters-from-date` | `dcc.DatePickerSingle` | Reused verbatim |
| `app-parameters-to-date` | `dcc.DatePickerSingle` | Reused verbatim |
| `overview-shortcut-ytd`/`-1y`/`-3y`/`-5y`/`-all` | `dbc.Button` | Reused verbatim (same IDs; only one route's bar is ever mounted — research.md #1) |
| `positions-parameters-stacked-toggle` | `dbc.Switch` | "Stacked area graph" toggle (FR-006), Positions-only |
| `positions-parameters-position-filter` | `dcc.Dropdown` (`multi=True`) | Position multi-select (FR-005), Positions-only |

## New stable component element IDs (Positions page body)

Rendered by `src/pages/positions.py`:

| Element ID | Component | Purpose |
|---|---|---|
| `positions-mount-trigger` | `dcc.Interval` | Same "fire once shortly after mount" pattern as `overview-mount-trigger` (016 research.md #7) |
| `positions-accounts-store` | `dcc.Store` | Same accounts payload Overview's own store holds — fetched independently per page mount, not shared cross-page in memory |
| `positions-attributes-store` | `dcc.Store` | `/v1/positions/attributes` payload |
| `positions-list-store` | `dcc.Store` | `/v1/accounts/{account}/positions` payload for the currently selected account |
| `positions-attribute-toggles` | `html.Div` | Container for attribute toggle switches (shared builder, research.md #2) |
| `positions-chart-container` | `html.Div` | Wraps the rendered `dcc.Graph` / empty-state / error-state |
| `positions-table-container` | `html.Div` | Wraps the rendered `dash_table.DataTable` / empty-state |
| `{"type": "positions-attribute-toggle", "name": ALL}` | `dbc.Switch` | Pattern-matched attribute toggles (mirrors Overview's `overview-attribute-toggle` type) |

## Callback contract

| Trigger | Inputs | State | Output | Behavior |
|---|---|---|---|---|
| Page mount | `positions-mount-trigger.n_intervals` | — | `positions-accounts-store.data`, `positions-attributes-store.data`, `app-parameters-account.options`, `positions-attribute-toggles.children` | Fetches `/v1/accounts` + `/v1/positions/attributes`; mirrors `overview.py::_fetch_accounts_and_attributes` |
| Default account selected | `positions-accounts-store.data`, `positions-attributes-store.data` | — | `app-parameters-account.value` | Alphabetically-first account (FR-012); mirrors `overview.py::_apply_default_account` |
| Account selected/changed | `app-parameters-account.value` | `positions-accounts-store.data` | `app-parameters-from-date.date`, `app-parameters-to-date.date`, `positions-list-store.data`, `positions-parameters-position-filter.options`, `positions-parameters-position-filter.value` | Resets date range to "YtD" for the new account via the shared `_shortcut_from_date(SHORTCUT_YTD, account, today)` (research.md #1a — deliberately NOT Overview's own `_sync_date_range_to_selected_account`, which yields full history), fetches `/v1/accounts/{account}/positions`, and resets the position filter to every position for the new account (FR-014) |
| Shortcut clicked | 5× `n_clicks` | `app-parameters-account.value`, `positions-accounts-store.data` | `app-parameters-from-date.date`, `app-parameters-to-date.date` | Identical shared logic to Overview's `_apply_date_range_shortcut` (research.md #1) |
| 2nd attribute toggled on while stacked-area is on | `{"type": "positions-attribute-toggle", "name": ALL}.value` | `positions-parameters-stacked-toggle.value` | `positions-parameters-stacked-toggle.value` (`allow_duplicate=True`) | Sets the toggle to `False` (FR-010) — never blocks the attribute toggle itself |
| Attribute count changes | `{"type": "positions-attribute-toggle", "name": ALL}.value` | — | `positions-parameters-stacked-toggle.disabled` | `True` while more than one attribute is selected (FR-011), `False` otherwise |
| Chart/table refresh | `app-parameters-account.value`, `app-parameters-from-date.date`, `app-parameters-to-date.date`, `{"type": "positions-attribute-toggle", "name": ALL}.value`, `positions-parameters-position-filter.value`, `positions-parameters-stacked-toggle.value` | — | `positions-chart-container.children`, `positions-table-container.children` | One callback renders both outputs together from one fetch (data-model.md's state flow; FR-013, SC-006); `running=` disables every listed control for its duration (FR-023), mirroring 017's `running=` pattern |

## Contract guarantees

- The chart and table are always rendered by the same callback from the
  same fetched response — there is no code path where one refreshes
  without the other (SC-006).
- `positions-parameters-stacked-toggle` is only ever set to `True` by a
  direct user click while `disabled=False`; it is only ever programmatically
  set to `False`, never programmatically set to `True` — satisfying FR-009
  (only user-initiated, single-attribute-gated) without a race between the
  auto-off callback and a hypothetical auto-on path (none exists).
- Because `app-parameters-account`/`-from-date`/`-to-date` and the
  `overview-shortcut-*` buttons are the *same* component IDs on both
  routes (research.md #1), `_render_parameters_bar()` guarantees only one
  set exists in the DOM at a time — Overview's and Positions's own
  chart-refresh callbacks each safely take them as `Input`/`State` without
  cross-page interference.
