# Data Model: Lodgement Deposit and Trade Offsets

**Feature**: 013-lodgement-offsets  
**Date**: 2026-07-02

---

## Entities

### JournalEvent (existing — no schema changes)

`JournalEvent` is the single data entity in the journal. Feature 013 generates two new `JournalEvent` instances per lodgement, both conforming to the existing frozen dataclass:

| Field | Type | Notes |
|-------|------|-------|
| `date` | `datetime.date` | Inherited from the lodgement event |
| `account` | `str` | Inherited from the lodgement event |
| `sub_account` | `str` | Always `CASH_SUB_ACCOUNT = "Cash"` for both companions |
| `action` | `ActionType` | `DEPOSIT` for deposit companion; `TRADING` for trading companion |
| `reference` | `str` | See companion reference rules below |
| `value` | `Decimal` | See companion value rules below |
| `quantity` | `Decimal \| None` | Always `None` for both companions (FR-008) |

---

## Companion Row Rules

### Deposit Companion

| Field | Rule | Example (lodgement L003538235, value = -2288.89) |
|-------|------|--------------------------------------------------|
| `action` | `ActionType.DEPOSIT` | `deposit` |
| `sub_account` | `CASH_SUB_ACCOUNT` | `Cash` |
| `reference` | `{lodgement.reference} + DEPOSIT_SUFFIX` | `L003538235-deposit` |
| `value` | `-lodgement.value` | `+2288.89` |
| `quantity` | `None` | — |

### Trading Companion

| Field | Rule | Example (lodgement L003538235, value = -2288.89) |
|-------|------|--------------------------------------------------|
| `action` | `ActionType.TRADING` | `trading` |
| `sub_account` | `CASH_SUB_ACCOUNT` | `Cash` |
| `reference` | `{lodgement.reference} + OFFSET_SUFFIX` | `L003538235-offset` |
| `value` | `lodgement.value` (mirrors) | `-2288.89` |
| `quantity` | `None` | — |

---

## New Constant

| Constant | Value | Location |
|----------|-------|----------|
| `DEPOSIT_SUFFIX` | `"-deposit"` | `src/modes/consolidate_journals/constants.py` |

---

## Deduplication Key Rules (updated)

`_is_transaction_reference(reference)` returns `True` (primary key = `date + reference`) for:

| Pattern | Example | Covers |
|---------|---------|--------|
| `RE_BUY.match` | `B12345` | Buy events |
| `RE_SELL.match` | `S67890` | Sell events |
| `RE_LODGEMENT.match` | `L003538235` | Lodgement events (fix for latent Feature 012 bug) |
| `endswith(OFFSET_SUFFIX)` | `B12345-offset` | Trading companions (buy/sell/lodgement) |
| `endswith(DEPOSIT_SUFFIX)` | `L003538235-deposit` | Deposit companions (lodgement) |

All other references (deposits, income, fees, dividends) use fallback key `(date, action, value)`.

---

## Invariant

**SC-003**: For every lodgement event, the sum of lodgement value and deposit companion value is zero:

```
lodgement.value + deposit_companion.value = 0
(-2288.89)     + (+2288.89)              = 0 ✓
```

The trading companion does not participate in this balance check — it mirrors the lodgement as a trade accounting offset (consistent with buy/sell trading offsets).
