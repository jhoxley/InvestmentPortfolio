# Data Model: Ledger Transaction ID

**Feature**: `007-ledger-transaction-id`
**Date**: 2026-06-10

## Entities

### TransactionID (Value Object)

A formatted string identifier for a single ledger row.

| Field | Type | Constraints |
|-------|------|-------------|
| `value` | `str` | Pattern `\d{5}-\d{3}`, e.g. `00001-001`. Zero-padded. Stored as text string. |
| `prefix` | `int` | 1 – 99 999 (derived from `value`). Encodes canonical row position on first run. |
| `suffix` | `int` | 1 – 999 (derived from `value`). `1` for first-time rows; incremented for insertions. |

**Formatting rule**: `f"{prefix:05d}-{suffix:03d}"`

**Uniqueness**: Each Transaction ID is unique within a ledger. No two rows share the same `NNNNN-NNN` value.

---

### CanonicalSortKey (Tuple)

The composite key used to order ledger rows before ID assignment.

| Component | Source Column | Type | Sort Direction |
|-----------|---------------|------|----------------|
| `date` | `date` | `str` or `datetime` | Ascending |
| `account` | `account` | `str` | Ascending (alphabetical) |
| `sub_account` | `sub_account` | `str` | Ascending (alphabetical) |
| `reference` | `reference` | `str` | Ascending (alphabetical) |

**Note**: `account` is included to ensure rows from different accounts with the same
`sub_account` and `reference` on the same date are unambiguously ordered. Within each
`(account, sub_account)` group, rows are still in date order, so the cumulative invariant holds.

---

### PriorIDMap (Dict)

An in-memory lookup populated from an existing ledger output file (if present) on re-run.

| Key | Value |
|-----|-------|
| `tuple[str, str, str, str]` = `(date_str, account, sub_account, reference)` | `str` = Transaction ID, e.g. `"00001-001"` |

- Built by `CreateLedgerMode` before invoking `LedgerEngine`.
- Empty dict `{}` if no prior ledger exists (first-time run).
- Passed to `LedgerEngine.run(df, prior_ids=...)`.
- 4-tuple key ensures uniqueness across multi-account journals where the same `sub_account` and `reference` may appear under different `account` values.

---

### LedgerRow (Extended)

The existing ledger row extended with the Transaction ID column.

| Column | Type | Position | Notes |
|--------|------|----------|-------|
| `Transaction ID` | `str` | First (column A) | New. `NNNNN-NNN` format. Text-formatted in XLSX. |
| `date` | `date` | Second (column B) | Existing. |
| `account` | `str` | Third (column C) | Existing. |
| `sub_account` | `str` | Fourth (column D) | Existing. |
| `action` | `str` | Fifth (column E) | Existing. |
| `reference` | `str` | Sixth (column F) | Existing. |
| `Account Value` | `float` | Seventh (column G) | Existing. Number format `#,##0.00`. |
| `Account Quantity` | `float` | Eighth (column H) | Existing. Number format `#,##0.0000`. |
| `Transaction Value` | `float` | Ninth (column I) | Existing. Number format `#,##0.00`. |
| `Transaction Quantity` | `float` | Tenth (column J) | Existing. Number format `#,##0.0000`. |

---

## Classes

### TransactionIDAssigner

Single-responsibility class for assigning Transaction IDs to a sorted DataFrame.

**Location**: `src/modes/create_ledger/transaction_id.py`

```
TransactionIDAssigner
├── assign(df: DataFrame, prior_ids: dict[tuple, str]) -> Series[str]
│   First-time: returns ["00001-001", "00002-001", ..., "NNNNN-001"]
│   Re-run: stable IDs for known keys; insertion IDs for new keys
└── _parse_id(tid: str) -> tuple[int, int]
    Parses "NNNNN-NNN" → (prefix_int, suffix_int)
```

**State**: None (stateless). All inputs passed as parameters. Safe to instantiate once and reuse.

**Error conditions**:
- `ValueError`: suffix exceeds 999 for a given prefix (overflow)
- `ValueError`: prefix exceeds 99 999 on a new append (overflow, practically impossible)

---

## ID Assignment Rules

### First-Time Run (prior_ids is empty)

```
Row index (0-based) → Transaction ID
0 → "00001-001"
1 → "00002-001"
...
n → f"{n+1:05d}-001"
```

### Re-Run (prior_ids is non-empty)

After sorting all rows by canonical key `(date, sub_account, reference)`:

```
For each row in canonical order:
  IF row key in prior_ids:
    → Use prior Transaction ID (stable)
  ELSE (new row):
    Find preceding_prior = last row before this position with a prior ID
    IF preceding_prior exists:
      prefix = preceding_prior.prefix (5-digit int)
      max_existing_suffix = max suffix already assigned for this prefix
      new_suffix = max_existing_suffix + 1
      → f"{prefix:05d}-{new_suffix:03d}"
    ELSE (new row sorts before all existing rows):
      prefix = 1  (first prefix block)
      max_existing_suffix = max suffix already assigned for prefix=1
      new_suffix = max_existing_suffix + 1
      → f"00001-{new_suffix:03d}"

For new rows after ALL existing rows:
  max_prefix = max 5-digit prefix across all prior IDs
  → f"{max_prefix+1:05d}-001", f"{max_prefix+2:05d}-001", ...
```

### Idempotent Re-Run

If all row keys match prior_ids exactly, all Transaction IDs are identical to the prior run.
No mutation occurs.

---

## State Transitions

```
No prior ledger
      │
      ▼ first run
Ledger with "NNNNN-001" IDs (all suffixes -001)
      │
      ▼ re-run (no new rows)
Identical ledger (idempotent)
      │
      ▼ re-run (new rows between existing)
Ledger with original IDs intact + new "NNNNN-00N" rows (N ≥ 2)
      │
      ▼ re-run (new rows after existing)
Ledger with original IDs intact + new "(max+K)-001" rows
```
