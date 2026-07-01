# Data Model: Dividend Cash Offset Entries

**Feature**: 010-dividend-cash-offset | **Date**: 2026-06-19

## No new entities

This feature introduces no new data entities, columns, or schema changes.

The `JournalEvent` dataclass (`schema.py`) is unchanged. The `ActionType.DIVIDEND` enum member
was added in Feature 009 and is already persisted as the string `"dividend"` in the journal XLSX.
The `ActionType.TRADING` enum member (used for all offset rows, including the new dividend offsets)
is also unchanged.

## Affected behaviour (not schema)

The only model-level change is that `OffsetGenerator` and `JournalStore` now treat `dividend`
events identically to `buy` and `sell` events when generating and backfilling Cash offset rows.
The resulting offset rows in the journal carry the same fields as existing buy/sell offsets:

| Field        | Value for dividend offset                          |
|--------------|----------------------------------------------------|
| `date`       | Same as originating dividend event date            |
| `account`    | Same as originating dividend event account         |
| `sub_account`| `"Cash"` (constant `CASH_SUB_ACCOUNT`)             |
| `action`     | `"trading"` (`ActionType.TRADING`)                 |
| `reference`  | Dividend reference + `"-offset"` (e.g. `"ST DIV-offset"`) |
| `value`      | Same as dividend event value (positive)            |
| `quantity`   | Same as `value` (Cash quantity mirrors value)      |

## Reference

- `src/modes/consolidate_journals/schema.py` — `ActionType`, `JournalEvent`
- `src/modes/consolidate_journals/constants.py` — `CASH_SUB_ACCOUNT`, `OFFSET_SUFFIX`
