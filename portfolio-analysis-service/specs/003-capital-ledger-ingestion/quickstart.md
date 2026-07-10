# Quickstart: Capital Ledger Ingestion

## Prerequisites

- `portfolio-analysis-service` set up per its existing README (`.venv` created, dependencies
  installed). No other service is required — this feature has no market-data dependency.
- An XLSX capital ledger file produced by the `AccountPreparationPipeline`'s
  `create_capital_ledger` mode, e.g.:

  ```powershell
  cd AccountPreparationPipeline
  .venv\Scripts\python pipeline.py create_capital_ledger `
    path\to\ledger.xlsx path\to\HL_SIPP_Capital_Ledger.xlsx
  ```

  The resulting file has columns `date`, `capital`, `income`, `book_value` (all cumulative).

## 1. Start the service

```powershell
cd portfolio-analysis-service
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 2. Ingest a capital ledger

```powershell
curl.exe -X POST "http://127.0.0.1:8000/v1/accounts/my-portfolio/capital" `
  -F "file=@C:\Users\jhoxl\OneDrive\Investments\HL_SIPP_Capital_Ledger.xlsx"
```

- First submission for a new account → `201 Created`, `status: "created"`.
- Re-submitting the exact same file → `200 OK`, `status: "refreshed"` (nothing recomputed — no
  enrichment step exists for this resource; only `ingested_at` is bumped).
- Submitting a *different* file for an account that already has a stored capital ledger →
  `409 Conflict` (merge not supported, matching the ladder endpoint's behaviour).

## 3. Retrieve the summary and download the full ledger

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/capital"
```

```json
{
  "account_name": "my-portfolio",
  "row_count": 2612,
  "from_date": "2016-04-20",
  "to_date": "2026-06-01",
  "ingested_at": "2026-07-10T10:00:00Z",
  "_links": {
    "self": "/v1/accounts/my-portfolio/capital",
    "download": "/v1/accounts/my-portfolio/capital/download"
  }
}
```

```powershell
curl.exe "http://127.0.0.1:8000/v1/accounts/my-portfolio/capital/download" -o capital.xlsx
```

The downloaded XLSX has one row per business day from the earliest to the latest date recorded
in the *original submitted file* — this range is **not** extended forward to today (unlike the
position ladder), since there is no pricing step requiring a current-as-of freshness boundary.

## 4. Expected failure modes

- **Missing/invalid columns, non-XLSX file, non-numeric values** → `422`, error names the
  specific problem.
- **Recorded date range yields zero business days** (e.g. a single-row file whose only date is a
  Saturday) → `422`.
- **Unknown account on `GET` or download** → `404`.
- **Different file submitted for an account with an existing capital ledger** → `409`.

In all failure cases, no capital ledger is written or overwritten for that account, and the
existing position ladder (if any) for the same account is entirely unaffected — the two resources
are independent (see data-model.md).
