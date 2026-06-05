# Feature Specification: Ledger Running Balance

**Feature Branch**: `003-create-ledger`
**Created**: 2026-06-03
**Status**: Draft
**Input**: User description: "Create a new mode called create_ledger..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a Position Ledger from a Consolidated Journal (Priority: P1)

A user has a consolidated journal XLSX produced by the `consolidate_journals` mode and wants to
derive a position ledger showing the running holding balance and cumulative cost for each
investment position and cash account over time. They invoke the pipeline with the `create_ledger`
mode, providing the input journal path and an output path for the ledger XLSX.

**Why this priority**: This is the sole function of the mode — computing running totals is the
entire value delivered. No other user story is possible without this one.

**Independent Test**: Run `create_ledger` against a consolidated journal with a known set of buy,
sell, deposit, income, and fee events. Verify the output XLSX contains one row per input event,
that each row's value and quantity reflect the correct cumulative total at that point in time, and
that action and reference are retained from the source row.

**Acceptance Scenarios**:

1. **Given** a consolidated journal with buy events for a position, **When** `create_ledger` is
   run, **Then** each buy row's value in the output is the negated cumulative cost (buy values are
   multiplied by -1 before summing), and quantity is the cumulative units held.
2. **Given** a consolidated journal with sell events for a position, **When** `create_ledger` is
   run, **Then** each sell row's value is the running cumulative (sell values are also multiplied
   by -1 before summing), and quantity reflects the running net holding (sell quantity is negated
   before summing).
3. **Given** a consolidated journal with Cash sub_account rows where quantity is blank, **When**
   `create_ledger` is run, **Then** the value is copied to quantity before cumulation, and both
   value and quantity for each Cash row show the running total of all prior and current Cash events.
4. **Given** a journal with events across multiple sub_accounts, **When** `create_ledger` is run,
   **Then** running totals are calculated independently per (account, sub_account) pair — events
   for one position do not affect the running total of another.
5. **Given** a journal with events across multiple dates for the same position, **When**
   `create_ledger` is run, **Then** rows appear in chronological order and each row's cumulative
   value and quantity correctly include all earlier rows for that position.
6. **Given** a valid input journal, **When** `create_ledger` completes, **Then** the output XLSX
   uses the same seven-column schema as the input (`date`, `account`, `sub_account`, `action`,
   `reference`, `value`, `quantity`) and the `action` and `reference` columns are carried through
   unchanged from the input row.

---

### Edge Cases

- What happens when the input XLSX does not exist or is not a valid journal file?
- What happens when the input journal contains no rows (header only)?
- What happens when a position has only sell events with no prior buys (quantity goes negative)?
- What happens when value or quantity cells in the input contain non-numeric data?
- What happens when the output path's parent directory does not exist?
- What happens when multiple events exist for the same date, account, and sub_account?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST support a `create_ledger` mode accepting two positional arguments:
  (1) input XLSX path — a consolidated journal in the schema produced by `consolidate_journals`;
  (2) output XLSX path — destination for the ledger file.
- **FR-002**: The system MUST read all rows from the input journal and produce one output row per
  input row (the row count is preserved, not aggregated).
- **FR-003**: Rows in the output MUST be sorted chronologically by date within each
  (account, sub_account) group. The sort order across groups is by account then sub_account.
- **FR-004**: For rows where the action is `buy` or `sell`, the input value MUST be multiplied by
  -1 before being included in the cumulative sum. For all other action types the value is included
  as-is.
- **FR-005**: For rows where the action is `sell`, the input quantity MUST be multiplied by -1
  before being included in the cumulative sum. For `buy` and all other action types the quantity is
  included as-is.
- **FR-006**: For rows where the sub_account is `Cash` and the input quantity is blank or absent,
  the input value MUST be copied to quantity before calculating the cumulative sum.
- **FR-007**: The `value` in each output row MUST be the cumulative sum of all adjusted values
  (per FR-004 and FR-006) for that (account, sub_account) pair up to and including the current row.
- **FR-008**: The `quantity` in each output row MUST be the cumulative sum of all adjusted
  quantities (per FR-005 and FR-006) for that (account, sub_account) pair up to and including the
  current row.
- **FR-009**: The `action` and `reference` columns MUST be carried through unchanged from each
  corresponding input row.
- **FR-010**: The `date` and `account` columns MUST be carried through unchanged from each
  corresponding input row.
- **FR-011**: The output XLSX MUST use the same seven-column schema and column order as the input:
  `date`, `account`, `sub_account`, `action`, `reference`, `value`, `quantity`.
- **FR-012**: The `value` and `quantity` columns in the output MUST be stored as numeric cells,
  consistent with the numeric formatting applied by `consolidate_journals`.
- **FR-013**: If the input file does not exist or cannot be read as a valid journal, the mode MUST
  exit with a descriptive error and a non-zero exit code without creating the output file.
- **FR-014**: The mode MUST log a structured completion record to the log indicating the number of
  input rows processed and output rows written.

### Key Entities

- **Input Journal**: A consolidated journal XLSX in the fixed seven-column schema produced by
  `consolidate_journals`. Read-only; never modified by this mode.
- **Ledger**: The output XLSX containing one row per input event with cumulative running balances
  of value and quantity, grouped by (account, sub_account).
- **Position**: A unique (account, sub_account) pair. Each position has its own independent
  running balance. All events for a position are sorted by date before cumulation.
- **Adjusted Value**: The per-row value after sign adjustment — negated for `buy` and `sell`
  actions; copied from `value` for Cash rows with blank quantity; unchanged for all others.
- **Adjusted Quantity**: The per-row quantity after sign adjustment — negated for `sell` actions;
  set to the input `value` for Cash rows with blank quantity; unchanged for `buy` and all others.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a journal of known events, every output row's cumulative value and quantity
  match hand-calculated expected totals for that position up to that date.
- **SC-002**: The output row count equals the input row count exactly — no rows are added,
  dropped, or merged.
- **SC-003**: Running `create_ledger` twice on the same input produces bit-identical output files.
- **SC-004**: Processing a consolidated journal of 500 rows across 20 positions completes in under
  10 seconds on a standard desktop.
- **SC-005**: The output schema (column names, order, and numeric cell types) is identical to the
  input schema.

## Assumptions

- The input XLSX conforms to the exact seven-column schema produced by `consolidate_journals`;
  behaviour is undefined if the schema differs.
- All monetary values in the input are denominated in GBP; no currency conversion is required.
- The `sub_account` value `"Cash"` is the canonical identifier for cash positions; other
  sub_account values represent investment positions.
- For Cash positions, the quantity column in the input is always blank (consistent with how
  `consolidate_journals` writes cash events); if a Cash row has a non-blank quantity, it is used
  as-is rather than overridden by the value.
- When multiple events share the same date for the same (account, sub_account), their relative
  order within that date is the order they appear in the input file.
- The parent directory of the output XLSX path must already exist; the mode does not create
  intermediate directories.
- The input journal is not modified during or after the ledger generation run.
