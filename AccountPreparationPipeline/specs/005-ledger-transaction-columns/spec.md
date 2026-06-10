# Feature Specification: Ledger Transaction Columns

**Feature Branch**: `005-ledger-transaction-columns`
**Created**: 2026-06-08
**Status**: Draft
**Input**: User description: "Extend the 'create_ledger' mode's output schema to rename two
existing columns: 'Value' to 'Account Value' and 'Quantity' to 'Account Quantity'. Introduce
two additional columns specific to the transaction on the given date. The first is 'Transaction
Value' which is the value (aggregated if multiple transactions on same date) of the event(s) on
that particular date. The second is 'Transaction Quantity' which has same behaviour but for the
quantity of the sub-account. A simple but important invariant must hold: The 'Account Value' from
the immediately previous row in the same account plus the 'Transaction Value' of the current row
should exactly match the 'Account Value' on the same row. An explainable lineage through a
sub-account must exist to explain why the account value or quantity increases or decreases."

## Clarifications

### Session 2026-06-08

- Q: When multiple events share the same (account, sub_account, date), should the output collapse them into one row per date or keep one row per event? → A: One row per event — row count preserved; Transaction Value is each event's individual contribution (per-row delta); `action` and `reference` columns carry through unchanged. The word "aggregated" in the feature description refers to the ability to sum Transaction Value entries for the same date using any analysis tool after the fact, not to row collapsing in the output.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ledger Includes Transaction Columns for Lineage (Priority: P1)

A user opens the ledger XLSX produced by `create_ledger` and wants to understand not just the
running balance of each position, but also what specific event caused each change. With the new
Transaction Value and Transaction Quantity columns, each row shows both the cumulative state
(`Account Value`, `Account Quantity`) and the individual event's contribution
(`Transaction Value`, `Transaction Quantity`). The user can filter or sum the transaction columns
to audit changes on any specific date.

**Why this priority**: The running balance alone tells you where you are; the transaction columns
tell you why. Without transaction detail, tracing an unexpected balance requires manual
back-calculation. This is the core value of the feature — lineage through each position.

**Independent Test**: Run `create_ledger` against a journal with a known sequence of buy, sell, and
deposit events. Open the output XLSX. For every row, verify that
`Account Value[prev row in group] + Transaction Value[this row] = Account Value[this row]`
(for the first row of each group, use 0 as the prior Account Value). Verify no column is missing.

**Acceptance Scenarios**:

1. **Given** a journal with a single buy event (e.g. £1 000 purchase), **When** `create_ledger`
   is run, **Then** the output row has `Account Value = −1 000`, `Transaction Value = −1 000`
   (both equal since it is the first event for that position).

2. **Given** a journal with two sequential buy events for the same position (£1 000 then £500),
   **When** `create_ledger` is run, **Then** the second row has
   `Account Value = −1 500`, `Transaction Value = −500`
   (the first row still has `Account Value = −1 000`, `Transaction Value = −1 000`).

3. **Given** a journal with a buy followed by a sell for the same position, **When** `create_ledger`
   is run, **Then** the sell row's `Transaction Value` reflects the sell's sign-adjusted contribution
   and the invariant `Account Value[row i−1] + Transaction Value[row i] = Account Value[row i]`
   holds.

4. **Given** a journal with events across two different positions, **When** `create_ledger` is run,
   **Then** each position's `Account Value` and `Transaction Value` are calculated independently —
   a transaction in one position does not affect the other's values.

5. **Given** a valid journal, **When** `create_ledger` is run, **Then** the output XLSX contains all
   nine columns in the defined order: `date`, `account`, `sub_account`, `action`, `reference`,
   `Account Value`, `Account Quantity`, `Transaction Value`, `Transaction Quantity`.

---

### User Story 2 — Invariant Holds Across All Event Types (Priority: P2)

A user runs `create_ledger` against a journal that includes buy, sell, deposit, income, fee, and
Cash offset events. For every row and every position, the transaction-to-account invariant holds
exactly. No event type is excluded or handled differently.

**Why this priority**: The invariant is the guarantee that the ledger is coherent. If even one row
violates it, the lineage is broken and the ledger cannot be trusted for reconciliation. This must
hold universally before the schema change is considered correct.

