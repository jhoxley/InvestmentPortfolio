# Feature Specification: Capital Ledger Mode

**Feature Branch**: `011-capital-ledger-mode`
**Created**: 2026-07-01
**Status**: Draft
**Input**: User description: "Create a new mode called create_capital_ledger that takes one account
ledger as input and produces a date-level summary of capital inflows, income, and book value."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate a Date-Level Capital Summary from a Capital Account Ledger (Priority: P1)

A user has a capital account ledger (produced by `create_ledger`) and wants a single, compact
view of how the account's capital base, accumulated income, and invested book value have changed
over time. They invoke `create_capital_ledger` with the ledger path and an output path. The
resulting file has one row per unique calendar date that appears in the filtered input, in
chronological order. Each row shows the cumulative running total for three columns — `capital`,
`income`, and `book_value` — as of that date. Dates on which no transactions occurred for a
particular column still carry forward the most recent value for that column (forward-fill), so
every row is fully populated.

**Why this priority**: This is the entire purpose of the mode. US2 (pipeline integration) is
only useful once this core output exists and is correct.

**Independent Test**: Run `create_capital_ledger` against a known ledger containing at least one
deposit, one income, one buy, and one sell row across three distinct dates. Verify the output has
exactly three rows (one per date), that `capital` reflects only the cumulative deposit total,
`income` reflects only the cumulative income total, and `book_value` reflects the net cumulative
buy+sell total. Verify that a date with no deposit transaction still shows the correct carry-forward
`capital` value from the most recent prior deposit.

**Acceptance Scenarios**:

1. **Given** a ledger with a £5,000 deposit on 2024-01-10 and a £500 income row on 2024-02-15,
   **When** `create_capital_ledger` is run,
   **Then** the output row for 2024-01-10 shows `capital=5000`, `income=0`, `book_value=0`, and
   the row for 2024-02-15 shows `capital=5000` (carried forward), `income=500`, `book_value=0`.

2. **Given** a ledger with two buy rows (value −£1,000 and −£2,000) on 2024-03-20 and a sell row
   (value £800) on 2024-04-10,
   **When** `create_capital_ledger` is run,
   **Then** the output row for 2024-03-20 shows `book_value=−3000` and the row for 2024-04-10
   shows `book_value=−2200` (net cumulative: −3000 + 800).

3. **Given** a ledger containing action types other than deposit, income, buy, and sell (e.g.
   trading, dividend, fee),
   **When** `create_capital_ledger` is run,
   **Then** those rows are excluded from all calculations and do not appear in the output.

4. **Given** a date that has a buy transaction but no deposit or income transaction,
   **When** `create_capital_ledger` is run,
   **Then** the output row for that date shows the correct carry-forward values for `capital` and
   `income` (not zero or null), and the updated `book_value`.

5. **Given** a ledger where rows are ordered by Transaction ID (canonical order per spec 007),
   **When** `create_capital_ledger` is run,
   **Then** the running totals are accumulated in Transaction ID order so that same-date rows are
   processed in the deterministic canonical sequence before the date's output row is emitted.

---

### User Story 2 — Pipeline Runs Capital Ledger Mode for Capital Accounts Only (Priority: P2)

A user runs `run_pipeline.ps1`. After completing the existing two steps (consolidate journals,
create ledger) for all accounts, the pipeline additionally runs `create_capital_ledger` as a
third step — but only for the two capital accounts (HL SIPP and HL ISA), not for the income
accounts. The output capital summary file for each capital account is written to a defined path.

**Why this priority**: This is an automation convenience on top of the core mode. The mode itself
(US1) must be working correctly before the pipeline integration adds value.

**Independent Test**: Run `run_pipeline.ps1`. Confirm that three steps are executed for HL SIPP
and HL ISA (consolidate → ledger → capital ledger) but only two steps for HL SIPP Income and
HL ISA Income (consolidate → ledger, no capital ledger step).

**Acceptance Scenarios**:

1. **Given** `run_pipeline.ps1` is run with all four accounts configured,
   **When** execution completes successfully,
   **Then** a capital summary XLSX is written for HL SIPP and for HL ISA at their configured
   output paths, and no capital summary file is created for HL SIPP Income or HL ISA Income.

2. **Given** `run_pipeline.ps1` is run and the `create_ledger` step for a capital account fails,
   **When** the failure is detected,
   **Then** the `create_capital_ledger` step for that account is skipped (consistent with the
   existing `$failed` guard pattern used by steps 1 and 2).

---

### Edge Cases

- What happens when the input ledger is empty (no rows after filtering)? The output file is
  created but contains only headers and zero data rows.
- What happens when all rows in the filtered set fall on the same date? The output has exactly
  one row showing the combined totals for all three columns.
- What happens if the input file does not exist or is not a valid ledger XLSX? The mode exits
  with a non-zero exit code and writes an error to the console.
- What happens if `book_value` has a net result of zero (buys and sells exactly cancel)?
  The column shows `0.00`, which is correct and distinct from "no buy/sell activity".
