# Research: Ledger Running Balance

**Feature**: 003-create-ledger
**Date**: 2026-06-03

## Decision 1: Computation Approach — Cumulative Sums

**Decision**: Use `pandas` groupby + cumulative sum (`cumsum`) to compute running balances per
(account, sub_account) position.

**Rationale**:
- `pandas` is already a declared runtime dependency (added for `consolidate_journals`); no new
  dependency is required.
- `DataFrame.groupby(...).cumsum()` computes per-group running totals in a single vectorised
  operation — no Python-level loops over rows.
- The sign-adjustment step (negate buy/sell values; negate sell quantities; copy value to
  quantity for Cash) maps cleanly to pandas `loc`-based column mutations before the cumsum.

**Alternatives considered**:
- Python-level row iteration with a running accumulator dict: Correct but O(N) Python overhead
  for each row; unnecessary given pandas is available. Rejected.
- `itertools.accumulate`: Stdlib but requires converting to/from lists and handling groups
  manually. More complex than groupby cumsum. Rejected.

---

## Decision 2: Row Ordering — Stable Sort Within Date

**Decision**: Sort the DataFrame by `(account, sub_account, date)` using a stable sort
(`kind="stable"` in pandas) before computing cumulative sums. The output retains this sort order.

**Rationale**:
- FR-003 requires chronological order within each (account, sub_account) group, with groups
  ordered by account then sub_account.
- A stable sort preserves the original input row order for events sharing the same date within
  the same position, satisfying Assumption 5 from the spec.
- Stable sort is the pandas default when using `mergesort` / `stable` kind; it imposes no
  additional complexity.

**Alternatives considered**:
- Sorting by date only (no group key): Breaks the requirement that groups are ordered by
  account/sub_account. Rejected.
- Index-based sort: Unnecessary; pandas sort_values with stable kind is sufficient. Rejected.

---

## Decision 3: Sign Adjustment Implementation

**Decision**: Apply sign adjustments in two sequential pandas `loc` operations before groupby
cumsum. A dedicated `adj_value` and `adj_quantity` column are computed, cumulatively summed, then
written back to the `value` and `quantity` columns. The temporary columns are dropped before output.

**Rationale**:
- Keeping the adjustment separate from the cumsum makes each step independently testable and
  auditable (the intermediate state after adjustment but before cumulation can be verified).
- Pandas `loc`-based conditional assignment is vectorised and idiomatic.
- The sign rules for value (negate for buy/sell) and quantity (negate for sell; copy from value
  for Cash-blank) are independent transformations that compose without interference.

**Adjustment sequence**:
1. Cash rows with blank quantity: set `quantity = value` (before any sign adjustment)
2. `adj_value = -value` where action in `{buy, sell}`; else `adj_value = value`
3. `adj_quantity = -quantity` where action is `sell`; else `adj_quantity = quantity`
4. Sort by (account, sub_account, date) — stable
5. `value = groupby(account, sub_account)[adj_value].cumsum()`
6. `quantity = groupby(account, sub_account)[adj_quantity].cumsum()`
7. Drop `adj_value`, `adj_quantity`

---

## Decision 4: Test Data Strategy — Programmatic Fixtures

**Decision**: Create XLSX test input files programmatically within pytest fixtures using
`pandas.DataFrame.to_excel` into `tmp_path`, rather than committing binary XLSX fixtures.

**Rationale**:
- Binary XLSX files are opaque in version control; programmatic fixtures are readable and
  maintainable alongside the tests.
- The `consolidate_journals` test suite already uses `tmp_path` for XLSX round-trip tests,
  establishing this as the project convention.
- Programmatic fixtures can express precise numerical scenarios (exact values, blank cells,
  specific date sequences) that are difficult to verify by inspection in a binary file.

---

## Decision 5: Module Structure

**Decision**: Implement `create_ledger` as a single mode module with three files:
`mode.py` (ModeInterface), `engine.py` (LedgerEngine computation), `constants.py` (named
constants). No sub-package for parsers is needed (no fragment parsing required).

**Rationale**:
- The computation is a single transformation pipeline (read → adjust → sort → cumsum → write),
  simpler than `consolidate_journals`. A separate engine class isolates computation from CLI
  concerns and keeps `mode.py` thin, following the project pattern established by
  `consolidate_journals`.
- `constants.py` defines `CASH_SUB_ACCOUNT = "Cash"` locally rather than importing from
  `consolidate_journals/constants.py`, keeping the two modes decoupled. The value is a domain
  concept, not a detail owned by either mode.

---

## Decision 6: Output Numeric Formatting

**Decision**: Apply the same number formats as `consolidate_journals` to the output XLSX:
`#,##0.00` for `value` and `#,##0.######` for `quantity`, via `pd.ExcelWriter` + openpyxl cell
format application.

**Rationale**:
- SC-005 requires the output schema and cell types to match the input. Since the input was
  written by `consolidate_journals` with these formats, the output should be consistent.
- Reusing the same constants (`NUMBER_FORMAT_VALUE`, `NUMBER_FORMAT_QUANTITY`) from
  `consolidate_journals/constants.py` ensures the formats stay in sync. Importing these two
  format constants cross-module is acceptable because they represent a shared schema
  contract, not business logic.

---

## Resolved NEEDS CLARIFICATION

None — all design decisions derivable from the spec and the existing codebase conventions.
