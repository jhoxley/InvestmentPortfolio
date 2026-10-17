# Quickstart: Periodicity Parameter for Account & Position Time Series

## Prerequisites

- `portfolio-analysis-service` set up per the existing README (`.venv` created, dependencies
  installed, service running with `uvicorn app.main:app`).
- An account with an ingested capital ledger and/or position ladder — exactly what the existing
  time series endpoints already require. This feature adds **no new ingestion step**, no new
  stored column, and no market-data-service calls.

## 1. Nothing changes if you don't ask for it

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/timeseries?attribute=capital"
```

One entry per business day, exactly as before. The only difference from the pre-feature response
is the additive `periodicity` field reporting the default:

```json
{
  "account_name": "my-portfolio",
  "attributes": ["capital"],
  "from_date": "2016-01-04",
  "to_date": "2026-09-21",
  "periodicity": "day",
  "entries": [
    { "date": "2016-01-04", "capital": 50000.0 },
    { "date": "2016-01-05", "capital": 50000.0 }
  ],
  "_links": { "self": "/v1/accounts/my-portfolio/timeseries", "attributes": "/v1/timeseries/attributes", "accounts": "/v1/accounts" }
}
```

`periodicity=day` is byte-identical to omitting the parameter.

## 2. Collapse a decade into ten observations

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/timeseries?attribute=capital&attribute=market_value&start=2016-01-04&end=2025-12-31&periodicity=annual"
```

```json
{
  "account_name": "my-portfolio",
  "attributes": ["capital", "market_value"],
  "from_date": "2016-01-04",
  "to_date": "2025-12-31",
  "periodicity": "annual",
  "entries": [
    { "date": "2016-01-04", "capital": 50000.0,  "market_value": 51230.44 },
    { "date": "2017-01-02", "capital": 60000.0,  "market_value": 64880.12 },
    { "date": "2025-01-01", "capital": 180000.0, "market_value": 241305.75 }
  ],
  "_links": { "self": "/v1/accounts/my-portfolio/timeseries", "attributes": "/v1/timeseries/attributes", "accounts": "/v1/accounts" }
}
```

Three things to notice:

- **10 entries**, not 2,608. Swap `annual` for `quarter`, `month` or `week` over the same range to
  get 40, 120 or 522 entries respectively.
- Each entry is dated at the **start** of its window (rolled forward to a business day), while its
  values are the **last** observation *in* that window. So the `2016-01-04` entry carries the
  capital and market value as they stood on **2016-12-30**, the last business day of 2016.
- The first entry is dated `2016-01-04`, not `2016-01-01`: the first window is clamped to
  `from_date` so no entry date ever falls outside the stated range.
- `from_date` / `to_date` still describe the resolved **daily** range and are unaffected by
  `periodicity`.

## 3. Same parameter, same rules, per position

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/position?attribute=market_value&start=2025-01-01&end=2025-06-30&periodicity=quarter"
```

```json
{
  "account_name": "my-portfolio",
  "attributes": ["market_value"],
  "positions": ["Blackrock_Consensus_85", "Scottish_Widows_Pension"],
  "from_date": "2025-01-01",
  "to_date": "2025-06-30",
  "periodicity": "quarter",
  "entries": [
    { "date": "2025-01-01", "position": "Blackrock_Consensus_85",  "market_value": 41200.55 },
    { "date": "2025-01-01", "position": "Scottish_Widows_Pension", "market_value": 62920.00 },
    { "date": "2025-04-01", "position": "Blackrock_Consensus_85",  "market_value": 43880.10 },
    { "date": "2025-04-01", "position": "Scottish_Widows_Pension", "market_value": 66000.00 }
  ],
  "_links": { "self": "/v1/accounts/my-portfolio/position", "positions": "/v1/accounts/my-portfolio/positions", "attributes": "/v1/positions/attributes", "accounts": "/v1/accounts" }
}
```

Every position in a window shares the **same** entry date, because a window's date comes from the
calendar period and the resolved start only — never from a position's own data. That is what lets
you overlay per-position series on the account-level series at the same periodicity. A position
with no data in a window simply produces no entry for it.

## 4. Verify the calendar alignment yourself

| Periodicity | Window starts on | Example entry dates |
|-------------|------------------|---------------------|
| `week` | Monday | 2026-01-05, 2026-01-12, 2026-01-19 |
| `month` | 1st of the month | 2026-01-01, 2026-02-02, 2026-03-02 |
| `quarter` | 1 Jan / 1 Apr / 1 Jul / 1 Oct | 2025-01-01, 2025-04-01, 2025-07-01 |
| `annual` | 1 Jan | 2024-01-01, 2025-01-01 |

Where a calendar boundary falls on a weekend it rolls forward to the next business day (hence
2026-02-02 for February 2026, whose 1st is a Sunday).

## 5. Bad values are rejected, not silently defaulted

```powershell
curl.exe -i "http://127.0.0.1:8000/v1/accounts/my-portfolio/timeseries?attribute=capital&periodicity=fortnight"
```

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/problem+json
```

```json
{
  "type": "https://portfolio-analysis/errors/unsupported-periodicity",
  "title": "Unsupported Periodicity",
  "status": 422,
  "detail": "Periodicity 'fortnight' is not supported. Supported values: day, week, month, quarter, annual.",
  "instance": "/v1/accounts/my-portfolio/timeseries"
}
```

Matching is **case-sensitive** and accepts no synonyms — `Annual`, `yearly`, `daily` and `Q` are
all rejected the same way. The full supported set always appears in `detail`, and also as a
machine-readable `enum` on the parameter in `http://127.0.0.1:8000/openapi.json`.

## 6. Watch out for return attributes

Under a non-`day` periodicity, `position_return` and `weighted_position_return` report the **last
single-day return** in the window — they are *not* compounded period returns. If you want a
compounded quarterly or annual return, use the performance endpoint (feature 007) or treat it as a
separate feature request.

## 7. Run the tests

```powershell
.venv\Scripts\python -m pytest tests/unit/test_periodicity_aggregation.py tests/unit/test_periodicity_validator.py -v
.venv\Scripts\python -m pytest tests/features/timeseries_periodicity.feature -v
.venv\Scripts\python -m pytest            # full suite — existing time series tests must still pass unchanged
.venv\Scripts\python -m mypy app
.venv\Scripts\python -m ruff check app tests
```

The last three matter most: this feature's core promise is that everything that worked before
still returns exactly what it returned before.
