# Research: Lodgement Deposit and Trade Offsets

**Feature**: 013-lodgement-offsets  
**Date**: 2026-07-02  
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## Existing Offset Architecture

### How buy/sell/dividend offsets work today

The offset pipeline is three modules:

| Module | Role |
|--------|------|
| `offset_generator.py` — `OffsetGenerator` | Generates synthetic cash rows for buy/sell/dividend events |
| `journal_store.py` — `JournalStore.missing_offset_trades()` | Detects rows missing their offset partner (backfill trigger) |
| `consolidator.py` — `ConsolidationEngine.run()` | Orchestrates: parse → merge → rectify → backfill |

`OffsetGenerator.generate()` currently accepts a `list[JournalEvent]` and returns one `TRADING` row per `BUY`/`SELL`/`DIVIDEND` event via `_make_offset()`. `_make_offset` sets:
- `action = TRADING`
- `sub_account = CASH_SUB_ACCOUNT`
- `reference = event.reference + OFFSET_SUFFIX`
- `value = event.value` (mirrors — same sign as original trade)
- `quantity = event.value` (cash quantity convention)

`missing_offset_trades()` checks only `{BUY, SELL, DIVIDEND}`. Each lodgement needs TWO companions instead of one, requiring both an extension to `OffsetGenerator` and a more complex missing-companion check.

---

## Decision 1: Deposit Companion Reference Format

**Problem**: Spec FR-003 says the deposit companion uses the same reference as the lodgement (e.g., `L003538235`). But `_is_transaction_reference()` in `journal_store.py` currently only recognises `B\d+`, `S\d+`, and `*-offset`. An unrecognised reference falls back to the `(date, action, value)` dedup key — which collides if two lodgements on the same date share the same value.

**Decision**: Introduce `DEPOSIT_SUFFIX = "-deposit"` in `constants.py`. The deposit companion reference becomes `{lodgement_reference}-deposit` (e.g., `L003538235-deposit`).

**Rationale**: This gives each deposit companion a unique, stable, machine-readable reference that maps 1:1 to its lodgement. It is still clearly distinguishable from the trading companion (`-offset` suffix) — the spec's stated reason for wanting a distinct reference is preserved. Dedup can use the primary key `(date, reference)` rather than the fragile fallback.

**Alternatives considered**:
- Same reference as lodgement (original FR-003): Rejected — two rows share the same date+reference, breaking the primary-key dedup path; fallback key `(date, action, value)` collides when two lodgements on the same date share a value.
- Separate `action` column in dedup key: Rejected — would require deeper changes to the `merge()` loop and add complexity beyond the feature scope.

**Spec impact**: FR-003 wording changes: "same reference" → "reference derived from the lodgement reference with a `-deposit` suffix." Intent (distinguishable from trading companion) is unchanged.

---

## Decision 2: Deposit Companion Value Sign

**Decision**: Deposit companion `value = -(lodgement.value)` — negated.

- Lodgement value = -£2,288.89 → deposit companion value = +£2,288.89
- This satisfies SC-003: `lodgement.value + deposit.value = 0` (cash balance is zero for the pair).

**Rationale**: Consistent with FR-001 and the user description ("the value of this line is the same as the lodgement but negative × -1").

---

## Decision 3: Trading Companion Value Sign

**Problem**: FR-002 says "negation of lodgement value" but also "same sign logic as buy trade offset." These conflict:
- "Negation of lodgement value" → trading companion value = +£2,288.89 (opposite sign to lodgement)
- "Same sign logic as buy trade offset" → buy value is -£1,000, trading offset value is -£1,000 (mirrors, same sign)

**Decision**: Trading companion `value = event.value` — mirrors the lodgement (same sign), consistent with how `_make_offset` works for buy/sell.

**Rationale**: The phrase "same logic as the trading action for buy/sell" from the user's original description is the authoritative intent. The `_make_offset` contract sets `value = event.value` (no negation) for all existing actions. Deviating for lodgements would add a special case with no accounting justification — the trading companion represents the "cash equivalent going out to acquire the securities," matching the direction of the lodgement itself.

