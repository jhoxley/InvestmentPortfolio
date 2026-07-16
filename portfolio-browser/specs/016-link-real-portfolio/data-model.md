# Phase 1 Data Model: Account Performance Chart on Overview

No persistence layer — every entity below is a transient, in-memory shape
held in Dash callback state (`dcc.Store` / callback arguments) for the
duration of a page session. Field names and types are taken directly from
`portfolio-analysis-service`'s `app/models/timeseries.py` and its
`specs/004-account-timeseries-api/contracts/openapi.yaml` (verified against
source, not assumed), reproduced here as the browser-side typed shapes in
`src/models/portfolio_analysis.py`.

## Account

Sourced from one element of `GET /v1/accounts`'s `accounts` array.

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | Case-sensitive identifier; used as the path param for the timeseries call and as the Account selector's option value/label (FR-001). |
| `capital_ledger` | `AccountResourceRange \| None` | `{from_date, to_date}` or `None` if not ingested. |
| `position_ladder` | `AccountResourceRange \| None` | `{from_date, to_date}` or `None` if not ingested. |

**Derived field (client-side, presentational — see research.md #8)**:
`earliest_from_date = min(r.from_date for r in (capital_ledger, position_ladder) if r is not None)`
— feeds the "from" `DatePickerSingle` default (FR-003). An `Account` with
both `capital_ledger` and `position_ladder` `None` cannot occur per the
API's own contract ("every account with at least one ingested resource"),
so this `min()` is never computed over an empty sequence — satisfies the
"account with no history is not selectable" edge case by construction, no
extra client-side filtering required.

**Selection state**: exactly one `Account` is "selected" at a time,
defaulting to the alphabetically-first `account_name` in the list
(FR-001a). Selecting a different account resets the date range to that
account's own `earliest_from_date` / last-completed-business-day (per the
"previously-chosen custom date range resets" edge case).

## Performance Metric (Attribute)

Sourced from one element of `GET /v1/timeseries/attributes`'s `attributes`
array.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Wire-format value passed as a repeated `attribute` query param to the timeseries call; also the toggle's value and the legend/series key. |
| `description` | `str` | Shown as the toggle's hover tooltip (FR-006). |
| `source` | `str` | Not rendered in this feature (no UI requirement references it); retained on the model for completeness/future use, not dropped at parse time. |

**Toggle state**: each `Performance Metric` has an independent boolean
on/off state (FR-005), defaulting to `market_value` = on and all others off
on first load (FR-001a). Zero-toggled-on is a valid (if inert) state — see
Chart Series below.

## Date Range

Not a response entity — a client-held selection pair.

| Field | Type | Notes |
|---|---|---|
| `from_date` | `date` | Defaults to selected `Account.earliest_from_date` (FR-003); user-editable within FR-015's constraint (must not exceed `to_date`). |
| `to_date` | `date` | Defaults to the last completed business day (FR-004, computed client-side per research.md #8); user-editable within FR-015's constraint (must not exceed today). |

## Performance Entry

Sourced from one element of the timeseries response's `entries` array
(`TimeSeriesEntry` in the service's model — `date` plus dynamic
attribute-keyed float fields, only for attributes that were requested).

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | X-axis value (FR-009). |
| `<metric_name>` | `float` (dynamic key, one per requested/toggled-on metric) | Y-axis value in GBP, plotted verbatim — no unit conversion (per spec Assumptions). |

## Chart Series

A purely client-side rendering shape — not fetched, derived from
`Performance Entry` list × toggled-on `Performance Metric`s, one per
toggled-on metric.

| Field | Type | Notes |
|---|---|---|
| `metric_name` | `str` | Matches a `Performance Metric.name`; drives the legend label (FR-010). |
| `x` | `list[date]` | All `entries[].date`, shared across every series in one chart. |
| `y` | `list[float]` | `entries[].{metric_name}` for this series. |
| `color` | `str` | Assigned once per metric name from a fixed palette (see below), stable across renders/sessions so the same metric always looks the same (per spec Assumptions). |

**Fixed color assignment**: a static `dict[str, str]` mapping each known
attribute name (`capital`, `income`, `book_cost`, `market_value`, `pnl` —
the enum from the timeseries API's `attribute` query param) to one color
from the existing Bootstrap theme's qualitative palette, defined once in
`src/pages/overview.py` (or a small `_colors.py` constant module) — not
computed at render time, so toggling metrics on/off never reassigns colors.

**Empty state**: zero toggled-on metrics → zero Chart Series → FR-013/edge
case requires the empty-state message, not an empty `dcc.Graph`; the
callback short-circuits before building a `Figure` in this case.

## State flow summary

```text
Page mount
  → GET /v1/accounts            → Store: accounts list
  → GET /v1/timeseries/attributes → Store: attributes list
  → select alphabetically-first account (FR-001a)
  → derive from_date (min of that account's ranges), to_date (last business day)
  → default market_value toggle on
  → GET /v1/accounts/{name}/timeseries?attribute=market_value&start=...&end=...
  → render chart + legend

User changes account
  → re-derive from_date/to_date from the newly-selected account's ranges (Store already has the data — no re-fetch of /v1/accounts)
  → re-fetch timeseries with new account_name + reset dates + currently-toggled metrics

User changes from/to date (valid per FR-015)
  → re-fetch timeseries with same account_name + new dates + currently-toggled metrics

User toggles a metric on/off
  → if ≥1 metric now on: re-fetch timeseries with updated attribute list
  → if 0 metrics now on: skip fetch, show empty-state message
```
