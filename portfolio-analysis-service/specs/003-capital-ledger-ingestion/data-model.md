# Data Model: Capital Ledger Ingestion

## Entities

### Capital Ledger Input File

The sparse XLSX file produced by the `create_capital_ledger` pipeline mode, uploaded via
`POST /v1/accounts/{account_name}/capital`. One row per date on which capital, income, or book
value changed. Confirmed against the reference file `HL_SIPP_Capital_Ledger.xlsx`.

| Field        | Type            | Notes                                                        |
|--------------|-----------------|----------------------------------------------------------------|
| `date`       | date (parseable)| One row per distinct date; not necessarily every calendar day |
| `capital`    | `float`         | Cumulative, not a delta                                        |
| `income`     | `float`         | Cumulative, not a delta                                        |
| `book_value` | `float`         | Cumulative, not a delta                                        |

Validation rules (FR-003/FR-004/FR-005, `CapitalLedgerValidator`):
1. All four columns MUST be present.
2. At least one data row MUST exist.
3. `date` MUST be parseable by `pd.to_datetime`.
4. `capital`, `income`, `book_value` MUST be numeric (`pd.to_numeric` coercible).
5. The recorded range `[min(date), max(date)]` MUST contain at least one business day
   (`EmptyCapitalDateRangeError` otherwise — see below).

No `sub_account` dimension exists for this entity, unlike the position ladder's input.

### Daily Capital Ledger (expanded output)

One row per business day (Mon–Fri) between the earliest and latest `date` present in the
submitted file — **not** extended forward to today (contrast with the position ladder; see
research.md §2). Same columns as the input, densified by forward-fill via the shared
`expand_business_days()` helper (research.md §1).

| Field        | Type    | Computation                                                          |
|--------------|---------|------------------------------------------------------------------------|
| `date`       | `date`  | Every business day from `min(date)` to `max(date)` inclusive           |
| `capital`    | `float` | Forward-filled from the most recent recorded observation on/before it |
| `income`     | `float` | Forward-filled from the most recent recorded observation on/before it |
| `book_value` | `float` | Forward-filled from the most recent recorded observation on/before it |

No closure rule and no grouping key apply — this is a single flat series, unlike the position
ladder's per-sub-account rows.

### CapitalMeta (persisted, `app/repositories/capital_repository.py`)

Metadata JSON persisted alongside `capital.xlsx`, mirroring `AccountMeta` for the ladder but
without a `sub_accounts` field (not applicable — no sub-account dimension).

| Field          | Type       | Notes                                             |
|----------------|------------|-----------------------------------------------------|
| `account_name` | `str`      |                                                      |
| `checksum`     | `str`      | SHA-256 of the uploaded file's raw bytes           |
| `row_count`    | `int`      | Rows in the expanded daily capital ledger           |
| `from_date`    | `date`     | Earliest date in the expanded ledger                |
| `to_date`      | `date`     | Latest date in the expanded ledger                  |
| `ingested_at`  | `datetime` | UTC timestamp of the last successful ingestion      |

### Response models (`app/models/capital.py`)

Reuses the existing `Links` model from `app.models.ladder` (identical shape: `self` + `download`).

**`CapitalIngestionSummary`** (`POST` response, 201/200):

| Field          | Type                        | Notes                                                     |
|----------------|-----------------------------|--------------------------------------------------------------|
| `account_name` | `str`                       |                                                                |
| `status`       | `Literal["created", "refreshed"]` | `created` = brand-new; `refreshed` = checksum matched, nothing recomputed (no enrichment step exists to refresh — see research.md §3), `ingested_at` bumped |
| `row_count`    | `int` (`ge=0`)              |                                                                |
| `from_date`    | `date`                      |                                                                |
| `to_date`      | `date`                      |                                                                |
| `ingested_at`  | `datetime`                  |                                                                |
| `links` (`_links`) | `Links`                 |                                                                |

**`CapitalSummary`** (`GET` response, 200): identical field set to `CapitalIngestionSummary` minus
`status`.

### New exception type (`app/exceptions.py`)

| Exception                     | Raised when                                                              | HTTP status |
|--------------------------------|---------------------------------------------------------------------------|-------------|
| `EmptyCapitalDateRangeError`   | The recorded `[min(date), max(date)]` range contains zero business days   | 422         |

Reused as-is (with capital-specific `message` overrides at the call site — research.md §4):

| Exception               | HTTP status | Capital-specific message                                                         |
|--------------------------|-------------|-------------------------------------------------------------------------------------|
| `InvalidAccountNameError`| 422         | Unchanged — message is already generic                                              |
| `SchemaValidationError`  | 422         | Unchanged — message is already generic                                              |
| `AccountNotFoundError`   | 404         | `"No capital ledger found for account '{account_name}'."`                          |
| `MergeNotSupportedError` | 409         | `"A capital ledger already exists for '{account_name}' with a different checksum. Merging updated capital ledgers is not currently supported."` |

## Relationships

```text
Capital ledger ingestion (new)
        │
        ▼
CapitalLedgerValidator.validate(df, account_name)
        │  (required columns, non-empty, parseable date, numeric values,
        │   non-empty business-day range over [min(date), max(date)])
        ▼
CapitalLedgerExpander.expand(df)
        │  delegates to shared expand_business_days() helper
        │  (research.md §1) — no grouping, no closure rule, no `today` input
        ▼
Daily Capital Ledger (date, capital, income, book_value)
        │
        ▼
Persisted as data/{account_name}/capital.xlsx + capital_meta.json
        (independent of ladder.xlsx / meta.json for the same account — FR-011)
```

## State Transitions (ingestion response `status`)

| Prior state                              | Trigger                              | New state    |
|--------------------------------------------|-----------------------------------------|--------------|
| No capital ledger exists for account        | Valid file submitted, expansion succeeds | `created`    |
| Capital ledger exists, checksum matches     | Same file re-submitted                   | `refreshed` (no recomputation — `ingested_at` bumped only) |
| Capital ledger exists, checksum differs     | Different file submitted                  | *(unchanged — raises `MergeNotSupportedError`, 409)* |
| Recorded date range yields zero business days | Any submission                         | *(rejected — raises `EmptyCapitalDateRangeError`, 422; nothing written)* |
