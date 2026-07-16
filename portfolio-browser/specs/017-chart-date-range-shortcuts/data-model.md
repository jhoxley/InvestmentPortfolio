# Phase 1 Data Model: Date Range Shortcut Buttons on Overview

This feature adds one new entity and one new derivation rule on top of
`016-link-real-portfolio`'s existing model (`specs/016-link-real-portfolio/data-model.md`)
— `Account`, `Performance Metric`, `Performance Entry`, and `Chart Series`
are unchanged and not reproduced here.

## Reporting Period Shortcut (new)

A fixed, spec-defined set of five — not fetched, not user-configurable, not
stored. Represented purely as a `dict[str, str]` mapping each shortcut
button's DOM id to a short shortcut code, defined once in
`src/pages/overview.py`.

| Field | Type | Notes |
|---|---|---|
| `code` | `str` (one of `"ytd"`, `"1y"`, `"3y"`, `"5y"`, `"all"`) | Identifies which calculation to run; resolved from the clicked button's DOM id via `dash.ctx.triggered_id`. |
| `label` | `str` (one of `"YtD"`, `"1Y"`, `"3Y"`, `"5Y"`, `"All"`) | The button's visible text (FR-001). |

## Date Range (extended)

Extends 016's `Date Range` entity (`from_date`, `to_date`) with a new
derivation source. `from_date` now has three possible origins instead of
two:

| Origin | When | Computation |
|---|---|---|
| Account default (016, unchanged) | Account first selected / switched | `Account.earliest_from_date` |
| Manual edit (016, unchanged) | User types/picks a date | Whatever the user entered, subject to FR-015 |
| **Shortcut click (new)** | User clicks a Reporting Period Shortcut button | See below |

**Shortcut `from_date` computation** (`_shortcut_from_date(code, account,
today) -> date` in `src/pages/_overview_chart.py`):

| Code | Computed (pre-clamp) date | Clamp (FR-008) |
|---|---|---|
| `ytd` | `date(today.year, 1, 1)` | `max(computed, Account.earliest_from_date)` |
| `1y` | `today` minus 1 year (leap-day-safe) | `max(computed, Account.earliest_from_date)` |
| `3y` | `today` minus 3 years (leap-day-safe) | `max(computed, Account.earliest_from_date)` |
| `5y` | `today` minus 5 years (leap-day-safe) | `max(computed, Account.earliest_from_date)` |
| `all` | `Account.earliest_from_date` directly | N/A — already the clamp floor |

`to_date` is always set to `_last_business_day(today)` (016's existing
function, reused verbatim) regardless of which shortcut was clicked
(FR-007).

## Refresh-in-flight state (new, transient — not a `dcc.Store`)

Not a data entity in the traditional sense — a UI state derived entirely
from whether `_render_chart` (016) is currently executing, surfaced via
Dash's `running=` callback parameter directly onto each shortcut button's
`disabled` prop (FR-013). No new field/store holds this; it exists only for
the duration of one callback invocation.

## State flow summary (extends 016's)

```text
User clicks a shortcut button (new)
  → look up account_name from app-parameters-account.value (State)
  → look up that account's full record from overview-accounts-store (State)
  → compute + clamp from_date via _shortcut_from_date(code, account, today)
  → compute to_date via _last_business_day(today) (unchanged from 016)
  → set app-parameters-from-date.date, app-parameters-to-date.date
      (the SAME props 016's manual pickers and account-switch already set)
  → _render_chart (016, unchanged) picks up the date change as its own
      Input and re-fetches/re-renders — no new fetch/render path
  → for the duration of that _render_chart execution, all 5 shortcut
      buttons are disabled (running=[...]), then re-enabled
```
