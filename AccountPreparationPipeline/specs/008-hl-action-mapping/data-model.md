# Data Model: HL Action Mapping

## Overview

No new entities or schema changes. This feature extends the reference→action classification table used by the HL fragment parser. The `ActionType` enum and `JournalEvent` dataclass are unchanged.

---

## Reference → Action Mapping Table

The complete mapping rules for `_map_action(reference, description)`, including new entries (marked **NEW**):

| Reference Pattern | Match Type | Action | Sub-account |
|---|---|---|---|
| `^B\d+$` | Regex | `buy` | From description |
| `^S\d+$` | Regex | `sell` | From description |
| `"Deposit"` (exact) | Case-sensitive set | `deposit` | `Cash` |
| `"BACS"` or `^BACS.*` | Set + prefix | `deposit` | `Cash` |
| `"contrib"` | Case-insensitive exact | `deposit` | `Cash` |
| `"CARD WEB"` | **NEW** Case-insensitive exact | `deposit` | `Cash` |
| `"FPC"` | **NEW** Case-insensitive exact | `deposit` | `Cash` |
| `"transfer"` + income in description | Case-insensitive exact + desc | `income` | `Cash` |
| `"transfer"` (no income in description) | Case-insensitive exact | `deposit` | `Cash` |
| `^URI.*` | Case-insensitive prefix | `income` | `Cash` |
| `"INTEREST"` | Case-insensitive set | `income` | `Cash` |
| `"RDP CR"` | Case-insensitive set | `income` | `Cash` |
| `"COMMISSION"` | **NEW** Case-insensitive exact | `income` | `Cash` |
| `"MANAGE FEE"` | Case-insensitive exact | `fee` | `Cash` |
| *(anything else)* | — | **ParseError** | — |

### Sub-account Assignment Rule

All actions in `CASH_ACTION_TYPES = {"deposit", "fee", "income"}` receive `sub_account = "Cash"`.
All other actions (`buy`, `sell`, `trading`) derive `sub_account` from the `Description` column.

---

## Constants Changes

### `src/modes/consolidate_journals/constants.py`

#### New constants

```text
HL_DEPOSIT_REFERENCE_ALIASES: frozenset[str]
  Values (uppercase): {"CARD WEB", "FPC"}
  Purpose: Case-insensitive exact match for new deposit reference types.
  Comparison: ref.upper() in HL_DEPOSIT_REFERENCE_ALIASES

HL_INCOME_REFERENCES: frozenset[str]
  Values (uppercase): {"INTEREST", "RDP CR", "COMMISSION"}
  Purpose: Case-insensitive exact match for income reference types.
  Comparison: ref.upper() in HL_INCOME_REFERENCES
  Note: Consolidates existing "INTEREST" and "RDP CR" magic strings from _map_action.
```

#### Unchanged constants

- `HL_DEPOSIT_REFERENCES` — unchanged (`{"Deposit", "BACS"}`, case-sensitive set)
- `CASH_ACTION_TYPES` — unchanged (`{"deposit", "fee", "income"}`)
- `RE_BUY`, `RE_SELL`, `RE_OFFSET` — unchanged
- All other constants — unchanged

---

## Entities (unchanged)

### ActionType (StrEnum)

```
buy | sell | deposit | income | fee | withdrawal | trading
```

All values already exist. No new values required.

### JournalEvent (dataclass)

```
date: datetime.date
account: str
sub_account: str       ← "Cash" for deposit/income/fee; from description for buy/sell
action: ActionType
reference: str         ← preserved verbatim from the CSV (whitespace-trimmed)
value: Decimal
quantity: Decimal | None
```

No field changes.
