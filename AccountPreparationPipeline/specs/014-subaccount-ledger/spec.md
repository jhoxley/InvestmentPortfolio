# Feature Specification: Sub-Account Consolidated Ledger

**Feature Branch**: `014-subaccount-ledger`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "Create a new mode for 'create_subaccount_ledger' that consolidates a list of ledgers together"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Consolidated Equity Positions (Priority: P1)

A portfolio owner wants to see the current quantity held and total cost (book cost) for every equity holding, consolidated across multiple capital account ledgers (e.g. SIPP and ISA). Currently each ledger covers one account in isolation; this view combines them to produce a single running per-holding position table.

**Why this priority**: The fundamental value of the mode — without a merged position view there is no basis for any further analysis.

**Independent Test**: Given two capital-account ledger files each containing buy/sell/lodgement records for overlapping and distinct sub-accounts, running the mode produces a single output where each (date, sub-account) pair has the correct cumulative quantity and book cost reflecting all contributing events.

**Acceptance Scenarios**:

1. **Given** two capital ledgers with buy/sell events for "HSBC Fund" (one ledger each), **When** I run create_subaccount_ledger, **Then** the output contains a "HSBC Fund" row for every date on which a buy or sell occurred in either ledger, with quantity and book_cost correctly accumulated across both sources.
2. **Given** a capital ledger containing lodgement records, **When** I run create_subaccount_ledger, **Then** the lodgement sub-account rows appear in the output with the lodgement quantity and value included in the cumulative quantity and book_cost.
3. **Given** ledger files where the same sub-account has events on different dates in each file, **When** I run create_subaccount_ledger, **Then** the output has one row per unique date-sub-account pair, with values cumulative across all prior events for that sub-account.

---

### User Story 2 — Accumulated Dividend Income Per Holding (Priority: P2)

The portfolio owner wants to see, alongside each holding's position, the total dividend income accumulated for that holding over time. This income originates in income-account ledgers and should be merged with the position data from capital-account ledgers.

**Why this priority**: Income tracking is the second core analytical dimension alongside position cost; the two belong together in a single consolidated view.

**Independent Test**: Given a capital ledger with buy/sell events for "HSBC Fund" and an income ledger with dividend events for the same sub-account, the output contains a total_income column that accumulates dividend Transaction Values, with zero contribution from the dividend's Transaction Quantity field.

**Acceptance Scenarios**:

1. **Given** an income ledger with dividend records for "HSBC Fund", **When** I run create_subaccount_ledger, **Then** the total_income column for "HSBC Fund" rows shows the cumulative sum of the dividend Transaction Values (not the dividend quantities).
2. **Given** a dividend record and a buy record on the same date for the same sub-account, **When** I run create_subaccount_ledger, **Then** a single row appears for that date, combining the book_cost contribution from the buy and the total_income contribution from the dividend.
3. **Given** a sub-account that has only dividend events and no buy/sell/lodgement events, **When** I run create_subaccount_ledger, **Then** the sub-account still appears in the output on dividend dates, with quantity=0 and book_cost=0.

---

### User Story 3 — Cash Balance Without Double-Counting (Priority: P3)

Both capital and income account ledgers contain a "Cash" sub-account tracking the running cash balance for their respective account. Including both would double-count the cash; the income ledger's Cash balance is effectively already reflected in the capital account. The portfolio owner needs to see an accurate, deduplicated cash position.

**Why this priority**: Correct cash reporting is essential for an accurate total portfolio view; double-counted cash would make aggregate totals meaningless.

**Independent Test**: Given a capital ledger and an income ledger both containing Cash rows, running the mode with the income ledger designated as an income file produces Cash rows sourced only from the capital ledger, with quantity equal to book_cost and total_income equal to zero.

**Acceptance Scenarios**:

1. **Given** a capital ledger and an income ledger, both with Cash sub-account rows, and the income ledger designated as `income`, **When** I run create_subaccount_ledger, **Then** Cash rows from the income ledger are absent from the output and Cash rows from the capital ledger appear with quantity == book_cost.
2. **Given** a capital ledger only (no income ledger supplied), **When** I run create_subaccount_ledger, **Then** Cash rows from the capital ledger appear correctly with total_income = 0.
3. **Given** a Cash row in the output, **When** I inspect the row, **Then** quantity equals book_cost (both reflect the cumulative cash balance) and total_income is zero.

---

### Edge Cases

- What happens when two capital ledgers contain Cash rows for the same date? Both should contribute to the cumulative Cash balance (not deduplicated).
- What happens when an income ledger contains non-Cash, non-dividend rows (e.g. income action rows)? Only dividend action rows from income ledgers contribute to total_income; all other income ledger rows are ignored.
- How does the mode handle a sub-account name that appears in only one of the supplied ledgers? It should appear in the output using events from that single source.
- What if no ledger files are supplied? The mode should exit with an error indicating at least one input is required.
- What if a designated income ledger contains buy or sell records (unexpected but possible)? Those records are still processed for book_cost and quantity; only Cash sub-account rows from income ledgers are excluded.

## Clarifications

### Session 2026-07-03

