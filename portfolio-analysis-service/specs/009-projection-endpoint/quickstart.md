# Quickstart: Account Projection Endpoint

## Prerequisites

- `portfolio-analysis-service` set up per the existing README (`.venv` created, dependencies
  installed, service running with `uvicorn app.main:app`).
- An account with an ingested position ladder covering several years, so both the historical
  series and at least the shorter-horizon return measures (`1Y`) have enough history to compute.

## 1. Project forward using one return

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/projection?projection_date=2036-09-22&return=5Y"
```

`start` was omitted, so it defaulted to the account's own most recently recorded date. The
response contains a `"Historical"` series through that date, plus one `"5Y"` series continuing
to `projection_date`:

```json
{
  "account_name": "my-portfolio",
  "attributes": ["market_value"],
  "positions": ["5Y", "Historical"],
  "from_date": "2016-04-20",
  "to_date": "2036-09-22",
  "periodicity": "day",
  "entries": [
    { "date": "2016-04-20", "position": "Historical", "market_value": 50000.0 },
    { "date": "2026-09-22", "position": "Historical", "market_value": 82340.11 },
    { "date": "2026-09-23", "position": "5Y", "market_value": 82412.90 },
    { "date": "2036-09-22", "position": "5Y", "market_value": 141230.44 }
  ],
  "_links": { "self": "/v1/accounts/my-portfolio/projection", "accounts": "/v1/accounts" }
}
```

Note the `"5Y"` series' first entry equals the `"Historical"` series' final `market_value`
exactly — both are the same real number, the account's market value on the resolved start date.

## 2. Compare several returns at once

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/projection?projection_date=2036-09-22&return=3Y&return=5Y"
```

`positions` now lists `["3Y", "5Y", "Historical"]` — one series per requested-and-computable
return, alongside the single historical series.

## 3. A return with insufficient history is silently skipped, not an error

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/a-newer-account/projection?projection_date=2036-09-22&return=5Y&return=1Y"
```

For an account with under five years of history, the response's `positions` contains `["1Y",
"Historical"]` — no `"5Y"` entry, and no error, mirroring exactly how `/v1/accounts/{account}/
performance` already omits a not-yet-computable measure.

## 4. Zero requested returns still succeeds

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/projection?projection_date=2036-09-22"
```

`positions` is `["Historical"]` alone. No `422`, no empty body.

## 5. A non-future projection date is rejected

```powershell
curl.exe -i "http://127.0.0.1:8000/v1/accounts/my-portfolio/projection?projection_date=2020-01-01"
```

```json
{
  "type": "https://portfolio-analysis/errors/invalid-projection-range",
  "title": "Invalid Projection Range",
  "status": 422,
  "detail": "Projection date 2020-01-01 is not later than the resolved start date 2026-09-22. A projection must run forward in time.",
  "instance": "/v1/accounts/my-portfolio/projection"
}
```

## 6. Collapse a long combined span with periodicity

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/projection?projection_date=2046-09-22&return=5Y&periodicity=annual"
```

Both the historical leg (2016–2026) and the projected leg (2026–2046) are bucketed to one entry
per calendar year — the same reduction `/v1/accounts/{account}/timeseries?periodicity=annual`
already produces, applied independently to each series.

## 7. Run the tests

```powershell
.venv\Scripts\python -m pytest tests/unit/test_projection_service.py tests/unit/test_projection_returns.py -v
.venv\Scripts\python -m pytest tests -k projection -v
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy --strict app
```