**Independent Test**: Run `create_ledger` against a journal containing all six action types
(buy, sell, deposit, income, fee, trading). For every output row, programmatically verify
`Account Value[i] - Account Value[i−1] = Transaction Value[i]` within each (account, sub_account)
group.

**Acceptance Scenarios**:

1. **Given** a Cash position with deposit events (blank quantity), **When** `create_ledger` is run,
   **Then** each row's `Transaction Value` and `Transaction Quantity` both reflect the deposit's
   value (after the Cash rule that sets quantity to value), and the invariant holds.

2. **Given** a position with a `trading` offset row (from the cash-offset feature), **When**
   `create_ledger` is run, **Then** the offset row's `Transaction Value` equals its sign-adjusted
   contribution and the invariant holds.

3. **Given** any journal with at least one row, **When** `create_ledger` is run, **Then** for every
   row in the output: `Account Value[i] − Account Value[i−1 in same group] = Transaction Value[i]`,
   where Account Value[i−1] is treated as 0 for the first row of each group.

---

### User Story 3 — Column Renames Are Backward-Compatible Within the Ledger (Priority: P3)

A user who previously used the `create_ledger` output re-runs the mode against the same input and
receives the updated schema. The existing five columns (`date`, `account`, `sub_account`, `action`,
`reference`) are unchanged. The two renamed columns (`Account Value`, `Account Quantity`) contain
the same values as the old `value` and `quantity` columns. The two new columns are additive.

**Why this priority**: Users may have downstream processes or reports that consume the ledger XLSX.
Renaming columns is a known-breaking change; this story ensures the rename is documented,
intentional, and the semantic content of the renamed columns is unchanged.

**Independent Test**: Run the old `create_ledger` (feature 003) and the new `create_ledger` on
the same input journal. Verify that the values in the `Account Value` column of the new output
exactly match the values in the `value` column of the old output, row-for-row.

**Acceptance Scenarios**:

1. **Given** a journal previously processed by feature 003's `create_ledger`, **When** the new
   `create_ledger` processes the same input, **Then** the `Account Value` column contains the same
   numerical values as the old `value` column and `Account Quantity` contains the same values as
   the old `quantity` column.

2. **Given** any valid input journal, **When** `create_ledger` is run, **Then** the output XLSX
   contains exactly nine columns (not seven); the five identity columns are present and unchanged;
   `Account Value` and `Account Quantity` are present; `Transaction Value` and `Transaction
   Quantity` are present.

---

### Edge Cases

- What happens for the first row of each (account, sub_account) group? `Transaction Value` equals
  `Account Value` (the prior account value is treated as 0).
- What happens when multiple events share the same date for the same position? Each event retains
  its own row; `Transaction Value` for each row shows that row's individual contribution. The
  invariant holds row-by-row.
- What happens when a Cash row has blank quantity? The existing Cash rule (quantity set to value
  before cumulation) applies first; `Transaction Quantity` and `Transaction Value` will both equal
  the same amount.
- What happens if a position has a zero-value event? `Transaction Value = 0`; `Account Value` is
  unchanged from the previous row.
- What happens when `Account Quantity` is not applicable (e.g. a non-unit investment with only
  value data)? The quantity columns are computed from whatever quantity is present in the input,
  including zero.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The output XLSX produced by `create_ledger` MUST contain exactly nine columns in this
  order: `date`, `account`, `sub_account`, `action`, `reference`, `Account Value`,
  `Account Quantity`, `Transaction Value`, `Transaction Quantity`.

- **FR-002**: The `Account Value` column MUST contain the same values as the `value` column defined
  in feature 003 (FR-007 of that spec) — the running cumulative sum of sign-adjusted values per
  (account, sub_account) group. No change to the calculation, only the column name.

- **FR-003**: The `Account Quantity` column MUST contain the same values as the `quantity` column
  defined in feature 003 (FR-008 of that spec) — the running cumulative sum of sign-adjusted
  quantities per (account, sub_account) group. No change to the calculation, only the column name.

- **FR-004**: The `Transaction Value` column MUST contain, for each row, the sign-adjusted value
  contribution of that event — the amount by which `Account Value` changes from the immediately
  preceding row in the same (account, sub_account) group to the current row.

