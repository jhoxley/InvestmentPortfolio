# Contract: `portfolio-analysis-service` Projection Endpoint

**Status**: Deferred — not implemented by this feature. This document pins the interface this
feature's browser-side code is built against, per the spec's own Assumptions ("a prerequisite
dependency... to be specified and built as its own effort"). Until a real service implements
it, `portfolio-browser`'s tests use a fake client implementing this same contract (matching
the existing pattern in `tests/bdd/steps/*_steps.py`).

## `GET /v1/accounts/{account_name}/projection`

### Query parameters

| Name | Type | Required | Default | Validation |
|---|---|---|---|---|
| `start` | `date` (ISO 8601) | No | Account's `position_ladder.to_date` | Must not be later than that same account's most recent recorded date |
| `projection_date` | `date` (ISO 8601) | **Yes** | — | Must be strictly later than the resolved `start`; else `422` |
| `periodicity` | `str` | No | `day` | One of `day`\|`week`\|`month`\|`quarter`\|`annual` (feature 008's existing enum); unknown value → `422` |
| `return` | `str`, repeatable | No | none | Zero or more of `itd_ann`\|`1y`\|`3y`\|`5y`; unknown value → `422` |

### Success response — `200 application/json`

Identical shape to `GET /v1/accounts/{account_name}/position` (`PositionTimeSeriesResponse`,
see `app/models/position_timeseries.py`), with these fixed/repurposed fields:

```json
{
  "account_name": "HL-SIPP",
  "attributes": ["market_value"],
  "positions": ["Historical", "3Y", "5Y"],
  "from_date": "2016-04-20",
  "to_date": "2036-09-22",
  "periodicity": "month",
  "entries": [
    { "date": "2016-04-30", "position": "Historical", "market_value": 10234.50 },
    { "date": "2016-05-31", "position": "Historical", "market_value": 10391.10 },
    { "date": "2026-09-30", "position": "Historical", "market_value": 48120.75 },
    { "date": "2026-10-31", "position": "3Y", "market_value": 48532.10 },
    { "date": "2026-10-31", "position": "5Y", "market_value": 48601.40 },
    { "date": "2036-09-30", "position": "3Y", "market_value": 71204.90 },
    { "date": "2036-09-30", "position": "5Y", "market_value": 78310.20 }
  ],
  "_links": {
    "self": "/v1/accounts/HL-SIPP/projection",
    "accounts": "/v1/accounts"
  }
}
```

- `positions` always includes `"Historical"`, plus one entry per requested `return` that was
  actually computable for the account (FR-012 — insufficient history silently omits that
  return's label and rows, no error).
- `"Historical"` rows span the account's earliest recorded date through the resolved `start`
  (inclusive of both ends), bucketed at `periodicity`.
- Each requested-and-computable return's rows span the resolved `start` (exclusive — that
  point belongs only to `"Historical"`) through `projection_date` (inclusive), bucketed at
  `periodicity`, computed per `research.md` #2/#3 (`daily_rate = r * sqrt(260)`, compounded
  daily from the start date's actual `market_value`, periodicity applied as an overlay).
- `from_date`/`to_date` are the response's true bounds: the account's earliest record through
  `projection_date`.

### Error responses (RFC 7807 `application/problem+json`, per constitution Principle V)

| Condition | Status | `type`/title (indicative) |
|---|---|---|
| `projection_date` not strictly later than resolved `start` | 422 | Invalid projection range |
| Unknown `periodicity` value | 422 | Unsupported periodicity |
| Unknown `return` value | 422 | Unsupported attribute |
| Account has no position ladder ingested | 404 | Account/resource not found |
| No returns requested and no history at all | 404 | Account/resource not found (same as above — a zero-return request still needs a position ladder to build the Historical series) |

## Browser-side consumption

`src/services/portfolio_analysis_client.py::PortfolioAnalysisClient.get_projection()`
(Protocol + `HttpPortfolioAnalysisClient` implementation) issues this request and parses the
response as the existing `PositionTimeSeriesResponse` model — no new model, no new parsing
code (`research.md` #6).
