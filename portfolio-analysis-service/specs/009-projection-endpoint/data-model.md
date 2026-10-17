# Phase 1 Data Model: Account Projection Endpoint

No new Pydantic response model is introduced — see `research.md` #1. This document maps the
spec's Key Entities onto the reused `PositionTimeSeriesResponse` shape and the request's own
resolved fields.

## Projection Request → query parameters

| Spec entity field | Wire parameter | Type | Resolution |
|---|---|---|---|
| Account | path segment `{account_name}` | str | Validated by the existing `validate_account_name` |
| Start date (defaults to most recent record) | `start` | date, optional | `research.md` #3 — defaults to `position_ladder.to_date`, forward-adjusted to a business day, capped at `to_date`, rejected if it lands before `from_date` |
| Projection target date | `projection_date` | date, required | Must be strictly later than resolved `start` (`InvalidProjectionRangeError` otherwise) |
| Periodicity | `periodicity` | str, optional | Existing `Periodicity` enum, resolved by the existing `resolve_periodicity()`, default `day` |
| Requested returns | `return` (repeated) | str, 0..N | One of `"ITD (Ann.)"`, `"1Y"`, `"3Y"`, `"5Y"` (`research.md` #2); empty list is valid |

## Historical Series / Projected Series → `PositionTimeSeriesResponse.entries`

Both series types are rows in the same flat `entries: list[PositionTimeSeriesEntry]`,
distinguished by `position` (repurposed as a series label):

| `position` value | Represents | Date range | Built from |
|---|---|---|---|
| `"Historical"` | Historical Series | ladder's `from_date` → resolved `start` (inclusive both ends) | `TimeSeriesService`'s own account-level `market_value` aggregation (`research.md` #4) |
| `"ITD (Ann.)"` / `"1Y"` / `"3Y"` / `"5Y"` | one Projected Series per requested-and-computable Return | resolved `start` (inclusive) → `projection_date` (inclusive) | `research.md` #5's compounding formula |

Each entry carries a single dynamic attribute key, `market_value` (float), via the model's
existing `extra="allow"`. `attributes` in the response is always `["market_value"]`.
`PositionTimeSeriesResponse.positions` is the sorted list of labels actually present — always
includes `"Historical"`; includes a requested return's label only if it was both requested and
computable (`research.md` #5's silent-omission rule).

## Return → the four supported performance measures, reused verbatim

Not a new entity — `app/services/projection_returns.py`'s `SUPPORTED_PROJECTION_RETURNS`
(`research.md` #2), a fixed subset of `performance_attributes.ATTRIBUTE_DEFINITIONS`'s own
`name` values. No new calculation, no new naming.

## Internal computation shape (not part of the wire contract)

Two small intermediate DataFrames, each shaped `[date, market_value]`, one business-day row
each, built independently and each passed once through `aggregate_last_observation()`
(`research.md` #6):

- **Historical**: `expand_business_days(ladder_df.groupby("date")["market_value"].sum(), ["market_value"], from_date, resolved_start)`
- **Per projected return**: a synthesized `pd.bdate_range(resolved_start, projection_date)` with
  `market_value = start_value * (1 + daily_rate) ** t`

Both shapes exactly match what `expand_business_days()`/`aggregate_last_observation()` already
expect and are already tested against elsewhere in this codebase — no new DataFrame contract is
introduced.
