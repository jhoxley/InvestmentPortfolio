# Contract: `GET /v1/accounts/{account_name}/projection`

The authoritative, finalized version of the contract originally pinned by `portfolio-browser`'s
`specs/022-projection-page/contracts/portfolio-analysis-api.md` — the two corrections made during
this service's own planning (`research.md` #2, #7) are reflected here as the source of truth for
this repository going forward.

## Request

`GET /v1/accounts/{account_name}/projection`

| Parameter | Location | Type | Required | Default | Validation |
|---|---|---|---|---|---|
| `account_name` | path | string | yes | — | Existing account-name pattern check |
| `start` | query | date (ISO 8601) | no | Account's `position_ladder.to_date` | Forward-adjusted to a business day, capped at `to_date`; rejected (422) if it would fall before `from_date` |
| `projection_date` | query | date (ISO 8601) | yes | — | Must be strictly later than resolved `start` (422 otherwise); **no upper bound** — future dates are the point |
| `periodicity` | query | string | no | `day` | One of `day`\|`week`\|`month`\|`quarter`\|`annual` (existing `Periodicity` enum) |
| `return` | query, repeatable | string | no | none | Zero or more of `ITD (Ann.)`\|`1Y`\|`3Y`\|`5Y` |

## Success response — `200 application/json`

Body shape: the existing `PositionTimeSeriesResponse` (`app/models/position_timeseries.py`),
unmodified.

```json
{
  "account_name": "HL-SIPP",
  "attributes": ["market_value"],
  "positions": ["3Y", "5Y", "Historical"],
  "from_date": "2016-04-20",
  "to_date": "2036-09-22",
  "periodicity": "month",
  "entries": [
    { "date": "2016-04-30", "position": "Historical", "market_value": 10234.50 },
    { "date": "2026-09-30", "position": "Historical", "market_value": 48120.75 },
    { "date": "2026-09-30", "position": "3Y", "market_value": 48120.75 },
    { "date": "2026-09-30", "position": "5Y", "market_value": 48120.75 },
    { "date": "2036-09-30", "position": "3Y", "market_value": 71204.90 },
    { "date": "2036-09-30", "position": "5Y", "market_value": 78310.20 }
  ],
  "_links": {
    "self": "/v1/accounts/HL-SIPP/projection",
    "accounts": "/v1/accounts"
  }
}
```

- `positions` always includes `"Historical"`, plus one entry per requested-and-computable
  return (alphabetically sorted, matching every other endpoint's own `positions` field
  convention — consumers must not assume `"Historical"` is first; `portfolio-browser`'s own
  chart code already sorts it to the front client-side).
- `"Historical"` rows span the account's earliest recorded date through resolved `start`.
- Each survivor return's rows span resolved `start` through `projection_date`, and its first
  row's `market_value` equals `"Historical"`'s final row's `market_value` exactly.
- `from_date`/`to_date` are the response's true bounds: the ladder's earliest record through
  `projection_date`.

## Error responses (RFC 7807 `application/problem+json`)

| Condition | Status | `type` slug |
|---|---|---|
| `projection_date` not strictly later than resolved `start` | 422 | `invalid-projection-range` |
| Unknown `periodicity` value | 422 | `unsupported-periodicity` |
| Unknown `return` value | 422 | `unsupported-attribute` |
| `resolved_start` precedes the ladder's own earliest recorded date | 422 | `missing-required-source` |
| Account known but has no ingested position ladder | 422 | `position-ladder-not-ingested` |
| Account has no ingested resource of any kind | 404 | `account-not-found` |
| Invalid `account_name` | 422 | `invalid-account-name` |

## OpenAPI

Documented via the router's own `summary`/`responses` kwargs (FastAPI auto-generates the
`/openapi.json` entry from these, per Constitution Principle V) — no separate hand-maintained
OpenAPI file exists in this codebase; the live spec at `/openapi.json` is authoritative,
consistent with every other endpoint here.

> **Update (010-projection-start-alignment):** for non-day periodicities each projected series contains window-start dates only; see `specs/010-projection-start-alignment/contracts/projection-api-delta.md`.