- Q: Should FR-009's exclusion of fee/deposit/trading/income apply to equity sub-account rows only, with an explicit exception for Cash sub-account rows from capital ledgers? → A: FR-009 applies to equity sub-accounts only; all action types on Cash rows from capital ledgers contribute to the cash balance (FR-008 takes precedence for Cash).
- Q: Should dividend action rows from capital ledger files contribute to total_income, or only dividends from income-designated files? → A: Dividend rows from any input ledger (capital or income) contribute to total_income.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The mode MUST accept one or more capital ledger input paths and zero or more income ledger input paths, with each file clearly designated as capital or income at invocation time.
- **FR-002**: The mode MUST produce one output row per unique (date, sub-account) pair discovered across all input files, covering any date on which a relevant event (buy, sell, lodgement, or dividend) occurred for that sub-account.
- **FR-003**: The output MUST contain exactly five columns: `date`, `sub_account`, `book_cost`, `quantity`, and `total_income`.
- **FR-004**: `quantity` MUST be the cumulative net total of Transaction Quantity values for buy, sell, and lodgement action rows for each sub-account up to and including each row's date.
- **FR-005**: `book_cost` MUST be the cumulative net total of Transaction Value contributions from buy, sell, and lodgement action rows for each sub-account up to and including each row's date. Lodgement Transaction Values (which are negative in the ledger) MUST be negated before accumulation so that lodgements add to book cost (matching the sign behaviour of buy records).
- **FR-006**: `total_income` MUST be the cumulative sum of Transaction Values from dividend action rows for each sub-account up to and including each row's date, regardless of whether the dividend row originates from a capital or income-designated input file. The Transaction Quantity of dividend records is ignored.
- **FR-007**: Cash sub-account rows originating from any income-designated input file MUST be excluded entirely from processing.
- **FR-008**: For the Cash sub-account, `quantity` and `book_cost` MUST both equal the cumulative running cash balance derived from all Cash Transaction Values in capital ledger inputs; `total_income` MUST be zero.
- **FR-009**: For equity sub-accounts, action types other than buy, sell, lodgement, and dividend MUST NOT contribute to any output column (fee, trading, income, deposit, and similar actions are excluded). Exception: this restriction does not apply to the Cash sub-account from capital ledgers, where all action types contribute to the cash balance as specified in FR-008.
- **FR-010**: Output rows MUST be sorted in ascending date order, with sub-account as the secondary sort key.
- **FR-011**: The mode MUST write output to a single XLSX file at a user-specified output path.
- **FR-012**: The mode MUST exit with a non-zero code and a descriptive error if any required input file is missing or unreadable.

### Key Entities

- **Ledger**: An XLSX file produced by `create_ledger` mode, containing columns: Transaction ID, date, account, sub_account, action, reference, Account Value, Account Quantity, Transaction Value, Transaction Quantity.
- **Capital Ledger**: A ledger file for a capital account (SIPP, ISA). Cash sub-account rows from these files are included.
- **Income Ledger**: A ledger file for an income account. Cash sub-account rows from these files are excluded; only dividend action rows from income ledgers contribute to `total_income`.
- **Sub-Account**: A named holding or the "Cash" position within a ledger. Sub-account names are treated as case-sensitive string identifiers.
- **Output Row**: A (date, sub_account) snapshot showing the cumulative position (book_cost, quantity) and income (total_income) as of that date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the mode against two ledger files (one capital, one income) produces an output where every (date, sub-account) pair with a relevant event is present and no pair is duplicated.
- **SC-002**: For any equity sub-account row in the output, `book_cost` and `quantity` exactly match the result of manually summing the buy/sell/lodgement Transaction Values and Transaction Quantities from all input ledgers up to that date.
- **SC-003**: For any Cash row in the output, `quantity` equals `book_cost` and `total_income` is zero; no Cash rows originating from income ledgers appear.
- **SC-004**: The mode completes processing a combined input of up to 1,000 ledger rows within 10 seconds on a standard desktop machine.
- **SC-005**: The output XLSX contains exactly the columns `date`, `sub_account`, `book_cost`, `quantity`, `total_income` in that order, with rows sorted ascending by date then sub_account.

## Assumptions

- All input ledger files are valid outputs from the `create_ledger` mode and conform to its column schema (Transaction ID, date, account, sub_account, action, reference, Account Value, Account Quantity, Transaction Value, Transaction Quantity).
- Sub-account names are consistent across capital and income ledgers for the same holding (e.g. the equity name "HSBC FTSE 250 Index" is spelled identically in both).
- A single invocation consolidates ledgers for one investor or account group; cross-investor merges are out of scope.
- The Cash sub-account is identified by the exact string "Cash" (case-sensitive), matching the convention already established in `consolidate_journals`.
- Lodgement records carry a negative Transaction Value in the ledger (the ledger engine does not sign-adjust lodgement rows, unlike buy/sell); this spec assumes that behaviour and specifies negation accordingly in FR-005.
- Buy Transaction Values in the ledger are positive (the ledger engine negates the raw journal buy value), and sell Transaction Values are negative. This matches the sign convention verified against live ISA ledger data.
- The output does not forward-fill rows to every calendar date; a row appears only on dates where at least one relevant event occurred for that sub-account.
- Income ledgers may contain action types other than dividend (e.g. income, trading offsets); only dividend rows from income ledgers contribute to the output.
- Multiple capital ledgers may be from different account types (SIPP, ISA); sub-accounts with the same name across accounts are merged into a single position in the output.
