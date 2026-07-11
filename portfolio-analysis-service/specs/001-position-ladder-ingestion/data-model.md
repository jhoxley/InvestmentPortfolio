# Data Model: Position Ladder Ingestion

**Feature**: 001-position-ladder-ingestion
**Date**: 2026-07-06

## Entities

### LedgerRow (input)

Represents one row of the sub-account ledger file produced by `create_subaccount_ledger`.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `date` | `datetime.date` | Required, parseable date | Activity date |
| `sub_account` | `str` | Required, non-empty | Position name or "Cash" |
| `book_cost` | `float` | Required | Cumulative book cost (£) |
| `quantity` | `float` | Required | Cumulative units held |
| `total_income` | `float` | Required | Cumulative income received (£) |

**Validation rules**:
- All five columns MUST be present; missing any → `SchemaValidationError` (422)
- `date` column MUST be parseable as a date; non-parseable rows → `SchemaValidationError`
- `book_cost`, `quantity`, `total_income` MUST be numeric; non-numeric → `SchemaValidationError`
- File MUST contain at least one data row; empty file → `SchemaValidationError`

---

### LadderRow (stored / output)

One row of the expanded daily position ladder. Same columns as `LedgerRow` but densified
across all business days in the date range.

| Field | Type | Notes |
|-------|------|-------|
| `date` | `datetime.date` | Business day in the expansion range |
| `sub_account` | `str` | Position name or "Cash" |
| `book_cost` | `float` | Forward-filled from most recent activity |
| `quantity` | `float` | Forward-filled from most recent activity |
| `total_income` | `float` | Forward-filled from most recent activity |

**State / lifecycle rules**:
- Equity sub-account (`sub_account != "Cash"`) rows are present from first activity date
  through the last business day on which `quantity > 0`
- Cash sub-account rows are present on every business day from first Cash activity through
  the end of the date range regardless of balance
- No row may appear for a date outside the expansion range

---

### AccountMeta (persisted as `meta.json`)

Lightweight metadata file stored alongside each account's `ladder.xlsx`.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `account_name` | `str` | `[A-Za-z0-9_-]`, 1–64 chars | Primary key |
| `checksum` | `str` | SHA-256 hex digest | Of raw input XLSX bytes |
| `row_count` | `int` | ≥ 0 | Total rows in the stored ladder |
| `from_date` | `datetime.date` | | Earliest date in the ladder |
| `to_date` | `datetime.date` | | Latest date in the ladder |
| `sub_accounts` | `list[str]` | | Distinct sub-account names present |
| `ingested_at` | `datetime` | ISO 8601 UTC | When the ladder was last written |

---

### API Response Models (Pydantic)

#### `IngestionSummary`

Returned on `POST /v1/accounts/{name}/ladder` (201 new, 200 no-op).

```python
class Links(BaseModel):
    self_: str = Field(alias="self")
    download: str

class IngestionSummary(BaseModel):
    account_name: str
    status: Literal["created", "unchanged"]
    row_count: int
    from_date: date
    to_date: date
    sub_accounts: list[str]
    ingested_at: datetime
    links: Links = Field(alias="_links")
```

#### `LadderSummary`

Returned on `GET /v1/accounts/{name}/ladder`.

```python
class LadderSummary(BaseModel):
    account_name: str
    row_count: int
    from_date: date
    to_date: date
    sub_accounts: list[str]
    ingested_at: datetime
    links: Links = Field(alias="_links")
```

#### `ProblemDetail` (RFC 7807)

Returned for all error responses (`Content-Type: application/problem+json`).

```python
class ProblemDetail(BaseModel):
    type: str        # URI reference identifying the error type
    title: str       # Short human-readable summary
    status: int      # HTTP status code
    detail: str      # Human-readable explanation
    instance: str    # The request path that triggered the error
```

---

## Storage Layout

```
data/
  {account_name}/
    ladder.xlsx      # Full expanded daily position ladder (human-readable)
    meta.json        # AccountMeta serialised as JSON
```

- Directory created on first successful ingestion for an account.
- `ladder.xlsx` is overwritten atomically (write to temp file, then rename) — not applicable
  in this version since merge is unsupported; the file is only written once per account.
- `meta.json` is read on every ingest/retrieve to perform checksum comparison without
  loading the full XLSX.

---

## State Transitions

```
[Account unknown]
      │
      │  POST with new file (checksum not seen)
      ▼
[Account exists — ladder current]
      │                    │
      │  POST same file    │  POST different file
      │  (checksum match)  │  (checksum mismatch)
      ▼                    ▼
[200 no-op]         [409 merge not supported]
```
