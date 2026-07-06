# Research: Dividend Cash Offset Entries

**Feature**: 010-dividend-cash-offset | **Date**: 2026-06-19

This feature is a surgical extension of existing code. There are no NEEDS CLARIFICATION items from
the spec. Research documents the four implementation decisions arising from reading the source.

---

## Decision 1 — Primary offset generation path

**Decision**: Add `ActionType.DIVIDEND` to the tuple filter in `OffsetGenerator.generate()`.

**Current code** (`offset_generator.py:18`):
```python
return [
    self._make_offset(e) for e in events if e.action in (ActionType.BUY, ActionType.SELL)
]
```

**Change**:
```python
return [
    self._make_offset(e) for e in events
    if e.action in (ActionType.BUY, ActionType.SELL, ActionType.DIVIDEND)
]
```

**Rationale**: `_make_offset` already produces the correct output — it copies `event.value` to
`offset.value` and `offset.quantity` (same-sign), sets `sub_account = CASH_SUB_ACCOUNT`, and
appends `OFFSET_SUFFIX` to `reference`. No logic in `_make_offset` needs to change.

**Alternatives considered**: None — this is the only code path that produces offset events.

---

## Decision 2 — Backfill scan must include dividend rows

**Decision**: Extend `JournalStore.missing_offset_trades()` to include `ActionType.DIVIDEND` in the
`trade_mask` filter.

**Current code** (`journal_store.py:58`):
```python
trade_mask = self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value})
```

**Change**:
```python
trade_mask = self._df["action"].isin(
    {ActionType.BUY.value, ActionType.SELL.value, ActionType.DIVIDEND.value}
)
```

**Rationale**: The backfill pass in `ConsolidationEngine.run()` calls `missing_offset_trades()` to
find events that have no corresponding offset row, then generates the missing offsets. If
`missing_offset_trades()` does not include dividend rows in its scan, pre-existing dividend events
(present in the journal before Feature 010 was deployed) will never receive backfilled offsets.
This would break FR-006.

**Alternatives considered**: Adding dividend backfill as a separate method in `JournalStore` —
rejected because it would duplicate the existing pattern without benefit; one generalised method
is cleaner and keeps the `ConsolidationEngine` unchanged.

---

## Decision 3 — Deduplication key for dividend offset references

**Problem**: `_is_transaction_reference()` currently returns True only for `[BS]\d+` references
and `[BS]\d+-offset` references (via `RE_OFFSET = re.compile(r"^[BS]\d+-offset$")`). Dividend
offset references (`"ST DIV-offset"`, `"OVR CR-offset"`, etc.) do not match this regex.

When `_is_transaction_reference` returns False, the `merge()` method uses the fallback dedup key
`(date + action + value)` instead of `(date + reference)`. For dividend offsets this is wrong:
two different dividend types on the same date with the same value (e.g., a £64.71 ST DIV and a
£64.71 OVR CR offset) would be treated as duplicates.

**Decision**: Replace the `RE_OFFSET.match(reference)` check in `_is_transaction_reference()` with
`reference.endswith(OFFSET_SUFFIX)`:

```python
def _is_transaction_reference(reference: str) -> bool:
    return bool(
        RE_BUY.match(reference)
        or RE_SELL.match(reference)
        or reference.endswith(OFFSET_SUFFIX)
    )
```

This correctly maps all `-offset` references (buy, sell, and dividend) to the `(date + reference)`
dedup key.

**Consequence**: `RE_OFFSET` is no longer used in `journal_store.py`. It must be removed from the
import and from `constants.py` to satisfy Ruff's unused-import gate (`F401`) and unused-variable
gate. Removal is safe — `RE_OFFSET` has no usages outside `journal_store.py`.

**Alternatives considered**:
- Widen `RE_OFFSET` to `re.compile(r".+-offset$")` — workable but less readable; the regex
  ceases to document intent (it previously encoded "buy or sell offset").
- Use fallback dedup `(date + action + value)` and accept wrong deduplication — rejected; breaks
  SC-001 when same-value dividends occur on the same date.

---

## Decision 4 — Extend rectify_offsets() to cover dividend events

**Decision**: Include `ActionType.DIVIDEND.value` in the `trade_mask` in `rectify_offsets()`.

**Current code** (`journal_store.py:75`):
```python
trade_mask = self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value})
```

**Change**:
```python
trade_mask = self._df["action"].isin(
    {ActionType.BUY.value, ActionType.SELL.value, ActionType.DIVIDEND.value}
)
```

**Rationale**: `rectify_offsets()` corrects offset rows whose stored value diverges from the
originating trade value (e.g., after a trade amendment). While dividend values are stable in
practice, consistent treatment across all offset-generating action types prevents a class of
latent bugs where a dividend re-statement would leave a stale offset uncorrected. The change is
a one-line extension of the existing frozenset.

**Alternatives considered**: Leave `rectify_offsets()` unchanged — acceptable in practice but
inconsistent with the extension principle; rejected in favour of uniform treatment.

---

## No-change decisions

| Area | Decision |
|------|----------|
| `_make_offset()` in `offset_generator.py` | Unchanged — value/quantity copy logic already correct for same-sign dividends |
| `ConsolidationEngine.run()` in `consolidator.py` | Unchanged — calls `missing_offset_trades()` which is extended; no new call sites needed |
| `schema.py` | Unchanged — `ActionType.DIVIDEND` was added in Feature 009; `ActionType.TRADING` already used for offsets |
| `constants.py` | Only `RE_OFFSET` removed; all other constants unchanged |
| `create_ledger` mode | Unchanged — already handles `trading` action type correctly |
| CLI interface | Unchanged — no new parameters |
| Journal XLSX schema | Unchanged — no new columns |
