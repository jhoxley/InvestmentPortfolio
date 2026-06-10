# Research: Ledger Transaction Columns

**Feature**: 005-ledger-transaction-columns
**Date**: 2026-06-08

## Decision 1: Transaction Value Computation — adj_value Before Cumsum

**Decision**: `Transaction Value[i]` is computed as `adj_value[i]` — the sign-adjusted per-row
value calculated before the cumulative sum. This is mathematically identical to
`Account Value[i] − Account Value[i−1]` (delta approach) but is simpler to implement because
`adj_value` is already computed in the engine as an intermediate column before being cumulatively
summed.

**Rationale**:
- `adj_value[i]` is already computed by the engine for every row. Retaining it (instead of
  dropping it) requires only renaming the column rather than a post-hoc differencing operation.
- The invariant proof is trivial: if `Account Value[i] = cumsum(adj_value[0..i])` and
  `Transaction Value[i] = adj_value[i]`, then
  `Account Value[i−1] + Transaction Value[i] = cumsum(adj_value[0..i−1]) + adj_value[i] = cumsum(adj_value[0..i]) = Account Value[i]`.
- No additional computation is required — just retain `adj_value` and `adj_quantity` as
  `Transaction Value` and `Transaction Quantity` instead of dropping them.

**Alternatives considered**:
- Post-hoc delta: compute `Transaction Value = Account Value[i] − Account Value[i−1]` using
  `groupby().diff()`. Correct, but requires a second pass over the data after cumsum. Rejected
  as more complex for no benefit.

---

## Decision 2: Output Column Schema — LEDGER_COLUMNS Constant

**Decision**: Introduce a `LEDGER_COLUMNS` constant in `src/modes/create_ledger/constants.py`
defining the nine-column output schema in order:
`["date", "account", "sub_account", "action", "reference", "Account Value", "Account Quantity",
"Transaction Value", "Transaction Quantity"]`

`JOURNAL_COLUMNS` (seven-column input schema from `consolidate_journals`) remains unchanged and
is still used for input validation in `LedgerEngine`. The output schema is entirely different from
the input schema and must be tracked separately.

**Rationale**:
- Keeping input and output schemas explicitly separate prevents accidental coupling — `LedgerEngine`
  continues to validate against the seven-column input, while `CreateLedgerMode` writes the
  nine-column output.
- Named column constants eliminate magic strings for the new column names.

**Column name constants added** (all in `create_ledger/constants.py`):
- `LEDGER_COL_ACCOUNT_VALUE: str = "Account Value"`
- `LEDGER_COL_ACCOUNT_QUANTITY: str = "Account Quantity"`
- `LEDGER_COL_TRANSACTION_VALUE: str = "Transaction Value"`
- `LEDGER_COL_TRANSACTION_QUANTITY: str = "Transaction Quantity"`

---

## Decision 3: Numeric Formatting for Transaction Columns

**Decision**: Apply `NUMBER_FORMAT_VALUE` to both `Account Value` and `Transaction Value`;
apply `NUMBER_FORMAT_QUANTITY` to both `Account Quantity` and `Transaction Quantity`.

**Rationale**:
- `Account Value` and `Transaction Value` are both monetary amounts (GBP, same precision).
- `Account Quantity` and `Transaction Quantity` are both unit counts (same precision).
- Consistent formatting within each domain makes the XLSX readable and prevents any cell
  appearing to have different precision to its counterpart.

**Impact on mode.py**:
- Currently, `mode.py` derives column indices via `JOURNAL_COLUMNS.index("value") + 1` and
  `JOURNAL_COLUMNS.index("quantity") + 1`. This approach breaks once columns are renamed.
- Replacement: use `LEDGER_COLUMNS.index(LEDGER_COL_ACCOUNT_VALUE) + 1` etc. to derive all
  four column indices.

---

## Decision 4: Empty DataFrame Handling

**Decision**: When the input journal has zero data rows (header only), `LedgerEngine.run()`
returns an empty DataFrame with `LEDGER_COLUMNS` as the column set (not `JOURNAL_COLUMNS`).

**Rationale**:
- The current code returns `df` early for empty input, which currently has `JOURNAL_COLUMNS`.
  After this feature, callers expect `LEDGER_COLUMNS`. Consistency between empty and non-empty
  return values is required for correct XLSX writing in `mode.py`.

---

## Decision 5: Test Update Scope — All Existing create_ledger Tests

**Decision**: All existing tests in `tests/unit/create_ledger/test_engine.py` and
`tests/features/steps/create_ledger_steps.py` that reference `["value"]` or `["quantity"]`
columns by name must be updated to `["Account Value"]` and `["Account Quantity"]`.
Additionally, `test_engine.py:test_output_columns_match_journal_columns` must be updated to
assert `LEDGER_COLUMNS` instead of `JOURNAL_COLUMNS`. New test assertions for
`Transaction Value` and `Transaction Quantity` are added alongside the updates.

**Rationale**:
- The column rename is a breaking change to all code that reads the ledger XLSX by column name.
  Tests are the first consumers to break.
- Updating tests in the same task as the implementation change ensures the Red-Green cycle
  is maintained (tests fail before implementation, pass after).

---

## Decision 6: Integration Test Coverage for the Invariant

**Decision**: The integration tests in `tests/integration/test_create_ledger_e2e.py` must
include a test that programmatically verifies the invariant
`Account Value[i] = Account Value[i−1] + Transaction Value[i]` holds for every row in the
output.

**Rationale**:
- SC-001 and SC-002 in the spec require exact numerical equality for the invariant. An integration
  test that programmatically loops over all rows and asserts the invariant provides a much stronger
  guarantee than spot-checking individual values.
