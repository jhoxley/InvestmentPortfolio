# Phase 1 Data Model: Performance Page

This feature reuses `Account`, `Reporting Period Shortcut`/`Date Range`, and
`Attribute` model shapes unchanged from `016-link-real-portfolio`/
`017-chart-date-range-shortcuts`/`018-positions-page`
(`specs/016-link-real-portfolio/data-model.md`,
`specs/017-chart-date-range-shortcuts/data-model.md`) — not reproduced here
except where this feature adds a new derivation. Unlike `018-positions-page`,
this feature introduces **no new Pydantic model at all** (research.md #1) —
every entity below maps onto an existing model or a purely local,
non-persisted value.

## Performance Measure (reused, not new)

`GET /v1/performance/attributes` returns the same `{name, description,
source}` shape as `/v1/timeseries/attributes`/`/v1/positions/attributes` —
the existing `src/models/portfolio_analysis.py::AttributeDefinition` model is
reused verbatim (research.md #1). No new model.

Known measure names per the `007-performance-endpoints` contract: `ITD`,
`ITD (Ann.)`, `1Y`, `3Y`, `5Y`. The client MUST NOT hard-code this list — it
always renders whatever `/v1/performance/attributes` returns, and the
default-toggled-on measure is computed as "whichever measure is returned
first," not asserted as a literal name (research.md #5).

## Performance Entry / Response (reused, not new)

One row from `GET /v1/accounts/{account_name}/performance` is structurally
identical to the existing `TimeSeriesEntry`/`TimeSeriesResponse` (016) — see
research.md #1 for the field-by-field verification. Reused as-is:

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | One business day within `[from_date, to_date]`. |
| *(dynamic)* | `float` | One key per requested measure (`extra="allow"`, same `TimeSeriesEntry` mechanism); absent for a date/measure combination not yet computable (insufficient history) — not `null`, simply not present in that entry's payload, mirroring the upstream contract's own "simply omitted" wording. |

`TimeSeriesResponse`: `account_name`, `attributes: list[str]`, `from_date`,
`to_date`, `entries: list[TimeSeriesEntry]`, `links: dict[str, str]` — all
reused verbatim; `get_performance()` (research.md #2) returns this same type.

## Account (reused, not new)

Unchanged from 016 — `AccountSummary`, sourced from the same `GET
/v1/accounts` call already shared with Overview and Positions.

## Reporting Period Shortcut (Performance variant — configuration, not a new entity)

Shares its underlying computation (`_shortcut_from_date()` in
`src/components/date_range_controls.py`) entirely with Overview/Positions —
no new shortcut code is added (research.md #3). Only the **label** and the
**page-local id→code mapping** differ for this page's first button:

| Button (Performance) | DOM id (shared/reused) | Underlying code | Computed date |
|---|---|---|---|
| "ITD" | `overview-shortcut-ytd` | `SHORTCUT_ALL` | Account's earliest recorded date |
| "1Y" | `overview-shortcut-1y` | `SHORTCUT_1Y` | 1 year before today, clamped |
| "3Y" | `overview-shortcut-3y` | `SHORTCUT_3Y` | 3 years before today, clamped |
| "5Y" | `overview-shortcut-5y` | `SHORTCUT_5Y` | 5 years before today, clamped |
| "All" | `overview-shortcut-all` | `SHORTCUT_ALL` | Account's earliest recorded date (identical to "ITD" — accepted redundancy per spec Clarifications) |

## Performance Chart Value Formatting (new, derived — not stored)

A pure lookup, `PERFORMANCE_ATTRIBUTE_COLORS: dict[str, str]` plus a
percentage tick/hover format string, in the new
`src/pages/_performance_chart.py` module (research.md #6) — mirrors
`_overview_chart.py`'s `ATTRIBUTE_COLORS`/`DEFAULT_ATTRIBUTE_COLOR` shape,
but every value is presented as a percentage (`.1%`), never a currency
figure, since every Performance measure is a return rate.

## State flow summary

```text
Page mount (performance.py)
  → fetch /v1/accounts (shared with Overview/Positions)
      + /v1/performance/attributes
  → default: first account (alphabetical), first-returned measure toggled
      on (research.md #5)
  → apply full recorded history ("ITD") via the shared
      `_earliest_from_date(account)` (research.md #4 — same default
      Overview itself uses, NOT Positions' own "always YtD" default);
      to = last business day

Any of {account, from, to, shortcut click, measure toggle} changes
  → GET /v1/accounts/{account}/performance?attribute=...&start=...&end=...
  → build chart: one line per toggled-on measure, percentage-formatted
      axis/hover (research.md #6); a measure missing from an entry (not yet
      computable) simply has no point plotted for that date — no error
  → empty state if zero measures are toggled on, or if the response has no
      entries; error state if the account/attributes fetch or the
      performance fetch itself fails — all three reuse the same
      messaging pattern already established by Overview/Positions
```
