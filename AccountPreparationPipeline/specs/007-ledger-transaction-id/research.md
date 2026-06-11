# Research: Ledger Transaction ID

**Feature**: `007-ledger-transaction-id`
**Date**: 2026-06-10

## Findings

### 1. Current LedgerEngine Sort Key

**Question**: What sort order does the engine currently apply, and is it compatible with the canonical
Transaction ID sort `(date, account, sub_account, reference)`?

**Finding**: `LedgerEngine.run()` (`src/modes/create_ledger/engine.py:55`) sorts by
`["account", "sub_account", "date"]` with `kind="stable"` before computing cumsums.

**Decision**: Replace this sort with `["date", "account", "sub_account", "reference"]` — the canonical
Transaction ID sort order.

**Rationale**: The `groupby(["account", "sub_account"])` cumsum is order-aware within each group,
not globally. Pandas `groupby` collects all matching rows regardless of their position in the
DataFrame, so after a global sort by `(date, account, sub_account, reference)`, rows within each
`(account, sub_account)` group are still in date order (date is the primary key), preserving
cumsum correctness. This single-pass sort both establishes the canonical order and feeds the
cumsum in one step.

**Alternatives considered**:
- Sort by `(account, sub_account, date)` for cumsum then re-sort by `(date, account, sub_account, reference)`
  for Transaction ID — rejected: two sorts, more code, same result since `groupby` is order-agnostic.

---

### 2. Prior Ledger Reading — Re-Run ID Preservation

**Question**: Does `CreateLedgerMode` currently read the existing output file on re-run?

**Finding**: `CreateLedgerMode.execute()` (`src/modes/create_ledger/mode.py`) is currently
write-only. It does not read `output_path` before writing. Line 62 reads only `input_path`.

**Decision**: Add a `_load_prior_ids()` helper in `mode.py` that reads `output_path` if it
exists, extracts the `Transaction ID`, `date`, `sub_account`, and `reference` columns, and
returns a `dict[tuple[str, str, str], str]` mapping `(date, sub_account, reference) → transaction_id`.
Pass this dict into `LedgerEngine.run()` as `prior_ids`.

**Rationale**: `output_path` is already in scope in `execute()`. Reading it there keeps the
engine pure (stateless, no file I/O) and the mode responsible for I/O concerns (SRP).

**Alternatives considered**:
- Engine reads prior ledger directly — rejected: violates SRP; engine becomes impure, harder to test.
- New `PriorLedgerReader` class — rejected: over-engineering for a two-line read; a module-level
  helper function is sufficient.

---

### 3. LEDGER_COLUMNS Index Arithmetic in mode.py

**Question**: Adding `Transaction ID` to `LEDGER_COLUMNS` at index 0 affects
`LEDGER_COLUMNS.index(col_name) + 1` used for cell number formatting. Is it safe?

**Finding**: `mode.py:79` computes `col_idx = LEDGER_COLUMNS.index(col_name) + 1` where the +1
is the 1-based Excel column index. Currently "Account Value" is at list index 5 → col_idx 6
(column F). After adding "Transaction ID" at index 0, "Account Value" moves to list index 6 →
col_idx 7 (column G). Excel also shifts all numeric columns right by one, so col_idx 7 correctly
points to "Account Value" — the arithmetic is self-consistent.

**Decision**: Add `LEDGER_COL_TRANSACTION_ID = "Transaction ID"` as the first element of
`LEDGER_COLUMNS`. Existing formatting code requires no change.

**Rationale**: The +1 formula accounts for the 1-based column index relative to the DataFrame
column order, which is always in sync with `LEDGER_COLUMNS` order. No magic number correction
needed.

---

### 4. Transaction ID Storage as Text in XLSX

**Question**: How to ensure `Transaction ID` values are stored as text (not numbers) in the XLSX
so Excel preserves zero-padding and the hyphen?

