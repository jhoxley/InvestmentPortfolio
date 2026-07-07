# Quickstart: Ladder Market Data Enrichment

## Prerequisites

- `portfolio-analysis-service` and `market-data-web-service` both set up per their existing
  READMEs (`.venv` created, dependencies installed).
- An identifier-mapping JSON file available on disk, shaped like:

  ```json
  [
    { "name": "AAPL", "isin": "US0378331005", "ticker": "AAPL" },
    { "name": "VWRL", "isin": "IE00B3RBWM25", "ticker": "VWRL.L" }
  ]
  ```

  (Only `name`, `isin`, `ticker` are read by this feature — see data-model.md. `ticker` is
  preferred over `isin` when both are present.) The `Cash` sub-account does **not** need an
  entry — it is always priced at 1.0 GBP.

## 1. Configure `portfolio-analysis-service`

Add the following to `portfolio-analysis-service/config.yaml`:

```yaml
data:
  directory: ./data

market_data_service:
  base_url: http://127.0.0.1:8001
  timeout_seconds: 30

identifier_mapping:
  path: C:/Users/jhoxl/OneDrive/Investments/InvestmentDataStatic.json
```

`base_url` must point at wherever `market-data-web-service` is actually running.
`identifier_mapping.path` must point at the mapping file described above.

## 2. Start both services

```powershell
# Terminal 1
cd market-data-web-service
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8001

# Terminal 2
cd portfolio-analysis-service
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or run both together via the repo-root `run_end_to_end.ps1`, which now wires the
`market_data_service` block automatically to match the ports it starts each service on.

## 3. Ingest a ledger and inspect the enriched ladder

```powershell
curl.exe -X POST "http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder" `
  -F "file=@C:\path\to\my-portfolio-ledger.xlsx"
```

- First submission for a new account → `201 Created`, `status: "created"`.
- Re-submitting the exact same file → `200 OK`, `status: "refreshed"` (prices recomputed,
  ladder rows/date range unchanged).
- Download the enriched XLSX (now with trailing `price`, `market_value`, `portfolio_weight`
  columns) via:

  ```powershell
  curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder/download" -o ladder.xlsx
  ```

## 4. Expected failure modes

- **Missing mapping entry**: a non-Cash sub-account with no matching `name` in the mapping file
  (or an entry with neither `isin` nor `ticker`) → `422`, error names the sub-account.
- **Unpriceable date(s)**: the market-data-service cannot supply a GBP price for one or more
  business days a sub-account is active on → `422`, error names every affected sub-account and
  date together (not just the first one found).
- **Market-data-service unreachable**: connection failure or non-2xx response → `502`.

In all three cases, no ladder is written or overwritten for that account.
