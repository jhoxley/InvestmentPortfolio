# Data Model: Position Time Series API

## Entities

### Position Attribute (internal enum, `app/services/position_attributes.py`)

The six supported attribute names for this endpoint and the position-ladder column each maps
to — the single source of truth FR-008 (validation) and FR-017 (metadata) both read from, so
they can never drift apart (SC-005).

| Attribute      | Position-ladder column | Computation                                    |
|----------------|-------------------------|-------------------------------------------------|
| `market_value` | `market_value`          | Direct value, per position, per date            |
| `income`       | `total_income`          | Direct value (cumulative), per position, per date |
| `book_cost`    | `book_cost`             | Direct value, per position, per date             |
| `close_price`  | `price`                 | Direct value, per position, per date             |
| `quantity`     | `quantity`              | Direct value, per position, per date             |
| `pnl`          | *(computed)*            | `income + market_value - book_cost`, per position, per date |

Unlike `app/services/timeseries_attributes.py`'s account-level set, every attribute here
requires only the position ladder — there is no `requires_capital_ledger` split.

### PositionSummary (`app/models/position_timeseries.py`)

One entry in the positions-enumeration endpoint's response (FR-016), and the internal
representation `PositionsService` uses to resolve the effective position set.

| Field | Type | Notes |
|---|---|---|
| `position` | `str` | Aliased from the position ladder's `sub_account` column (incl. `"Cash"`) |
| `from_date` | `date` | This position's earliest recorded position-ladder row |
| `to_date` | `date` | This position's latest recorded position-ladder row |

### PositionsResponse (`app/models/position_timeseries.py`)

Response body for `GET /v1/accounts/{account_name}/positions`.

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | Echoes the requested account |
| `positions` | `list[PositionSummary]` | Every distinct sub_account recorded for the account, sorted by name |
| `links` (`_links`) | `dict[str, str]` | `self` only |

### PositionTimeSeriesEntry (`app/models/position_timeseries.py`)

One row of the main endpoint's response — one per (date, position) combination that has data.

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | One business day within the position's own active window |
| `position` | `str` | The sub_account this entry belongs to |
| *(dynamic)* | `float` | One key per requested attribute — only requested attributes appear (mirrors `TimeSeriesEntry`'s `ConfigDict(extra="allow")` pattern) |

### PositionTimeSeriesResponse (`app/models/position_timeseries.py`)

Response body for `GET /v1/accounts/{account_name}/position`.

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | Echoes the requested account |
| `attributes` | `list[str]` | Requested attribute names, in request order |
| `positions` | `list[str]` | The effective position set actually represented in `entries`, sorted |
| `from_date` | `date` | Resolved start date (request-wide, before per-position clipping) |
| `to_date` | `date` | Resolved end date (request-wide, before per-position clipping) |
| `entries` | `list[PositionTimeSeriesEntry]` | Flat list, one per (date, position) with data — FR-014 |
| `links` (`_links`) | `dict[str, str]` | `self`, `positions`, `attributes`, `accounts` |

### Position Attribute Definition

Reuses `app.models.timeseries.AttributeDefinition` (`name`, `description`, `source`) and
`AttributeMetadataResponse` (`attributes`, `_links`) as-is — identical shape to feature 004's
metadata response, `source` is always `"position_ladder"` for every entry here. No new model
needed (see research.md §5 for why the underlying attribute *list* is still a separate module).

## New Exceptions (`app/exceptions.py`)

| Exception | Raised when | HTTP status |
|---|---|---|
| `PositionLadderNotIngestedError` | Account is known to `/v1/accounts` (e.g. via a capital ledger) but has no ingested position ladder (FR-002, FR-016) | 422 |

Reused as-is: `AccountNotFoundError` (404 — no resource of any kind ingested, message
override), `NoAttributesRequestedError` (422), `UnsupportedAttributeError` (422, this
endpoint's own supported set), `FutureEndDateError` (422), `InvalidDateRangeError` (422),
`MissingRequiredSourceError` (422 — FR-010, `source="position_ladder"`,
`attribute=", ".join(attributes)`).

## Relationships

```text
GET /v1/accounts/{account_name}/position?position=...&attribute=...&start=...&end=...
        │
        ▼
PositionTimeSeriesService.get_series(account_name, positions, attributes, start, end, today)
        │
        ├─ position_attributes.validate_attributes(attributes)   → FR-007/FR-008
        │
        ├─ AccountsService.get_summary(account_name)              → FR-002:
        │       both None            → AccountNotFoundError (404)
        │       position_ladder None → PositionLadderNotIngestedError (422)
        │
        ├─ LadderRepository.read_full_df(account_name)            → full per-sub_account rows
        │
        ├─ PositionsService.resolve_effective_positions(ladder_df, requested_positions)
        │       → distinct sub_accounts ∩ requested (or all, if none requested)  → FR-004/FR-005
        │
        ├─ TimeseriesDateResolver.resolve(start, end, today, [ladder.from_date])
        │       → resolved_start, resolved_end                    → FR-009
        │       (resolved_start < ladder.from_date → MissingRequiredSourceError, FR-010)
        │
        └─ For each position in the effective set:
               subset = ladder_df[ladder_df.sub_account == position]
               first_date, last_date = subset.date.min(), subset.date.max()
               still_held = (last_date == ladder.to_date)
               expand_start = max(resolved_start, first_date)
               expand_end   = resolved_end if still_held else min(resolved_end, last_date)
               if expand_start > expand_end: skip (zero entries for this position)
               expanded = expand_business_days(subset, value_columns, expand_start, expand_end)
               if "pnl" requested: expanded["pnl"] = income + market_value - book_cost
               → append PositionTimeSeriesEntry per row, mapped to requested attribute names
        │
        ▼
PositionTimeSeriesResponse (flat entries, sorted by date then position)


GET /v1/accounts/{account_name}/positions
        │
        ▼
AccountsService.get_summary(account_name)   → same FR-002 validation as above
LadderRepository.read_full_df(account_name)
PositionsService.list_positions(ladder_df)  → groupby(sub_account)[date].agg(min, max)
        │
        ▼
PositionsResponse


GET /v1/positions/attributes
        │
        ▼
AttributeMetadataResponse(attributes=position_attributes.ATTRIBUTE_DEFINITIONS, _links={self})
```

## Repository additions

None. `LadderRepository.read_full_df()` (added in feature 002) already returns every column
this feature needs, ungrouped by `sub_account` — no new repository method required
(research.md §1).
