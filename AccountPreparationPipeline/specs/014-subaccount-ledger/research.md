# Research: Sub-Account Consolidated Ledger (Feature 014)

## Decision 1 — CLI Input Designation: How to mark a file as capital vs income

**Decision**: Use two named flag arguments: `--capital PATH [PATH...]` and `--income PATH [PATH...]` (both accept one or more paths via `nargs='+'`). Output path is a positional argument.

```
pipeline.py create_subaccount_ledger OUTPUT_PATH --capital LEDGER [LEDGER...] [--income LEDGER [LEDGER...]]
```

**Rationale**: The existing modes use positional args for simple 1-in/1-out shapes, but this mode has a variadic, typed input list. Named flags with `nargs='+'` are idiomatic argparse and make the capital/income distinction explicit and self-documenting in the command line. `--income` is optional (some use cases may have only capital ledgers).

**Alternatives considered**:
- Positional pairs `CAPITAL_1 INCOME_1 CAPITAL_2 INCOME_2`: rejected — ambiguous order and hard to extend.
- Config file listing paths and types: rejected — over-engineering for a pipeline mode that is driven from a PowerShell script.
- Single list with a `--income-indices` flag: rejected — opaque and error-prone.

---

## Decision 2 — Sub-Account Merging Across Multiple Ledgers

**Decision**: All input ledgers are pooled into a single event list. Sub-account names are treated as the merge key. Rows with the same `sub_account` string from any input file contribute to the same cumulative position in the output.

**Rationale**: The mode's purpose is a unified portfolio view. An equity holding like "HSBC FTSE 250 Index" may appear in both the SIPP and ISA capital ledgers; the portfolio owner wants a single consolidated position, not one row per account. Merging by sub-account name achieves this without requiring the user to specify cross-account relationships.

**Alternatives considered**:
- Keep (account, sub_account) as the merge key: rejected — the spec says "one row per unique date and sub-account" (no account dimension in the output schema).
- Require sub-account names to be unique across all input files: rejected — unrealistic; the same fund appears in multiple accounts.

---

## Decision 3 — Lodgement Sign Convention for book_cost and quantity

**Decision**: 
- **book_cost**: Negate the lodgement Transaction Value before accumulation. Lodgement TV is negative in the ledger (the ledger engine does not sign-adjust lodgement, unlike buy/sell). Negating gives a positive contribution — i.e., the cost of the securities transferred in adds to book cost, matching the positive TV produced by buy records.
- **quantity**: Use the Transaction Quantity as-is (positive) for lodgement. The ledger engine only negates quantity for sell; lodgement quantity is already positive.

**Evidence**: Verified against live ISA ledger data (see Feature 013 and Feature 014 bug fix work):
- Buy TV: +200 (ledger negates journal's −200) → positive contribution to book_cost ✓
- Lodgement TV: −2288.89 (not negated by ledger) → negate to get +2288.89 for book_cost ✓
- Lodgement TQ: 1221 (positive, correct)

**Alternatives considered**:
- Add lodgement directly to bv_trade_mask (same treatment as buy/sell): rejected — would give negative book_cost contribution for lodgement, reducing rather than adding to book cost.

---

## Decision 4 — Cash Consolidation Across Multiple Capital Accounts

**Decision**: All Cash sub-account rows from all capital ledger inputs are combined into a single Cash position in the output. The running cash balance is the cumulative sum of Transaction Values for all Cash rows across all capital ledgers, regardless of which account they originate from.

**Rationale**: The consolidated sub-account ledger represents total portfolio holdings. Cash across all capital accounts is a single asset class. Separately reporting SIPP Cash and ISA Cash would require a different merge key (account, sub_account), which contradicts the spec's output schema (no account column). Merging gives total cash held across all capital accounts.

**Alternatives considered**:
- Report Cash per originating account by adding a hidden account prefix: rejected — the output schema has no account column; this would require schema changes beyond the spec.
- Report only one capital ledger's Cash (e.g., the first supplied): rejected — would silently discard cash from other accounts.

---

## Decision 5 — Output Rows: Event Dates Only vs Full Forward-Fill

**Decision**: Output contains one row per (date, sub-account) pair where at least one relevant event (buy, sell, lodgement, dividend, or — for Cash — any action) actually occurred. No rows are synthesised for dates between events.

**Rationale**: The spec states "one row per unique date and sub-account discovered across the input files" — "discovered" means actually present in the data. Forward-filling to all calendar dates would produce rows the ledger never recorded, inflating the output and obscuring what changed when. Consumers of the output who want "current position as of any date" can take the most recent row for each sub-account with date ≤ the target date.

**Implementation note**: The cumsum approach naturally handles this. Grouping events by (date, sub_account), summing their contributions, then cumsumming per sub_account gives the correct cumulative value at each event date without needing explicit forward-fill.

---

## Decision 6 — Dividend Income: Transaction Value Only, Quantity Ignored

**Decision**: For dividend action rows, only the Transaction Value column is summed into `total_income`. The Transaction Quantity column on dividend rows (which records the number of shares to which the dividend relates) is ignored.

**Rationale**: The spec explicitly states "taking the 'transaction value' and ignoring the dividend quantity from the income ledger". The Transaction Value reflects the cash income received; the quantity is informational metadata about entitlement, not a cash figure.

---

## Decision 7 — Actions to Exclude from All Computations

**Decision**: The following action types contribute to NO output column and are discarded during processing: `fee`, `trading`, `income`, `deposit`, `lodgement` (for income and total_income columns only — see FR-004/FR-005), and any unrecognised action type. The complete inclusion map:

| Action     | book_cost | quantity | total_income | Cash balance |
|------------|-----------|----------|--------------|--------------|
| buy        | ✓ (+TV)   | ✓ (+TQ)  | —            | —            |
| sell       | ✓ (+TV)   | ✓ (+TQ)  | —            | —            |
| lodgement  | ✓ (−TV)   | ✓ (+TQ)  | —            | —            |
| dividend   | —         | —        | ✓ (+TV)      | —            |
| fee        | —         | —        | —            | ✓ (Cash only)|
| trading    | —         | —        | —            | ✓ (Cash only)|
| income     | —         | —        | —            | ✓ (Cash only)|
| deposit    | —         | —        | —            | ✓ (Cash only)|

For the Cash sub-account from capital ledgers, ALL action types contribute to the running cash balance via their Transaction Value (matching the ledger's Account Value for Cash). The individual action distinction is irrelevant for Cash.

---

## Decision 8 — Engine Design: Single-Pass Pandas Computation

**Decision**: Implement `SubAccountLedgerEngine` as a single class with a `run(capital_dfs, income_dfs)` method that processes all data in pandas in three logical passes: (1) equity book_cost/quantity, (2) dividend income, (3) Cash balance. Merge the three results on (date, sub_account), fill missing values with 0, then cumsum within each sub_account. Return a single DataFrame.

**Rationale**: The data volumes are small (hundreds to low thousands of rows), so pandas batch processing is appropriate. Separating the three passes keeps the logic readable and each pass independently testable as a private method.

**Alternatives considered**:
- Row-by-row Python iteration: rejected — unnecessary complexity and slower for larger inputs.
- Three separate engine classes: rejected — over-engineering; the three passes share input data and the engine is not polymorphic.
