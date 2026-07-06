# Data Model: Ledger Running Balance

**Feature**: 003-create-ledger
**Date**: 2026-06-03

## Entities

### InputJournal

The source data read from the consolidated journal XLSX produced by `consolidate_journals`. The
schema is fixed; this mode validates that all required columns are present before processing.

| Column | Type | Required | Description |
|---|---|---|---|
| `date` | string (YYYY-MM-DD) | Yes | Settlement date of the event |
| `account` | string | Yes | Free-text account name |
| `sub_account` | string | Yes | Investment or position name; `"Cash"` for cash events |
| `action` | string | Yes | Normalised action: one of `buy`, `sell`, `deposit`, `income`, `fee`, `withdrawal` |
| `reference` | string | Yes | Original transaction reference from the source journal |
| `value` | float | Yes | Transaction value in GBP |
| `quantity` | float \| blank | No | Number of units; blank for cash events |

**Validation rules**:
- All seven columns MUST be present; missing columns are a fatal input error (FR-013).
- `value` MUST be numeric for every row.
- `quantity` may be `NaN` / blank; blank is expected and valid for Cash rows.

---

### LedgerRow

A single row in the output ledger XLSX. One LedgerRow is produced for each InputJournal row.
The `action`, `reference`, `date`, `account`, and `sub_account` columns are carried through
unchanged. The `value` and `quantity` columns hold the cumulative running balance for the
position at that point in time.

| Column | Type | Description |
|---|---|---|
| `date` | string | Carried through from input |
| `account` | string | Carried through from input |
| `sub_account` | string | Carried through from input |
| `action` | string | Carried through from input |
| `reference` | string | Carried through from input |
| `value` | float (numeric cell) | Cumulative sum of adjusted values for this position up to and including this row |
| `quantity` | float (numeric cell) | Cumulative sum of adjusted quantities for this position up to and including this row |

**Output ordering**: sorted by (account, sub_account, date); within the same date for the same
position, input file row order is preserved.

---

### Position

The grouping key for cumulative balance calculation. All input rows sharing the same (account,
sub_account) pair belong to the same Position and share an independent running total.

| Field | Type | Description |
|---|---|---|
| `account` | string | The account name |
| `sub_account` | string | The investment name or `"Cash"` |

**Special rule**: Positions where `sub_account == "Cash"` apply an additional pre-adjustment step:
if the input `quantity` is blank, it is set to the input `value` before sign adjustments and
cumulation are applied.

---

### AdjustedEvent

An intermediate representation produced during computation — not persisted; used to describe the
sign-adjusted value and quantity for a single input row before cumulation.

| Field | Derivation |
|---|---|
| `adj_value` | `-value` if action is `buy` or `sell`; otherwise `value` |
| `adj_quantity` | `value` if sub_account is `"Cash"` and quantity is blank; then `-quantity` if action is `sell`; otherwise `quantity` |

**Computation sequence** (applied before groupby cumsum):

```
1. Cash rows (sub_account == "Cash") with blank quantity:
     quantity ← value

2. adj_value:
     buy or sell  → -value
     all others   →  value

3. adj_quantity:
     sell         → -quantity
     all others   →  quantity

4. Sort by (account, sub_account, date) — stable within date

5. For each (account, sub_account) group:
     value    ← cumsum(adj_value)
     quantity ← cumsum(adj_quantity)
```

---

## Entity Relationships

```
InputJournal (read from XLSX)
    │
    ├─ validated → all 7 columns present
    │
    ├─ grouped by ──────────────────► Position (account, sub_account)
    │                                     │
    │                                     └─ sorted by date (stable)
    │
    ├─ transformed → AdjustedEvent (sign adjustments per FR-004, FR-005, FR-006)
    │
    └─ cumsum per Position ─────────► LedgerRow (one per input row)
                                           │
                                           └─ written → Ledger XLSX (output)
```
