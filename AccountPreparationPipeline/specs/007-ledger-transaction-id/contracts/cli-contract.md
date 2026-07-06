# CLI Contract: create_ledger

**Feature**: `007-ledger-transaction-id`
**Date**: 2026-06-10

## Command

```
pipeline.py create_ledger INPUT_PATH OUTPUT_PATH
```

No new CLI arguments are introduced by this feature. The `OUTPUT_PATH` argument acquires a
dual role: it is both the write destination and (if the file already exists) the source of
prior Transaction IDs for stable re-run assignment.

---

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `INPUT_PATH` | Path (positional) | Yes | Path to an existing consolidated journal XLSX. Must exist and be readable. |
| `OUTPUT_PATH` | Path (positional) | Yes | Path for the ledger output XLSX. Parent directory must exist. If the file already exists, it is read for prior Transaction IDs before being overwritten. |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — ledger written to `OUTPUT_PATH`. |
| 2 | Invalid arguments — `INPUT_PATH` does not exist or journal is malformed. |

**Note**: If `OUTPUT_PATH` exists but cannot be read (locked, corrupted), the mode logs a
WARNING and treats it as absent (first-time run), then overwrites it with exit code 0.

---

## Output Schema

The ledger XLSX has the following column layout (left to right):

| Column | Type | Excel Format |
|--------|------|--------------|
| Transaction ID | Text | `@` (explicit text — preserves zero-padding and hyphen) |
| date | Date | Default |
| account | Text | Default |
| sub_account | Text | Default |
| action | Text | Default |
| reference | Text | Default |
| Account Value | Number | `#,##0.00` |
| Account Quantity | Number | `#,##0.0000` |
| Transaction Value | Number | `#,##0.00` |
| Transaction Quantity | Number | `#,##0.0000` |

---

## Re-Run Behaviour

When `OUTPUT_PATH` already exists:

1. The mode reads the existing file's `Transaction ID`, `date`, `account`, `sub_account`, and
   `reference` columns to build a `PriorIDMap` keyed by `(date, account, sub_account, reference)`.
2. If the file exists but lacks a `Transaction ID` column (ledger from a pre-feature run), the
   mode logs a WARNING and proceeds as a first-time run.
3. The engine receives the `PriorIDMap` and assigns stable IDs to known rows; new rows receive
   insertion IDs.
4. The output file is overwritten atomically.

---

## Invariant Contract

For any output ledger produced by `create_ledger`:

1. When rows are sorted by `Transaction ID` ascending, for every `(account, sub_account)` group
   and every row `i > 1` in that group:
   ```
   Account Value[i] = Account Value[i-1] + Transaction Value[i]
   ```
2. On an idempotent re-run (identical input journal, same `OUTPUT_PATH`), all `Transaction ID`
   values are unchanged.
