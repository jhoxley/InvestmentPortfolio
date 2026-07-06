# Data Model: Trade Cash Offset Entries

**Feature**: 004-trade-cash-offsets
**Date**: 2026-06-05

## Entities

### JournalEvent (extended)

Existing entity. One new valid `action` value is added.

| Field | Type | Description |
|-------|------|-------------|
| date | `datetime.date` | Settlement date of the trade |
| account | `str` | Account name (same as the originating trade) |
| sub_account | `str` | Always `"Cash"` for offset rows |
| action | `ActionType` | `"trading"` — the new value added by this feature |
| reference | `str` | Trade reference + `"-offset"` suffix (e.g. `"B12345-offset"`) |
| value | `Decimal` | Negated trade value (`-trade.value`) |
| quantity | `Decimal` | Negated trade value (`-trade.value`) — same as `value` for Cash rows |

**Constraint**: An offset row is always `sub_account = "Cash"` and `action = "trading"`.
No other combination of these two fields produces an offset row.

**Constraint**: The `quantity` field is always the negated `value` of the originating trade,
never the negated `quantity`. This is the Cash-position convention for all rows.

---

### ActionType (extended)

Existing enumeration in `src/modes/consolidate_journals/schema.py`.

| Value | Action | Source |
|-------|--------|--------|
| `"buy"` | Purchase of an investment | Fragment parser |
| `"sell"` | Sale of an investment | Fragment parser |
| `"deposit"` | Cash deposit or contribution | Fragment parser |
| `"income"` | Dividend or interest income | Fragment parser |
| `"fee"` | Platform or adviser fee | Fragment parser |
| `"withdrawal"` | Cash withdrawal | Fragment parser |
| **`"trading"`** | **Synthetic cash offset for a buy/sell trade** | **OffsetGenerator (new)** |

**Constraint**: `"trading"` is never emitted by any fragment parser. It is exclusively produced
by `OffsetGenerator`.

---

### OffsetGenerator (new)

A stateless computation component. Receives trade events (as a list or DataFrame) and returns
a list of synthetic offset `JournalEvent` objects, one per `buy` or `sell` event.

**Input**: `list[JournalEvent]` or `pd.DataFrame` of buy/sell rows lacking offsets  
**Output**: `list[JournalEvent]` — zero or more synthetic offset events

**Transformation rule**:

```
for each event in input:
  if event.action in {BUY, SELL}:
    yield JournalEvent(
      date       = event.date,
      account    = event.account,
      sub_account = CASH_SUB_ACCOUNT,      # "Cash"
      action     = ActionType.TRADING,
      reference  = event.reference + OFFSET_SUFFIX,   # e.g. "B12345-offset"
      value      = -event.value,
      quantity   = -event.value,           # not -event.quantity
    )
```

**Invariant**: `len(output) == count(event.action in {BUY, SELL} for event in input)`

---

## Constants (additions to existing `constants.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `OFFSET_SUFFIX` | `"-offset"` | Suffix appended to trade reference to form offset reference |
| `RE_OFFSET` | `re.compile(r"^[BS]\d+-offset$")` | Matches offset references for reference-based dedup |

### JournalStore — new query method

`missing_offset_trades()` is added to `JournalStore`. Returns a DataFrame of all `buy`/`sell`
rows for which no corresponding `<reference>-offset` row exists in the journal. Used by
`ConsolidationEngine` to drive the backfill pass on every run.

**Postcondition**: If `missing_offset_trades()` returns an empty DataFrame, the journal
already satisfies SC-001 and no write is needed.

## Deduplication Key Extension

The existing `_is_transaction_reference()` function in `journal_store.py` is extended to
return `True` for offset references:

```
_is_transaction_reference(ref) := RE_BUY.match(ref) OR RE_SELL.match(ref) OR RE_OFFSET.match(ref)
```

This ensures offset rows use `date + reference` as their dedup key (reliable, unique per
trade) rather than the fallback `date + action + value` (ambiguous when two trades share
the same date and value).
