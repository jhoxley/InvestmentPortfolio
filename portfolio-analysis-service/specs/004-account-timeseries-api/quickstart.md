# Quickstart: Account Time Series API

## Prerequisites

- `portfolio-analysis-service` set up per its existing README, with at least one account
  already ingested via `POST /v1/accounts/{account_name}/ladder` and/or
  `POST /v1/accounts/{account_name}/capital` (features 001–003). No other service is required
  — this feature only reads already-stored data.

## 1. Start the service

```powershell
cd portfolio-analysis-service
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 2. Discover what accounts and attributes are available

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts"
```

```json
{
  "accounts": [
    {
      "account_name": "HL-SIPP",
      "capital_ledger": { "from_date": "2016-04-20", "to_date": "2026-06-01" },
      "position_ladder": { "from_date": "2016-04-20", "to_date": "2026-07-08" }
    }
  ],
  "_links": { "self": "/v1/accounts" }
}
```

```powershell
curl.exe "http://127.0.0.1:8000/v1/timeseries/attributes"
```

Lists all five supported attribute names, descriptions, and source ledgers.

## 3. Request a time series

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/HL-SIPP/timeseries?attribute=capital&attribute=market_value&attribute=pnl&start=2024-01-02&end=2024-01-10"
```

- Omit `start`/`end` to get the full available range (start = the later of the required
  sources' earliest dates; end = the business day before today).
- If the capital ledger's or position ladder's most recent recorded date is older than the
  resolved end date, the last known value is forward-filled — this is not an error.
- A weekend `start`/`end` is silently adjusted to the next business day (or, in the rare case
  that would land after today, backward to the most recent business day on or before today).

## 4. Expected failure modes

- **Unknown account** (no capital ledger or position ladder ever ingested) → `404`.
- **No `attribute` supplied** → `422`.
- **Unsupported attribute name** → `422`, lists the valid set (see `/v1/timeseries/attributes`).
- **`start` after `end`** (before or after adjustment) → `422`.
- **`end` later than today** → `422`.
- **Requested attribute's required source was never ingested for this account** (e.g.
  `market_value` requested for a capital-only account) → `422`, names the missing source.
- **`start` earlier than a required source's earliest recorded date** → `422`, names the source
  and the earliest date it actually supports (no backward-fill).

In every failure case, the response is an RFC 7807 Problem Detail and no partial time series is
returned.
