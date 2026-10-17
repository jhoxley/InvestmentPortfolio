# Data Model: Position & Portfolio-Weighted Daily Returns

## Entities

### Return-Enriched Ladder Row (extension of feature 002's Priced Ladder Row)

The existing priced row shape (`date`, `sub_account`, `book_cost`, `quantity`, `total_income`,
`price`, `market_value`, `portfolio_weight`) gains two trailing columns, appended — not
interleaved — to preserve backward-compatible column order for anything already reading the
XLSX by position:

| Field                      | Type    | Computation                                                                                     |
|-----------------------------|---------|---------------------------------------------------------------------------------------------------|
| `position_return`           | `float` | `0.0` for a sub-account's first recorded ladder row; otherwise `(price_t - price_{t-1} + income_per_share_t) / price_{t-1}`, where `price_{t-1}` is that sub-account's price on its immediately preceding ladder row (FR-001, FR-004) |
| `weighted_position_return`  | `float` | `0.0` for a sub-account's first recorded ladder row; otherwise `position_return_t * portfolio_weight_{t-1}`, where `portfolio_weight_{t-1}` is that sub-account's portfolio weight on its immediately preceding ladder row — the *start-of-day* weight, not the current row's own `portfolio_weight` (FR-003, FR-004) |

Invariant (FR-001–FR-005, SC-001–SC-003): for every row of a successfully return-enriched
ladder, both columns are non-null. For every sub-account's first recorded row, both columns are
exactly `0.0`. Both columns are pure functions of columns already present on the row and its
immediately preceding same-sub-account row — no external data or additional market-data calls
are consulted.

### Income Per Share (intermediate, not persisted)

| Field               | Type    | Computation                                                                 |
|----------------------|---------|-------------------------------------------------------------------------------|
| `income_per_share_t` | `float` | `0` when `quantity_t == 0` (FR-005); otherwise `(total_income_t - total_income_{t-1}) / quantity_t` (FR-002) |

Computed and discarded entirely within `ReturnsEnrichmentService.enrich()`; never written to
`ladder.xlsx` and never exposed as a retrievable attribute.

### Configuration additions

None. This feature introduces no new configuration surface — it consumes only columns already
produced by the existing ingestion pipeline (feature 002) and writes no external requests.

### `AttributeDefinition` additions (`app/services/position_attributes.py`)

Two new entries in `ATTRIBUTE_DEFINITIONS` (and matching `COLUMN_FOR_ATTRIBUTE` entries),
`source="position_ladder"` like every existing entry:

| `name`                     | `description`                                                                              |
|------------------------------|-----------------------------------------------------------------------------------------------|
| `position_return`            | The position's daily return: price change plus per-share income, relative to the previous day's price. Zero on the position's first recorded ladder date. |
| `weighted_position_return`   | `position_return` scaled by the position's start-of-day (previous ladder date's) portfolio weight, for account- or theme-level contribution analysis. |

### `IngestionSummary` (unchanged in shape)

No field changes. `status` remains `Literal["created", "refreshed"]` (feature 002); return
enrichment participates in both the `created` and `refreshed` flows exactly as pricing
enrichment does, with no new summary-level fields (the spec does not require return totals at
the summary level, mirroring feature 002's equivalent decision for price/market-value totals).

## Relationships

```text
Base daily position ladder (feature 001)
        │
        ▼
PricingEnrichmentService.enrich()   (feature 002)
        │  adds: price, market_value, portfolio_weight
        ▼
ReturnsEnrichmentService.enrich()   (this feature)
        │  groups by sub_account, sorted by date
        │  shift(1) → prev_price, prev_total_income, prev_portfolio_weight
        │  adds: position_return, weighted_position_return
        ▼
Return-Enriched Ladder Row
        │
        ▼
Persisted as ladder.xlsx (unchanged storage mechanism — LadderRepository)
        │
        ├── read_ladder_df()  → base columns only (refresh path re-enrichment input;
        │                       position_return/weighted_position_return already excluded
        │                       by the existing explicit column allowlist)
        │
        └── read_full_df()   → all stored columns, including position_return and
                                weighted_position_return (position time series endpoint)
```

## State Transitions

No new state machine. `position_return`/`weighted_position_return` are recomputed every time
the existing `PricingEnrichmentService` → `ReturnsEnrichmentService` chain runs — on both a
brand-new ingestion (`status: created`) and a checksum-unchanged forced refresh
(`status: refreshed`, feature 002) — and are never partially stale relative to the
price/market-value/portfolio-weight columns they depend on, since both stages always run
together within a single `IngestionService.ingest()` call.
