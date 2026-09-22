# Phase 1 Data Model: Projection Page (replaces Income)

This feature introduces **no new Pydantic models** on the browser side — see
`research.md` #1 and #6 for why `PositionTimeSeriesResponse` is reused as-is. This document
maps the spec's Key Entities onto that existing shape, plus the page-local UI state that has
no server-side representation.

## Projection Request → HTTP query parameters

| Spec entity field | Wire parameter | Type | Notes |
|---|---|---|---|
| Account | path segment `{account_name}` | str | Same as every other account-scoped endpoint |
| Start date (defaults to most recent record) | `start` | date, optional | Omitted → service defaults to `position_ladder.to_date` |
| Projection target date | `projection_date` | date, required | Must be `> resolved_start`; service returns a validation error otherwise (FR-014) |
| Interval | `periodicity` | str, optional | Feature 008's existing enum; default `day` |
| Requested returns | `return` (repeated) | str, 0..N | `itd_ann` \| `1y` \| `3y` \| `5y` |

## Historical Series / Projected Series → `PositionTimeSeriesResponse.entries`

Both series types are rows in the same flat `entries: list[PositionTimeSeriesEntry]` list,
distinguished by the existing `position` field, repurposed here as a **series label**:

| `position` value | Represents | Date range covered |
|---|---|---|
| `"Historical"` | Historical Series (spec) | account's earliest recorded date → resolved start date |
| `"1Y"` / `"3Y"` / `"5Y"` / `"Ann. ITD"` | one Projected Series per requested Return | resolved start date → projection target date |

Each entry carries a single dynamic attribute key, `market_value` (float), via the model's
existing `extra="allow"` — no schema change needed; `attributes` in the response is always
the fixed single-element list `["market_value"]`.

`PositionTimeSeriesResponse.positions` (the "positions actually represented" field) becomes,
for this endpoint, the list of series labels actually present — always includes
`"Historical"`; includes a requested return's label only if that return was both requested
**and** computable for the account (FR-012's silent-omission rule — an omitted return simply
never contributes a `position` value, exactly as an unrepresented position already behaves on
the existing Positions endpoint today).

## Return → the four fixed selectable measures

Not a server-defined list for this page (research.md #5) — a page-local constant in
`src/pages/projection.py`:

```python
_PROJECTION_RETURNS: list[AttributeDefinition] = [
    AttributeDefinition(name="Ann. ITD", description="...", source="performance"),
    AttributeDefinition(name="1Y", description="...", source="performance"),
    AttributeDefinition(name="3Y", description="...", source="performance"),
    AttributeDefinition(name="5Y", description="...", source="performance"),
]
```

Wire values sent as `return` query params use the lowercase-with-underscore form
(`itd_ann`, `1y`, `3y`, `5y`) mirroring `performance_attributes.py`'s existing
`ITD (Ann.)` → `itd_ann` convention on the service side; the mapping from display label to
wire value is a small local dict alongside the constant above, not derived at runtime.

## Page-local UI state (no server representation)

| State | Held in | Written by | Read by |
|---|---|---|---|
| Selected account | `app-parameters-account.value` (shared control, page-scoped per 020's fix) | account dropdown | start-date sync, chart render |
| Start date | `projection-start-date.date` | account sync (default) OR direct user edit | chart render, horizon button math, calendar `min_date_allowed` |
| Projection target date in effect | `projection-target-store.data` | horizon button click OR calendar picker change | calendar picker sync (display), chart render |
| Selected returns | pattern-matched `projection-attribute-toggle` switches | toggle switches | chart render |
| Validation message (FR-014) | `projection-date-validation.children` | calendar picker change handler / chart-render error path | rendered `dbc.FormText`/`dbc.Alert` beside the calendar control |

This mirrors 021's `overview-periodicity-store` single-writer pattern exactly (research.md
#4) — no new state-management approach introduced.
