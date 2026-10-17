# Quickstart: Account Performance Retrieval Endpoints

## Prerequisites

- `portfolio-analysis-service` set up per the existing README (`.venv` created, dependencies
  installed).
- An account with an ingested, return-enriched position ladder (feature 006) — i.e.
  `POST /v1/accounts/{account_name}/ladder` has already succeeded for this account, so every
  row carries `weighted_position_return`. This feature adds no new ingestion step and makes no
  market-data-service calls of its own.

## 1. Request performance measures for an account

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/performance?attribute=ITD&attribute=1Y&attribute=5Y"
```

With no `start`/`end` supplied, the response covers the account's full ingested history through
the business day before today — the same defaulting behaviour as
`GET /v1/accounts/{account_name}/timeseries`.

Each entry carries whichever requested measures are computable for that date:

```json
{
  "account_name": "my-portfolio",
  "attributes": ["ITD", "1Y", "5Y"],
  "from_date": "2020-01-02",
  "to_date": "2026-07-24",
  "entries": [
    { "date": "2020-01-02", "ITD": 0.0 },
    { "date": "2021-01-04", "ITD": 0.041 },
    { "date": "2025-01-06", "ITD": 0.183, "1Y": 0.071, "5Y": 0.062 }
  ],
  "_links": {
    "self": "/v1/accounts/my-portfolio/performance?attribute=ITD&attribute=1Y&attribute=5Y",
    "attributes": "/v1/performance/attributes",
    "accounts": "/v1/accounts"
  }
}
```

Note `1Y` and `5Y` are absent from the 2020-01-02 and 2021-01-04 entries — the account doesn't
yet have 1 (or 5) years of history at those dates, so those keys are simply omitted rather than
appearing as `null` (per this feature's resolved clarification).

## 2. Confirm a narrow window still uses the full trailing history

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/performance?attribute=3Y&start=2022-01-01&end=2022-01-01"
```

Even though only one date is requested, the returned `3Y` value is computed from the trailing 780
business days ending on 2022-01-01 (reaching back to on or around 2019-01-01) — the same value
you'd see for that date if a wider window were requested instead.

## 3. Confirm the new measures are discoverable

```powershell
curl.exe "http://127.0.0.1:8000/v1/performance/attributes"
```

The response lists exactly five entries — `ITD`, `ITD (Ann.)`, `1Y`, `3Y`, `5Y` — each with a
description (including its formula) and `source: position_ladder`.

## 4. Expected values to sanity-check

- `ITD` is `0.0` on the account's very first recorded ladder date (a single day of zero daily
  portfolio return compounds to `0.0`).
- `1Y`/`3Y`/`5Y` first appear exactly 260/780/1300 business days after the account's first
  recorded ladder date, never earlier.
- Requesting the same measure for the same date in two different requests (one with a narrow
  window, one with a wide window that includes that date) always returns the same value — a
  quick way to spot a regression is to compare a single-day request against a multi-year request
  covering that day.
- No ingestion behaviour changes — this feature only adds two new read-only `GET` endpoints.

## Validation notes (from end-to-end testing against real ingested accounts)

- All four `curl` commands above were run against a real multi-year account and confirmed to
  match: `ITD` is `0.0` on the first recorded date; `1Y`/`3Y`/`5Y` first appear exactly
  260/780/1300 business days after inception; a single-day request and a wide-window request
  return byte-identical values for a shared date; `/v1/performance/attributes` lists exactly the
  five documented entries.
- On one real account, a single day's `weighted_position_return` was found to be an extreme
  outlier (a large negative value, almost certainly an upstream price-data anomaly for one
  position, unrelated to this feature). Because `ITD` is an expanding cumulative product from
  inception, that one bad day permanently distorts every subsequent `ITD`/`ITD (Ann.)` value for
  the account — this is the mathematically correct behaviour given the input, not a bug in this
  feature's formulas (verified: `1Y`/`3Y`/`5Y` recover once the offending date rolls out of the
  trailing window). This feature intentionally performs no outlier filtering or sanitization of
  `weighted_position_return` — it is out of scope, and any such fix belongs in feature 006's
  ingestion/enrichment pipeline, not here.