**Finding**: The value `"00001-001"` is a Python `str`. When pandas writes a string-typed column
via openpyxl, each cell is written as a string cell (`data_type='s'`). Excel does not re-interpret
string cells as numbers. Zero-padding and hyphens are preserved without any additional formatting.

**Decision**: Store Transaction IDs as `str` in the DataFrame. Additionally, set
`number_format = '@'` (Excel "Text" format) for the Transaction ID column in `mode.py` to
suppress any auto-format override in older Excel versions.

**Rationale**: Belt-and-suspenders approach: string dtype guarantees safe write; `@` number
format is the Excel convention for explicitly text-formatted columns.

---

### 5. TransactionIDAssigner — Algorithm

**Question**: How should the ID assignment algorithm handle new rows inserted between existing rows,
and new rows appended after all existing rows?

**Finding**: Rows are sorted by `(date, account, sub_account, reference)` globally. After sorting, each
row's canonical position is its 0-based index in the sorted DataFrame.

**Decision**: Implement `TransactionIDAssigner` as a stateless class with one public method
`assign(df, prior_ids) -> pd.Series`:

**First-time run** (`prior_ids` is empty/None):
- For row at index `i` (0-based): `f"{i+1:05d}-001"`

**Re-run** (`prior_ids` is non-empty):
1. Build `prior_positions`: for each prior `(date, account, sub_account, reference)` key, record its
   transaction ID as a `(prefix_int, suffix_int)` pair.
2. Sort all rows by canonical key. Walk through them in order, maintaining a pointer into the
   list of prior IDs sorted by their `(prefix_int, suffix_int)`.
3. For each row:
   - If its key is in `prior_ids`: use the prior ID.
   - If it's a new row: find the preceding row that has a prior ID (the last prior-ID row
     seen before this position). Take its 5-digit prefix. Find the maximum suffix already
     assigned for that prefix. Assign `prefix-{max_suffix + 1:03d}`.
   - If no prior-ID row precedes (new row sorts before all existing rows): assign prefix `00001`
     with the next available suffix for that prefix. This is a known limitation documented in
     Edge Cases.
4. For new rows that sort after all existing rows: find the maximum 5-digit prefix in all prior
   IDs, increment it by 1, assign suffix `-001`.

**Overflow guards**: If suffix reaches 999, raise `ValueError`. If prefix reaches 99999 and
a new row needs `99999` suffix overflow, raise `ValueError`.

---

### 6. Impact on Existing Tests

**Question**: Adding `Transaction ID` as a new column changes `LEDGER_COLUMNS` and the sort
order — which existing tests break?

**Finding**: 
- `test_engine.py` — all tests that check specific column values or DataFrame shape will see
  a new `Transaction ID` column. Tests asserting `df.columns == LEDGER_COLUMNS` need no change
  (they'll pick up the updated constant). Tests asserting specific column values must include
  the Transaction ID expectation.
- `test_create_ledger_e2e.py` — integration tests that check `out_df["Account Value"]` by
  position (`.iloc[0]`) may break if row order changes due to the new sort. Tests using named
  columns (`out_df[out_df["sub_account"] == "Cash"]`) are safe.
- The output row order changes from `(account, sub_account, date)` to `(date, account, sub_account, reference)`.
  Tests relying on implicit row order need updating.

**Decision**: Update all tests that rely on the old sort order. Document specific row indices
that change in the tasks.md.

---

## Summary Decision Table

| Decision | Choice | Alternatives Rejected |
|----------|--------|-----------------------|
| Sort key | `(date, account, sub_account, reference)` | Two-pass sort |
| Prior ledger I/O | In `mode.py` helper | In engine; separate class |
| LEDGER_COLUMNS | Transaction ID at index 0 | Separate constant list |
| Text storage | str dtype + `@` number_format | Explicit prefix trick |
| Assigner design | Stateless class, `assign(df, prior_ids)` | Module-level function |
| New-row-before-all | Assign prefix `00001` + next suffix | Error/abort |
