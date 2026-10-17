# Quickstart: Position Time Series API

## Prerequisites

- `portfolio-analysis-service` set up per its existing README, with at least one account
  already ingested via `POST /v1/accounts/{account_name}/ladder` (features 001–002). A capital
  ledger is not required — this feature reads only the position ladder.

## 1. Start the service

```powershell
cd portfolio-analysis-service
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 2. Discover which positions and attributes are available

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/HL-SIPP/positions"
```

```json
{
  "account_name": "HL-SIPP",
  "positions": [
    { "position": "Apple Inc", "from_date": "2020-03-02", "to_date": "2026-07-08" },
    { "position": "Cash", "from_date": "2016-04-20", "to_date": "2026-07-08" },
    { "position": "Sold Corp", "from_date": "2018-06-01", "to_date": "2021-11-15" }
  ],
  "_links": { "self": "/v1/accounts/HL-SIPP/positions" }
}
```

```powershell
curl.exe "http://127.0.0.1:8000/v1/positions/attributes"
```

Lists all six supported attribute names and descriptions (`market_value`, `income`,
`book_cost`, `pnl`, `close_price`, `quantity` — note `capital` is not valid here).

## 3. Request a position time series

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/HL-SIPP/position?position=Apple%20Inc&attribute=market_value&attribute=quantity&start=2024-01-02&end=2024-01-10"
```

- Position names containing spaces or symbols must be percent-encoded (`Apple Inc` →
  `Apple%20Inc`).
- Omit `position` entirely to get every position recorded for the account, including `Cash`.
- An unrecognised `position` value is silently dropped — it never causes an error.
- Omit `start`/`end` to get the full available range (start = the account's own earliest
  recorded position-ladder date; end = the business day before today).
- A position still actively held as of the ladder's last refresh has its last known values
  forward-filled through the resolved end date, the same as the account-level endpoint's
  staleness handling. A position that was genuinely sold stops at its real last active date
  and is never forward-filled past it.
- The response is a flat list of `{date, position, ...requested attributes}` entries — ready
  to load directly into a dataframe and plot one line per position (e.g.
  `px.line(df, x="date", y="market_value", color="position")` in a Dash app) with no
  reshaping required.

## 4. Expected failure modes

- **Unknown account** (no resource of any kind ever ingested) → `404`.
- **Known account with no ingested position ladder** (e.g. capital-ledger-only) → `422`
  (not `404` — the account name itself is valid).
- **No `attribute` supplied** → `422`.
- **Unsupported attribute name, including `capital`** → `422`, lists this endpoint's valid
  set (see `/v1/positions/attributes`).
- **`start` after `end`** (before or after adjustment) → `422`.
- **`end` later than today** → `422`.
- **`start` earlier than the position ladder's earliest recorded date** → `422`.

In every failure case, the response is an RFC 7807 Problem Detail and no partial time series
is returned. A request naming one or more unrecognised `position` values alongside at least
one recognised value (or resolving to an empty effective position set) is **not** a failure
mode — it returns `200` with data only for the recognised positions (or zero entries).
