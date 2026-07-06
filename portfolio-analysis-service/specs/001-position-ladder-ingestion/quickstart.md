# Quickstart: Position Ladder Ingestion

**Feature**: 001-position-ladder-ingestion

## Prerequisites

- Python 3.11+
- `pip install -r requirements.txt` (or `pip install -e ".[dev]"`)
- A sub-account ledger XLSX file produced by `create_subaccount_ledger`

## Start the service

```bash
uvicorn app.main:app --reload --port 8001
```

Interactive API docs available at: `http://localhost:8001/docs`

## Ingest a ledger

```bash
curl -X POST "http://localhost:8001/v1/accounts/my-portfolio/ladder" \
     -F "file=@path/to/subaccount_ledger.xlsx"
```

**201 Created** (new account):
```json
{
  "account_name": "my-portfolio",
  "status": "created",
  "row_count": 1240,
  "from_date": "2022-01-03",
  "to_date": "2026-07-03",
  "sub_accounts": ["Cash", "AAPL.L", "VWRL.L"],
  "ingested_at": "2026-07-06T10:00:00Z",
  "_links": {
    "self": "/v1/accounts/my-portfolio/ladder",
    "download": "/v1/accounts/my-portfolio/ladder/download"
  }
}
```

**200 OK** (same file re-submitted — no reprocessing):
```json
{ "status": "unchanged", ... }
```

**409 Conflict** (different file — merge not supported):
```json
{
  "type": "https://portfolio-analysis/errors/merge-not-supported",
  "title": "Merge Not Supported",
  "status": 409,
  "detail": "A ladder already exists for 'my-portfolio' with a different checksum. Merging updated ledgers is not currently supported.",
  "instance": "/v1/accounts/my-portfolio/ladder"
}
```

## Retrieve a ladder summary

```bash
curl "http://localhost:8001/v1/accounts/my-portfolio/ladder"
```

## Download the full XLSX ladder

```bash
curl -OJ "http://localhost:8001/v1/accounts/my-portfolio/ladder/download"
```

This downloads `my-portfolio-ladder.xlsx` to the current directory.

## Health / readiness

```bash
curl "http://localhost:8001/health"   # {"status": "ok"}
curl "http://localhost:8001/ready"    # {"status": "ready"}
```

## Run tests

```bash
# All tests (unit + BDD)
pytest

# BDD acceptance tests only
pytest tests/features/

# Single feature file
pytest tests/features/ingest_ladder.feature
```

## Validation errors reference

| HTTP | Error type | Cause |
|------|-----------|-------|
| 422 | `invalid-account-name` | Name contains illegal characters or exceeds 64 chars |
| 422 | `invalid-file-format` | Uploaded file is not a valid XLSX |
| 422 | `schema-validation-failed` | Missing required columns or bad data types |
| 422 | `empty-date-range` | Earliest activity date is within 2 business days of today |
| 404 | `account-not-found` | No ladder ingested for this account name |
| 409 | `merge-not-supported` | File checksum differs from stored ladder |