---

## Decision 4: Companion Row Quantity

**Decision**: Both companion rows have `quantity = None`.

**Rationale**: Spec FR-008 is explicit. Deposit rows in the journal have no quantity (they represent a monetary amount, not a unit count). The trading companion for a lodgement follows the same reasoning — there is no meaningful "quantity of cash units." This differs from buy/sell trading offsets (which set `quantity = event.value` as a cash-quantity convention), but the spec intentionally excludes this convention for lodgement companions.

---

## Decision 5: Extending `_is_transaction_reference`

**Decision**: Add two conditions to `_is_transaction_reference()`:
1. `RE_LODGEMENT.match(reference)` — so lodgement rows themselves use primary key `(date, reference)` dedup (fixes a latent bug where two same-date/same-value lodgements would incorrectly be treated as duplicates)
2. `reference.endswith(DEPOSIT_SUFFIX)` — so deposit companions use primary key dedup

**Rationale**: Without recognising `L\d+`, the lodgement event itself uses the fallback `(date, action, value)` key — a latent correctness bug from Feature 012 that Feature 013 should fix opportunistically. Recognising `-deposit` suffix follows the same pattern already established for `-offset`.

---

## Decision 6: Extending `missing_offset_trades()`

**Decision**: `missing_offset_trades()` returns a row for a lodgement if EITHER companion is missing:
- Trading companion: `{ref}-offset` absent from TRADING rows
- Deposit companion: `{ref}-deposit` absent from DEPOSIT rows

When `OffsetGenerator` generates companions for a partially-complete lodgement (one companion already exists), the `merge()` dedup prevents re-insertion of the already-present companion. The missing companion is inserted. This handles both the full-backfill and partial-backfill cases correctly.

---

## Decision 7: No Changes to `rectify_offsets()`

**Decision**: Do not extend `rectify_offsets()` to handle lodgement companions in this feature.

**Rationale**: `rectify_offsets()` corrects stale offset values when a trade's value changes. In practice, lodgement values in HL CSV exports do not change after being written. Extending rectification is out of scope for Feature 013 and not referenced in the spec. It can be added in a future feature if needed.

---

## Decision 8: `OffsetGenerator` Companion Generation

**Decision**: Add `_make_lodgement_deposit()` and `_make_lodgement_trading()` private methods. Update `generate()` to emit TWO events per lodgement via a list comprehension extension:

```python
# Pseudocode
for e in events:
    if e.action in (BUY, SELL, DIVIDEND):
        yield _make_offset(e)          # 1 trading companion
    elif e.action is LODGEMENT:
        yield _make_lodgement_deposit(e)   # deposit companion
        yield _make_lodgement_trading(e)   # trading companion
```

`generate_from_df()` requires no changes — it delegates to `generate()`.

---

## File Change Summary

| File | Change |
|------|--------|
| `src/modes/consolidate_journals/constants.py` | Add `DEPOSIT_SUFFIX = "-deposit"` |
| `src/modes/consolidate_journals/journal_store.py` | Import `RE_LODGEMENT`, `DEPOSIT_SUFFIX`; extend `_is_transaction_reference()`; extend `missing_offset_trades()` |
| `src/modes/consolidate_journals/offset_generator.py` | Import `DEPOSIT_SUFFIX`, `ActionType.DEPOSIT`; add lodgement companion methods; extend `generate()` |
| `tests/unit/consolidate_journals/test_offset_generator.py` | New `TestLodgementCompanions` class (12–15 tests) |
| `tests/unit/consolidate_journals/test_journal_store.py` | New lodgement dedup and backfill test methods |
| `tests/features/consolidate_journals.feature` | 3 new BDD scenarios for Feature 013 |
| `tests/features/steps/consolidate_journals_steps.py` | New @given and @then steps; new @scenario bindings |

No changes to: `hl.py` (parser), `schema.py`, `consolidator.py`, `mode.py`.
