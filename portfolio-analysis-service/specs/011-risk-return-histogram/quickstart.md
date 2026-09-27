# Quickstart: Risk Endpoints — Daily Return Histogram

## Prerequisites

- Service set up per the README (`.venv`, dependencies installed).
- An account with an ingested, return-enriched position ladder (features 001/002/006), i.e. the
  same prerequisite as the performance endpoints. This feature adds no ingestion step and makes no
  market-data-service calls.

## 1. Request a histogram

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/risk/return-histogram?start=2024-01-02&end=2024-12-31"
```

`start` and `end` are optional and default exactly as they do for
`/v1/accounts/{account_name}/performance`.

```json
{
  "account_name": "my-portfolio",
  "from_date": "2024-01-02",
  "to_date": "2024-12-31",
  "histogram": [[-25, 1], [-3, 4], [0, 12], [7, 9], [65, 1]],
  "statistics": {
    "count": 27,
    "mean": 4.1,
    "median": 3.0,
    "mode": 0,
    "minimum": -25,
    "maximum": 65,
    "std_dev": 14.2,
    "std_dev_bands": [
      {"sigma": 1, "multiple": 14.2, "lower": -10.1, "upper": 18.3},
      {"sigma": 2, "multiple": 28.4, "lower": -24.3, "upper": 32.5},
      {"sigma": 3, "multiple": 42.6, "lower": -38.5, "upper": 46.7}
    ],
    "skewness": 1.8,
    "kurtosis": 6.2
  },
  "_links": {"self": "/v1/accounts/my-portfolio/risk/return-histogram", "accounts": "/v1/accounts"}
}
```

(Values illustrative.) Buckets are integer basis points (1 bp = 0.01%); only buckets with at least
one observation appear, smallest first.

## 2. Verify consistency with performance

The number of observations equals the number of business days in the window that the performance
endpoints have a daily return for:

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/performance?attribute=ITD&start=2024-01-02&end=2024-12-31"
```

## 3. Error cases

- `start` after `end` → `422` problem+json (`InvalidDateRangeError`)
- Unknown account → `404` problem+json
- Single-day window (`start` = `end`) → `200`, one bucket with count 1, `std_dev`/`skewness`/`kurtosis` `null`

## 4. Run the tests

```powershell
.venv/Scripts/python -m pytest tests/unit/test_return_histogram.py tests/unit/test_risk_service.py tests/unit/test_daily_return_series_loader.py
.venv/Scripts/python -m pytest tests/features/return_histogram.feature
.venv/Scripts/python -m pytest tests/unit/test_performance_service.py tests/features/retrieve_performance.feature   # regression for the shared refactor
ruff check app tests; ruff format --check app tests; mypy --strict app
```
