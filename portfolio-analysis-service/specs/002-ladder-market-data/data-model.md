# Data Model: Ladder Market Data Enrichment

## Entities

### IdentifierMappingEntry

One entry in the configured JSON identifier-mapping file. Read-only from this service's
perspective; the file itself is owned and maintained outside this repository.

| Field    | Type          | Notes                                                              |
|----------|---------------|---------------------------------------------------------------------|
| `name`   | `str`         | Matched exactly (case-sensitive) against a ladder's `sub_account`   |
| `isin`   | `str \| None` | Fallback identifier; used only when `ticker` is absent (research.md §4) |
| `ticker` | `str \| None` | Preferred identifier when populated (research.md §4)                |

Validation rule: an entry with both `isin` and `ticker` null/absent is equivalent to no entry at
all for FR-005 purposes (triggers `IdentifierMappingError`). Other fields that may exist in the
source file (e.g. `theme`, `multiplier`, `ignore` — see the legacy static JSON schema in this
repository's root `CLAUDE.md`) are ignored; only `name`, `isin`, `ticker` are consumed.

### PriceHistoryPoint (client-side)

The internal representation of one element of `market-data-web-service`'s
`PriceHistoryResponse.prices` array, after being fetched for a given sub-account's identifier.

| Field   | Type    | Notes                                  |
|---------|---------|------------------------------------------|
| `date`  | `date`  | Trading/calendar date                      |
| `close` | `float` | Price in the requested currency (GBP)      |

### Priced Ladder Row (extension of feature 001's Daily Position Ladder row)

The existing row shape (`date`, `sub_account`, `book_cost`, `quantity`, `total_income`) gains
three trailing columns, appended — not interleaved — to preserve backward-compatible column
order for anything already reading the XLSX by position:

| Field              | Type    | Computation                                                                 |
|--------------------|---------|-------------------------------------------------------------------------------|
| `price`            | `float` | 1.0 for `sub_account == "Cash"`; otherwise the GBP close for that date, from the sub-account's single batched price-history request |
| `market_value`     | `float` | `price * quantity` (FR-009)                                                    |
| `portfolio_weight` | `float` | `market_value / sum(market_value for all sub_accounts on that date)`, or `0` when that date's total is zero (FR-010) |

Invariant (FR-011/FR-012, SC-001/SC-002): for every row in a successfully enriched ladder,
`price`, `market_value`, and `portfolio_weight` are non-null; for every date where the
cross-sub-account `market_value` sum is non-zero, `sum(portfolio_weight)` over that date equals
`1.0` within `abs_tol=0.0001`.

### Configuration additions (`app/config.py`)

```text
MarketDataServiceSettings
├── base_url: str = "http://127.0.0.1:8001"
└── timeout_seconds: float = 30.0

IdentifierMappingSettings
└── path: Path | None = None
```

Both are added as new fields on the top-level `Settings` model (alongside the existing `data:`
section), loaded from `config.yaml` exactly like the existing `DataSettings`.

### IngestionSummary (modified)

`status` changes from `Literal["created", "unchanged"]` to `Literal["created", "refreshed"]`
(research.md §6 — a rename, not an additive value). No other fields change shape; `row_count`,
`from_date`, `to_date`, `sub_accounts` continue to describe the base ladder, not the priced
columns (the spec does not require summary-level price/market-value totals).

### New exception types (`app/exceptions.py`)

| Exception                 | Raised when                                                                 | HTTP status |
|----------------------------|-----------------------------------------------------------------------------|-------------|
| `IdentifierMappingError`   | One or more non-Cash sub-accounts have no usable mapping entry (FR-005)     | 422         |
| `PriceCoverageError`       | One or more (sub_account, date) pairs cannot be priced in GBP (FR-008)      | 422         |
| `MarketDataServiceError`   | The market-data-service request fails (network error, non-2xx, timeout)     | 502         |

`IdentifierMappingError` and `PriceCoverageError` both carry a structured payload (mapping of
sub-account → list of problem dates, empty list for a pure mapping failure) so a single response
can name every affected sub-account/date together, per FR-008 and SC-004 — mirroring the existing
pattern of a `.message` attribute built from that structured data (see `EmptyDateRangeError` for
the precedent).

## Relationships

```text
Ledger ingestion (existing)
        │
        ▼
Daily Position Ladder (date, sub_account, book_cost, quantity, total_income)
        │
        ├── group by sub_account (excluding "Cash")
        │       │
        │       ▼
        │   IdentifierMappingRepository.lookup(name) → IdentifierMappingEntry
        │       │
        │       ▼
        │   MarketDataClient.get_price_history(ticker_or_isin, min_date, max_date, "GBP")
        │       │
        │       ▼
        │   list[PriceHistoryPoint]  (one batched call per sub-account — SC-003)
        │
        ▼
Priced Ladder Row (+ price, market_value, portfolio_weight)
        │
        ▼
Persisted as ladder.xlsx (unchanged storage mechanism — LadderRepository)
```

## State Transitions (ingestion response `status`)

| Prior state                          | Trigger                                    | New state    |
|----------------------------------------|---------------------------------------------|--------------|
| No ladder exists for account            | Valid ledger submitted, enrichment succeeds  | `created`    |
| Ladder exists, checksum matches         | Same file re-submitted, enrichment succeeds  | `refreshed`  |
| Ladder exists, checksum differs         | Different file submitted                      | *(unchanged — still raises `MergeNotSupportedError`, 409)* |
| Any of the above, enrichment fails      | Mapping/coverage/service error                | *(no ladder written or overwritten; error response only)* |
