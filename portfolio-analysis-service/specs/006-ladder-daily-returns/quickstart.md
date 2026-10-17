# Quickstart: Position & Portfolio-Weighted Daily Returns

## Prerequisites

- `portfolio-analysis-service` set up per the existing README (`.venv` created, dependencies
  installed).
- An account with a position ladder that can be successfully ingested and priced, i.e. feature
  002's prerequisites (identifier mapping file + reachable `market-data-web-service`) still
  apply — this feature adds no new prerequisites and makes no additional external calls.

## 1. Ingest a ledger as before

No configuration changes are required. Ingestion automatically computes and persists
`position_return` and `weighted_position_return` for every row, immediately after the existing
price/market-value/portfolio-weight enrichment:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder" `
  -F "file=@C:\path\to\my-portfolio-ledger.xlsx"
```

- First submission for a new account → `201 Created`, `status: "created"`.
- Re-submitting the exact same file → `200 OK`, `status: "refreshed"` — price, market value,
  portfolio weight, position return, and weighted position return are all recomputed.
- Download the enriched XLSX (now with trailing `position_return`, `weighted_position_return`
  columns, after the existing `price`/`market_value`/`portfolio_weight` columns) via:

  ```powershell
  curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder/download" -o ladder.xlsx
  ```

## 2. Retrieve the new metrics through the position time series endpoint

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/position?attribute=position_return&attribute=weighted_position_return&position=AAPL.L"
```

Each entry in the response's `entries` array carries `position_return` and
`weighted_position_return` for that `(date, position)` pair, computed once at ingestion and
simply read back — no recomputation on retrieval (User Story 3).

## 3. Confirm the new attributes are discoverable

```powershell
curl.exe "http://127.0.0.1:8000/v1/positions/attributes"
```

The response's `attributes` array now includes `position_return` and
`weighted_position_return` alongside the existing six attributes, each with a description and
`source: position_ladder`.

## 4. Expected values to sanity-check

- Every sub-account's **first recorded ladder row** (including a brand-new position and a
  Cash row on the account's very first ingested date) has `position_return == 0.0` and
  `weighted_position_return == 0.0`.
- For any non-first row, `weighted_position_return` equals `position_return` multiplied by that
  sub-account's `portfolio_weight` from the **previous** row, not the same row — a quick way to
  spot a regression is to compare `weighted_position_return / position_return` against the
  `portfolio_weight` column one date earlier for the same position, not the same date.
- No new error responses are introduced by this feature — a ledger that would have succeeded
  ingestion before this feature still succeeds, now with two additional stored columns.
