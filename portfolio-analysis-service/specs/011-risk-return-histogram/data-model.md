# Data Model: Risk Endpoints — Daily Return Histogram

No new persisted data. All entities are computed per request from the stored position ladder.

## Portfolio Daily Return (existing, shared)

Produced by `compute_daily_portfolio_return`.

| Field | Type | Notes |
|---|---|---|
| date | date | Business day |
| daily_return | float | Sum of `weighted_position_return` across all sub-accounts that day; `0.0` when no rows |

## Basis Point Observation (internal)

| Field | Type | Rule |
|---|---|---|
| bps | int | `round_half_away_from_zero(daily_return × 10,000)` |

Only dates in `[resolved_start, resolved_end]` are observed.

## ReturnHistogramResponse (API)

| Field | Type | Notes |
|---|---|---|
| account_name | string | Echoed from path |
| from_date | date | Resolved start |
| to_date | date | Resolved end |
| histogram | array of `[int, int]` | `[bucket_bps, count]`; count ≥ 1; sorted by bucket ascending; unique buckets |
| statistics | HistogramStatistics | See below |
| _links | object | `self`, `accounts` |

### HistogramStatistics

| Field | Type | Units | Null when |
|---|---|---|---|
| count | integer | observations | never |
| mean | number \| null | bps | count = 0 |
| median | number \| null | bps | count = 0 |
| mode | integer \| null | bps | count = 0 (ties → smallest bucket) |
| minimum | integer \| null | bps | count = 0 |
| maximum | integer \| null | bps | count = 0 |
| std_dev | number \| null | bps | count < 2 (sample, ddof = 1) |
| std_dev_bands | array of StdDevBand | bps | empty list when std_dev is null |
| skewness | number \| null | dimensionless | count < 3 or std_dev = 0 |
| kurtosis | number \| null | dimensionless (excess) | count < 4 or std_dev = 0 |

### StdDevBand

| Field | Type | Notes |
|---|---|---|
| sigma | integer | 1, 2 or 3 |
| multiple | number | sigma × std_dev |
| lower | number | mean − multiple |
| upper | number | mean + multiple |

## Invariants

- `sum(count for _, count in histogram) == statistics.count`.
- `histogram` is strictly increasing in bucket; no zero counts.
- `minimum` = first bucket, `maximum` = last bucket (when non-empty).
- `count` equals the number of business days in the window present in the shared daily-return
  series (identical to the performance endpoints' series).

## Validation & errors

| Condition | Outcome |
|---|---|
| Invalid account name | 422, `InvalidAccountNameError` |
| No ledger or ladder ingested | 404, `AccountNotFoundError` |
| Ladder missing / start before ladder's first date | 422, `MissingRequiredSourceError` |
| End date in the future | 422, `FutureEndDateError` |
| Resolved start after end | 422, `InvalidDateRangeError` |
| Valid request | 200; window always has ≥ 1 business day, so `count ≥ 1` (zero-observation statistics are defined defensively: `count = 0`, all else null) |