- **FR-005**: The `Transaction Quantity` column MUST contain, for each row, the sign-adjusted
  quantity contribution of that event — the amount by which `Account Quantity` changes from the
  immediately preceding row in the same (account, sub_account) group to the current row.

- **FR-006**: For the first row in any (account, sub_account) group, `Transaction Value` MUST equal
  `Account Value` and `Transaction Quantity` MUST equal `Account Quantity` (because the prior
  cumulative balance is zero).

- **FR-007**: The invariant MUST hold for every output row: `Account Value` equals the sum of all
  `Transaction Value` entries for that (account, sub_account) group up to and including the current
  row. Equivalently: `Account Value[i] = Account Value[i−1 in group] + Transaction Value[i]`.

- **FR-008**: The same invariant MUST hold for quantities: `Account Quantity[i] = Account
  Quantity[i−1 in group] + Transaction Quantity[i]`.

- **FR-009**: All five identity columns (`date`, `account`, `sub_account`, `action`, `reference`)
  MUST be carried through unchanged from the corresponding input row.

- **FR-010**: The `Transaction Value` and `Transaction Quantity` columns MUST be stored as numeric
  cells in the output XLSX with the same numeric formatting applied to `Account Value` and
  `Account Quantity`.

- **FR-011**: The output row count MUST equal the input row count — no rows are added, dropped, or
  merged. When multiple events share the same (account, sub_account, date), each event retains its
  own output row with its own `Transaction Value` showing that event's individual contribution.
  Date-level aggregation of rows is explicitly out of scope.

- **FR-012**: If the input file does not exist or cannot be read as a valid journal, the mode MUST
  exit with a descriptive error and a non-zero exit code without creating the output file.

### Key Entities

- **Account Value**: The running cumulative balance of sign-adjusted values for a position up to
  and including the current row. Formerly the `value` column.
- **Account Quantity**: The running cumulative balance of sign-adjusted quantities for a position
  up to and including the current row. Formerly the `quantity` column.
- **Transaction Value**: The sign-adjusted value contribution of a single event — the delta between
  the current row's Account Value and the prior row's Account Value in the same group.
- **Transaction Quantity**: The sign-adjusted quantity contribution of a single event — the delta
  between the current row's Account Quantity and the prior row's Account Quantity in the same group.
- **Position**: A unique (account, sub_account) pair. Running balances and transaction deltas are
  computed independently per position.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every output row, the invariant `Account Value[i] = Account Value[i−1] +
  Transaction Value[i]` (with Account Value[i−1] = 0 for the first row in a group) holds with
  exact numerical equality — no row violates this.

- **SC-002**: For every output row, the analogous quantity invariant
  `Account Quantity[i] = Account Quantity[i−1] + Transaction Quantity[i]` holds with exact
  numerical equality.

- **SC-003**: The `Account Value` column values are numerically identical to the `value` column
  values that feature 003's `create_ledger` would produce for the same input.

- **SC-004**: The output contains exactly nine columns and the row count equals the input row count.

- **SC-005**: Processing a 500-row journal completes in under 10 seconds (consistent with feature
  003's SC-004 performance baseline).

## Assumptions

- This feature modifies the `create_ledger` mode's output schema; existing consumers of the ledger
  XLSX who reference columns by name (`value`, `quantity`) will need to be updated.
- The sign-adjustment rules (negate buy/sell values; negate sell quantities; copy value to quantity
  for Cash blank-quantity rows) are inherited unchanged from feature 003.
- The `Transaction Value` for each row is computed as the difference between consecutive
  `Account Value` entries in the same group — this is an exact inverse of the cumulative sum and
  does not require the original input values to be separately retained in the output.
- Multiple events on the same date for the same position remain as separate rows (confirmed by
  clarification). No date-level aggregation occurs in the output. The word "aggregated" in the
  original feature description refers to the ability to sum `Transaction Value` entries for the
  same date using any analysis tool after the fact — not to collapsing events into one row.
- The column name changes (`value` → `Account Value`, `quantity` → `Account Quantity`) apply only
  to the output XLSX headers; the internal journal schema used by other modes is not changed.
- The `date`, `account`, `sub_account`, `action`, and `reference` column names are not renamed.
