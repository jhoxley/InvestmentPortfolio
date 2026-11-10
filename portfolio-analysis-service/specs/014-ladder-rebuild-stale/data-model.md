# Phase 1 Data Model: On-Demand Ladder Rebuild for Stale Requests

## Updated entities

### AccountMeta (`app/repositories/ladder_repository.py`)

| Field | Type | Change | Notes |
|---|---|---|---|
| `account_name` | `str` | unchanged | |
| `checksum` | `str` | unchanged | Checksum of the most recently *ingested* file; unaffected by a rebuild (a rebuild uploads nothing). |
| `row_count` | `int` | unchanged | Recomputed on every write, including a rebuild write. |
| `from_date` | `date` | unchanged | |
| `to_date` | `date` | **meaning clarified** | Latest date with a persisted row of *any* provenance (ingested or projected) — unchanged field, now explicitly documented as the "last ingested-or-rebuilt date" the staleness check compares against. |
| `sub_accounts` | `list[str]` | unchanged | |
| `ingested_at` | `datetime` | unchanged | Timestamp of the most recent *ingestion* (ledger upload). Not updated by a rebuild. |
| `rebuilt_at` | `datetime \| None` | **new** | Timestamp of the most recent rebuild write. `None` if the ladder has never been rebuilt, only ingested. |

### CapitalMeta (`app/repositories/capital_repository.py`)

| Field | Type | Change | Notes |
|---|---|---|---|
| `account_name` | `str` | unchanged | |
| `checksum` | `str` | unchanged | |
| `row_count` | `int` | unchanged | |
| `from_date` | `date` | unchanged | |
| `to_date` | `date` | **meaning clarified** | Same clarification as `AccountMeta.to_date` above. |
| `ingested_at` | `datetime` | unchanged | |
| `rebuilt_at` | `datetime \| None` | **new** | Same meaning as `AccountMeta.rebuilt_at`. |

### Position ladder rows (stored in `ladder.xlsx`, read via `LadderRepository`)

| Column | Type | Change | Notes |
|---|---|---|---|
| `date`, `sub_account`, `book_cost`, `quantity`, `total_income` | existing | unchanged | |
| `price`, `market_value`, `portfolio_weight` | existing | unchanged | May be `null` for a row written by a partial rebuild (R7/R8) where pricing could not be sourced for that date. |
| `position_return`, `weighted_position_return` | existing | unchanged | `null` wherever `price` is `null` for the row (cannot compute a return without a price). |
| `provenance` | `"ingested" \| "projected"` | **new** | Set to `"ingested"` for every row written by `IngestionService` from an uploaded ledger; `"projected"` for every row written by the new rebuild path. A later ingestion that supersedes a projected span (R5) rewrites those rows' `provenance` back to `"ingested"`. This column, together with `AccountMeta.rebuilt_at`, is the concrete implementation of spec.md's "Rebuild Coverage" key entity — no separate coverage-range record is persisted (see research.md R4). |

### Capital ledger rows (stored in `capital.xlsx`, read via `CapitalRepository`)

| Column | Type | Change | Notes |
|---|---|---|---|
| `date`, `capital`, `income`, `book_value` | existing | unchanged | Capital rebuild rows always carry forward the last known values — never `null` (R3: no external pricing dependency, so total/partial unavailability does not apply to this resource). |
| `provenance` | `"ingested" \| "projected"` | **new** | Same meaning as the position ladder's column; also implements spec.md's "Rebuild Coverage" entity for this resource. |

## New concepts (not separately persisted entities, but new runtime constructs)

### Rebuild target

Computed per request, per resource, not persisted as its own record:

- `last_known_date`: `AccountMeta.to_date` or `CapitalMeta.to_date` as read at the start of the request.
- `rebuild_target_end`: the prior business day relative to `today` (reusing `TimeseriesDateResolver`'s existing business-day helpers — see research.md R1).
- A rebuild is required iff `resolved_end > last_known_date`, in which case the gap to fill is `(last_known_date, rebuild_target_end]`.

### Rebuild lock key

`(account_name, resource)` where `resource ∈ {"ladder", "capital"}` — the registry key for the in-process `threading.Lock` described in research.md R6. Not persisted; scoped to process lifetime, matching the existing `ThreadRunScheduler` pattern.

## Validation rules

- `rebuild_target_end` MUST NOT exceed the prior business day relative to `today` (FR-003); this is enforced by construction (it is derived from, not supplied by, the request).
- A rebuild MUST NOT run when `resolved_end <= last_known_date` for the resource being read (FR-001/FR-002 only trigger on an actual gap).
- `provenance` MUST be set on every row at write time; no row written by this feature's code paths may omit it.
- A capital-ladder row's value columns (`capital`, `income`, `book_value`) MUST NOT be `null` (R3) — only position-ladder price-derived columns may be `null`, and only for `provenance = "projected"` rows affected by partial pricing unavailability (R7/R8).

## State transitions

```
[no row for date D]
      │ ingestion (LedgerExpander over an uploaded ledger that reaches D)
      ▼
[row at D, provenance=ingested]
      │ rebuild extends the ladder past D's account but D itself is untouched
      ▼
(ingested rows are never rewritten by a rebuild)

[no row for date D, D > last_known_date]
      │ rebuild (gap-fill, positions held constant + fresh pricing)
      ▼
[row at D, provenance=projected]
      │ a later ledger ingestion whose own date range includes D
      ▼
[row at D, provenance=ingested]   (R5 supersession: recomputed from the new ledger, not the old projection)
```
