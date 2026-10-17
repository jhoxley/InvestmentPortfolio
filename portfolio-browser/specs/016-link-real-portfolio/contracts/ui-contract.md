# UI Contract: Account Performance Chart on Overview

Extends `specs/015-create-template-python/contracts/ui-contract.md`'s
element-ID contract. IDs listed there that are superseded on the Overview
route are called out explicitly below; all other 015 IDs (`app-header`,
`app-footer`, `app-sidebar`, `app-sidebar-nav-{key}`, `app-content-frame`,
`app-page-content`) are unchanged and still govern non-Overview routes.

## Route-aware parameters bar (`app-parameters-bar`)

`app-parameters-bar` (`src/layout/shell.py`) is now route-aware (see
research.md #7):

| Route | Contents |
|---|---|
| `/` (Overview) | Real controls: `app-parameters-account` (populated `dbc.Select`), `app-parameters-from-date` (`dcc.DatePickerSingle`), `app-parameters-to-date` (`dcc.DatePickerSingle`) |
| Any other route | Unchanged 015 static, disabled placeholder (`app-parameters-account`, `app-parameters-daterange`, both `disabled=True`) |

`app-parameters-daterange` (015's single placeholder input) is **split**
into `app-parameters-from-date` / `app-parameters-to-date` on the Overview
route only — this is a superseding, not an additive, change to that ID's
role; the 015 ID string itself keeps rendering unchanged on non-Overview
routes.

## New stable component element IDs (Overview page only)

Rendered inside `app-page-content` by `src/pages/overview.py` — these do
not exist on any other route, satisfying FR-007 by construction (see
research.md #7):

| Element ID | Component | Purpose |
|---|---|---|
| `overview-attribute-toggles` | `dbc.Checklist` (`switch=True`) | One switch per `Performance Metric` from `/v1/timeseries/attributes` (FR-005) |
| `overview-attribute-tooltip-{name}` | `dbc.Tooltip` | Hover description for the `{name}` metric's switch (FR-006), targeting that switch option's generated id |
| `overview-chart` | `dcc.Graph` | The rendered line chart (FR-009); legend rendered via Plotly's own `layout.legend`, positioned below the plot area (FR-010) |
| `overview-chart-loading` | `dcc.Loading` | Wraps `overview-chart`; gives feedback within 100ms of any triggering interaction (constitution UX standard) |
| `overview-empty-state` | `html.Div` | Rendered instead of `overview-chart` when zero metrics are toggled on, or the account/date/metric combination yields zero entries (FR-013) |
| `overview-error-state` | `html.Div` | Rendered instead of `overview-chart` when any of the three upstream calls fails (FR-014) |
| `overview-accounts-store` | `dcc.Store` | Session-scoped cache of the `/v1/accounts` response (research.md #9) |
| `overview-attributes-store` | `dcc.Store` | Session-scoped cache of the `/v1/timeseries/attributes` response (research.md #9) |

## Callback contract

| Trigger | Inputs | Output | Behavior |
|---|---|---|---|
| Overview page mount | (page load) | `overview-accounts-store`, `overview-attributes-store`, `app-parameters-account` options+value, `app-parameters-from-date`/`to-date` values, `overview-attribute-toggles` options+value | Fetches accounts + attributes once; auto-selects alphabetically-first account and `market_value` (FR-001a); derives date defaults (FR-003/FR-004) |
| Account changed | `app-parameters-account.value` | `app-parameters-from-date`/`to-date` values, `overview-chart`/`overview-empty-state`/`overview-error-state` | Re-derives date range from `overview-accounts-store` (no re-fetch of `/v1/accounts`); re-fetches timeseries |
| From/To date changed | `app-parameters-from-date.value`, `app-parameters-to-date.value` | `overview-chart`/`overview-empty-state`/`overview-error-state`, `app-parameters-to-date.max_date_allowed`, `app-parameters-from-date.max_date_allowed` | Validates FR-015 (`to` ≤ today, `from` ≤ `to`) before fetching; invalid state is prevented at the picker level via `max_date_allowed`/`min_date_allowed`, not caught post-hoc |
| Metric toggle changed | `overview-attribute-toggles.value` | `overview-chart`/`overview-empty-state`/`overview-error-state` | ≥1 metric on → re-fetch timeseries with the new attribute list; 0 metrics on → render `overview-empty-state`, no fetch |

## Contract guarantees

- `overview-attribute-toggles` and both `overview-*-store` elements exist
  only within `src/pages/overview.py`'s layout — Dash Pages unmounts them on
  navigation away, so FR-007 ("MUST NOT appear on any other navigation
  section") holds without any explicit show/hide logic to maintain.
- `overview-chart`, `overview-empty-state`, and `overview-error-state` are
  mutually exclusive — exactly one is visible at a time, driven by a single
  callback output (a `Div` children swap), never three independently-toggled
  `style={"display": ...}` states that could drift out of sync.
- The chart callback's *only* inputs affecting the plotted `y` values are
  the raw `entries` from `GET /v1/accounts/{name}/timeseries` — no
  client-side recomputation of any value, per constitution Principle I.
