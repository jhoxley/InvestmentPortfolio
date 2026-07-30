# Data Model: Account Performance Retrieval Endpoints

None of the entities below introduce new persisted storage — every value is derived at request
time from the already-stored position ladder (`weighted_position_return`, feature 006). This
document describes the in-memory shapes used while serving a request, plus the two new API
response schemas.

## Derived (in-memory only)

### Daily Portfolio Return

One row per business day, spanning an account's entire ingested position-ladder history.

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | Business day. |
| `daily_return` | `float` | Sum of `weighted_position_return` across every position present in the ladder on that date; `0.0` for a date with no ladder rows at all. |

Built by aggregating `LadderRepository.read_full_df(account_name)` (`groupby("date")` sum), then
reindexed over every business day from the ladder's earliest recorded date through the resolved
`end` date. Never computed for dates before the ladder's earliest recorded date.

### Performance Measure Series

One row per business day (same index as Daily Portfolio Return), with one column per supported
measure. A cell is absent (`NaN` internally; omitted from the API response) wherever that
measure's required look-back window extends before the ladder's earliest recorded date.

| Field | Type | Formula (FR-006–FR-009) | First available on |
|---|---|---|---|
| `ITD` | `float \| None` | Cumulative product of `(1 + daily_return)` since inception, minus 1 | Ladder's first recorded date (value `0.0`) |
| `ITD (Ann.)` | `float \| None` | `(1 + ITD) ** (260 / elapsed_trading_days) - 1` | Ladder's first recorded date (value `0.0`) |
| `1Y` | `float \| None` | Cumulative product of `(1 + daily_return)` over trailing 260 business days, minus 1 | 260th business day of history |
| `3Y` | `float \| None` | `(1 + trailing_780_day_cumprod) ** (1/3) - 1` | 780th business day of history |
| `5Y` | `float \| None` | `(1 + trailing_1300_day_cumprod) ** (1/5) - 1` | 1300th business day of history |

## API Schemas

### `PerformanceEntry`

One entry per business day in the resolved `[from_date, to_date]` window.

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | The business day. |
| *(dynamic)* | `float` | One key per requested, computable measure (`ITD`, `ITD (Ann.)`, `1Y`, `3Y`, `5Y`); a measure not yet computable for this date is simply absent from the entry (FR-011). |

### `PerformanceResponse`

Response body for `GET /v1/accounts/{account_name}/performance`.

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | Case-sensitive account identifier. |
| `attributes` | `list[str]` | Requested measure names, in request order (always the full requested list, regardless of per-date availability). |
| `from_date` | `date` | Resolved start date. |
| `to_date` | `date` | Resolved end date. |
| `entries` | `list[PerformanceEntry]` | One per business day in range. |
| `_links` | `dict[str, str]` | HATEOAS navigation (`self`, `attributes`, `accounts`). |

### `PerformanceAttributeDefinition`

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | One of `ITD`, `ITD (Ann.)`, `1Y`, `3Y`, `5Y`. |
| `description` | `str` | Human-readable meaning, including the formula. |
| `source` | `str` | `"position_ladder"` for every entry (all measures derive from `weighted_position_return`). |

### `PerformanceAttributeMetadataResponse`

Response body for `GET /v1/performance/attributes`.

| Field | Type | Notes |
|---|---|---|
| `attributes` | `list[PerformanceAttributeDefinition]` | Exactly five entries. |
| `_links` | `dict[str, str]` | HATEOAS navigation (`self`). |

## Validation Rules

- At least one `attribute` must be requested (`NoAttributesRequestedError`, mirrors FR-014).
- Every requested `attribute` must be one of the five supported names
  (`UnsupportedAttributeError`).
- `start`/`end` resolution and rejection rules (future `end`, resolved `start` after resolved
  `end`) are unchanged from the existing time series endpoint (`TimeseriesDateResolver`, reused
  as-is).
- The account must have an ingested position ladder — `AccountNotFoundError` (404) if the account
  has no ingested resource of any kind, `MissingRequiredSourceError` (422) if the account is known
  via another resource (e.g. a capital ledger) but has no position ladder.
