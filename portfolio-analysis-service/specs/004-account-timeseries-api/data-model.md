# Data Model: Account Time Series API

## Entities

### Attribute (internal enum, `app/services/timeseries_attributes.py`)

The five supported attribute names and their source requirements — the single source of truth
FR-004 (validation) and FR-017 (metadata) both read from, so they can never drift apart
(SC-004).

| Attribute      | Requires capital ledger | Requires position ladder | Computation                                  |
|----------------|:------------------------:|:--------------------------:|-----------------------------------------------|
| `capital`      | ✅                        |                             | Capital ledger's `capital` column             |
| `income`       | ✅                        |                             | Capital ledger's `income` column (cumulative) |
| `book_cost`    | ✅                        |                             | Capital ledger's `book_value` column          |
| `market_value` |                           | ✅                          | Sum of position ladder's `market_value` column across all sub-accounts (incl. Cash) for that date |
| `pnl`          | ✅                        | ✅                          | `income + market_value - book_cost`           |

### TimeSeriesEntry (`app/models/timeseries.py`)

One row of the main endpoint's response.

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | One business day in the resolved range |
| *(dynamic)* | `float` | One key per requested attribute, e.g. `capital`, `market_value` — only requested attributes appear (research.md §5); modelled via `ConfigDict(extra="allow")` |

### TimeSeriesResponse (`app/models/timeseries.py`)

The main endpoint's full response body.

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | Echoes the requested account |
| `attributes` | `list[str]` | The requested attribute names, in request order |
| `from_date` | `date` | Resolved start date (FR-006/FR-008) |
| `to_date` | `date` | Resolved end date (FR-007/FR-008) |
| `entries` | `list[TimeSeriesEntry]` | One per business day in `[from_date, to_date]` |
| `links` (`_links`) | `Links` | `self`, `attributes`, `accounts` (reuses `app.models.ladder.Links`-style shape, extended — see below) |

### AttributeDefinition (`app/models/timeseries.py`)

One entry in the metadata endpoint's response.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Wire-format attribute name (e.g. `pnl`) |
| `description` | `str` | Human-readable meaning |
| `source` | `str` | `capital_ledger`, `position_ladder`, or `capital_ledger,position_ladder` |

### AttributeMetadataResponse (`app/models/timeseries.py`)

| Field | Type | Notes |
|---|---|---|
| `attributes` | `list[AttributeDefinition]` | All five, in the canonical order from the Attribute table above |
| `links` (`_links`) | `object` | `self` only (this resource has no related detail/download endpoint) |

### AccountResourceRange (`app/models/timeseries.py`)

| Field | Type | Notes |
|---|---|---|
| `from_date` | `date` | Earliest recorded date for this resource |
| `to_date` | `date` | Latest recorded date for this resource |

### AccountSummary (`app/models/timeseries.py`)

One entry in the accounts-enumeration endpoint's response.

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | |
| `capital_ledger` | `AccountResourceRange \| None` | `None` if no capital ledger ingested |
| `position_ladder` | `AccountResourceRange \| None` | `None` if no position ladder ingested |

### AccountsResponse (`app/models/timeseries.py`)

| Field | Type | Notes |
|---|---|---|
| `accounts` | `list[AccountSummary]` | Every account with at least one ingested resource |
| `links` (`_links`) | `object` | `self` only |

## New/changed links shape

A generic `_links` object is used across all three new response types; unlike the existing
`Links` model (which always has exactly `self` + `download`), these need a variable set of
related links (`attributes`, `accounts` on the main response; just `self` on the other two).
Modelled as a plain `dict[str, str]` per response rather than forcing a new named model per
shape — still serialises identically as a JSON object under `_links`.

## New Exceptions (`app/exceptions.py`)

| Exception | Raised when | HTTP status |
|---|---|---|
| `NoAttributesRequestedError` | Zero `attribute` query params supplied (FR-003) | 422 |
| `UnsupportedAttributeError` | One or more requested attribute names aren't in the supported set (FR-004) | 422 |
| `FutureEndDateError` | Supplied `end` is later than today, before adjustment (FR-010) | 422 |
| `InvalidDateRangeError` | Resolved start is after resolved end, post-adjustment (FR-009) | 422 |
| `MissingRequiredSourceError` | A required source doesn't exist for the account, or its earliest recorded date is after the resolved start (FR-015) | 422 |

Reused as-is: `AccountNotFoundError` (404, FR-002) with a timeseries-specific message override.

## Relationships

```text
GET /v1/accounts/{account_name}/timeseries?attribute=...&start=...&end=...
        │
        ▼
TimeSeriesService.get_series(account_name, attributes, start, end)
        │
        ├─ AccountsService.get_summary(account_name)   → validates account known (FR-002)
        │                                               → supplies each source's own
        │                                                 from_date/to_date for defaulting
        │                                                 and the earliest-date check
        │
        ├─ TimeseriesDateResolver.resolve(start, end, today, required_sources)
        │       → resolved_start, resolved_end (FR-006–FR-010)
        │
        ├─ CapitalRepository.read_df(account_name)      (if capital-derived attrs requested)
        │       → expand_business_days(df, [...], resolved_start, resolved_end)
        │
        ├─ LadderRepository.read_full_df(account_name)  (if market_value/pnl requested)
        │       → groupby(date)[market_value].sum()
        │       → expand_business_days(agg, ["market_value"], resolved_start, resolved_end)
        │
        ├─ if BOTH sources required: join capital-derived + market_value series on date
        │  if only ONE source required: use that single expanded frame directly (no join —
        │  e.g. market_value alone on a ladder-only account, or capital/income/book_cost
        │  alone with no ladder involvement at all)
        ├─ compute pnl per row if requested (only reachable when both sources were required)
        └─ select only requested attribute columns → TimeSeriesResponse
```

## Repository additions

| Method | Repository | Purpose |
|---|---|---|
| `read_df(account_name) -> pd.DataFrame` | `CapitalRepository` | Full `[date, capital, income, book_value]` — did not exist before this feature |
| `read_full_df(account_name) -> pd.DataFrame` | `LadderRepository` | Full stored columns including `market_value` (existing `read_ladder_df` deliberately drops enrichment columns for the refresh path, so a new method is added rather than changing that one's contract) |
| `list_accounts() -> list[str]` | Both | Scans `data_dir` for subdirectories containing this repository's meta file; used by `AccountsService` |