- What happens when the output file already exists? It is overwritten (consistent with how
  `create_ledger` overwrites its output).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The mode MUST be named `create_capital_ledger` and invokable via `pipeline.py` with
  exactly two positional arguments: `input_ledger_path` and `output_file_path`.

- **FR-002**: The mode MUST read the input ledger XLSX and filter to rows whose `action` column
  value is one of: `deposit`, `income`, `buy`, `sell`. All other action types are excluded.

- **FR-003**: Filtered rows MUST be processed in Transaction ID order (ascending, per the
  canonical sort defined in spec 007: `(date, account, sub_account, reference)` ascending).
  This ensures same-date rows are accumulated in deterministic sequence before the date's
  summary row is emitted.

- **FR-004**: The output MUST contain exactly one row per unique calendar date from the filtered
  input, in chronological (date ascending) order.

- **FR-005**: Each output row MUST include a `capital` column equal to the cumulative sum of
  the `Transaction Value` for all `deposit` action rows up to and including that date.

- **FR-006**: Each output row MUST include an `income` column equal to the cumulative sum of
  the `Transaction Value` for all `income` action rows up to and including that date.

- **FR-007**: Each output row MUST include a `book_value` column equal to the cumulative net
  sum of the `Transaction Value` for all `buy` and `sell` action rows up to and including
  that date (buy values are typically negative; sell values are typically positive; the column
  represents the net invested cost basis).

- **FR-008**: For dates where no new transactions contribute to a particular column, that
  column's value MUST be the carry-forward value from the most recent prior date that had a
  contribution. On the first date in the output, columns with no contributing transactions
  MUST show `0.00`.

- **FR-009**: The output MUST be written as an XLSX file to `output_file_path`. If the file
  already exists it is overwritten. The output columns (in order) are:
  `date`, `capital`, `income`, `book_value`.

- **FR-010**: `run_pipeline.ps1` MUST be updated to run `create_capital_ledger` as step 3 for
  HL SIPP and HL ISA accounts only. The `CapitalLedgerPath` output file for each capital account
  must be declared in the account's configuration hashtable and written to the Investments
  directory alongside the existing ledger file.

### Key Entities

- **Capital Summary Row**: One record per unique date in the filtered ledger, containing date,
  running capital total, running income total, and running book value total.
- **Capital Column**: The cumulative sum of all `deposit` transaction values processed so far.
  Represents total cash injected into the account by the investor.
- **Income Column**: The cumulative sum of all `income` transaction values processed so far.
  Represents accumulated income (e.g. commission rebates) credited to the account.
- **Book Value Column**: The cumulative net sum of all `buy` and `sell` transaction values
  processed so far. Represents net amount deployed into investments (cost basis, sign-adjusted).
- **Capital Account**: An account in `run_pipeline.ps1` whose `Name` does not contain "Income"
  (i.e. HL SIPP and HL ISA). Only capital accounts receive the `create_capital_ledger` step.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any capital account ledger with N distinct dates after filtering, the output
  contains exactly N rows — one per date — in ascending date order. Zero missing dates, zero
  duplicate dates.

- **SC-002**: For every output row, `capital`, `income`, and `book_value` equal the exact
  running totals computed from all filtered input rows up to that date (tested against
  hand-calculated expected values). Zero calculation errors in the test suite.

- **SC-003**: No output cell in `capital`, `income`, or `book_value` is null or empty.
  Dates with no new contributions for a column show the correct carry-forward value from the
  preceding row (or `0.00` if no prior row). Zero nulls in any numeric column.

- **SC-004**: `run_pipeline.ps1` runs `create_capital_ledger` for HL SIPP and HL ISA and does
  not run it for HL SIPP Income or HL ISA Income. Confirmed by inspecting the script and
  validating that the capital summary output files are created only for the two capital accounts
  on a successful end-to-end pipeline run.

- **SC-005**: The new mode does not alter or break the output of `consolidate_journals` or
  `create_ledger` for any account. All existing pipeline tests pass unchanged.

## Assumptions

- The input ledger was produced by `create_ledger` and therefore contains a `Transaction ID`
  column (per spec 007), a `date` column, an `action` column, and a `Transaction Value` column.
  The mode may assume these columns are always present.
- "Transaction Value" in the input ledger refers to the signed monetary value of each event
  (deposits are positive, buys are negative, sells are positive). The mode uses these values
  as-is without sign adjustment.
- Capital accounts are HL SIPP and HL ISA; income accounts are HL SIPP Income and HL ISA Income.
  This distinction is encoded in `run_pipeline.ps1` by adding a `CapitalLedgerPath` key only to
  the capital account hashtables.
- The output file format is XLSX (not CSV) for consistency with all other pipeline outputs.
- The mode does not need to handle multi-account ledgers as input; each capital account's ledger
  is produced independently by `create_ledger` and is passed separately to `create_capital_ledger`.
- A `CapitalLedgerPath` for HL SIPP will be `HL_SIPP_Capital_Ledger.xlsx` and for HL ISA will be
  `HL_ISA_Capital_Ledger.xlsx`, both written to `$InvestmentsDir`.
