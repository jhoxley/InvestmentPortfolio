# Data Model: Sub-Account Consolidated Ledger (Feature 014)

## Input: Ledger Row (from create_ledger output)

Each input XLSX file conforms to the schema produced by the `create_ledger` mode.

| Column              | Type    | Notes                                                           |
|---------------------|---------|-----------------------------------------------------------------|
| Transaction ID      | str     | `NNNNN-NNN` format; used for ordering within a date (ignored in output) |
| date                | str     | `YYYY-MM-DD` format                                             |
| account             | str     | Account label (e.g. "HL Stocks and Shares ISA")                |
| sub_account         | str     | Holding name or `"Cash"`                                        |
| action              | str     | `buy`, `sell`, `lodgement`, `dividend`, `fee`, `trading`, `income`, `deposit` |
| reference           | str     | Trade/event reference                                           |
| Account Value       | float   | Running cumulative balance for this (account, sub_account)     |
| Account Quantity    | float   | Running cumulative quantity for this (account, sub_account)    |
| Transaction Value   | float   | Per-row signed contribution to value                           |
| Transaction Quantity| float   | Per-row signed contribution to quantity                        |

### Sign conventions (established in prior features)

- **buy**: Transaction Value positive (ledger negates journal's negative value); Transaction Quantity positive
- **sell**: Transaction Value negative; Transaction Quantity negative
- **lodgement**: Transaction Value negative (NOT sign-adjusted by ledger engine); Transaction Quantity positive
- **dividend**: Transaction Value positive (income received); Transaction Quantity = shares entitled (ignored)
- **Cash rows**: Transaction Value reflects the directional effect on the cash balance (deposits/income positive; buys/fees negative)

---

## Processing Entities

### InputLedgerSet

Represents the complete set of input files passed to the mode.

| Attribute       | Type             | Notes                                      |
|-----------------|------------------|--------------------------------------------|
| capital_paths   | list[Path]       | One or more capital ledger XLSX paths      |
| income_paths    | list[Path]       | Zero or more income ledger XLSX paths      |

### EquityEvent

An extracted contribution record for a single buy/sell/lodgement or dividend row.

| Attribute      | Type   | Notes                                                      |
|----------------|--------|------------------------------------------------------------|
| date           | str    | `YYYY-MM-DD`                                               |
| sub_account    | str    | Holding name (never "Cash")                                |
| bv_contrib     | float  | Contribution to book_cost: +TV for buy/sell; −TV for lodgement |
| qty_contrib    | float  | Contribution to quantity: TQ for buy/sell/lodgement; 0 for dividend |
| income_contrib | float  | Contribution to total_income: TV for dividend; 0 otherwise |

### CashEvent

An extracted contribution record for a single Cash sub-account row from a capital ledger.

| Attribute   | Type   | Notes                        |
|-------------|--------|------------------------------|
| date        | str    | `YYYY-MM-DD`                 |
| cash_contrib| float  | Transaction Value (any action)|

---

## Output: SubAccountSnapshot

One row per unique (date, sub_account) pair in the output XLSX.

| Column        | Type   | Notes                                                               |
|---------------|--------|---------------------------------------------------------------------|
| date          | str    | `YYYY-MM-DD`; sorted ascending                                      |
| sub_account   | str    | Holding name or `"Cash"`; secondary sort key                        |
| book_cost     | float  | Cumulative net book cost from buy/sell/lodgement to this date       |
| quantity      | float  | Cumulative net quantity from buy/sell/lodgement to this date        |
| total_income  | float  | Cumulative dividend Transaction Value to this date; 0 for Cash rows |

### Output invariants

- Exactly one row per unique (date, sub_account) pair
- Rows sorted: date ascending, sub_account ascending (secondary)
- For Cash rows: `book_cost == quantity == cumulative cash balance`; `total_income == 0`
- Cash rows originate exclusively from capital ledger inputs
- All values are cumulative (running totals), not per-event deltas

---

## Computation Flow

```
capital_dfs  (list of DataFrames)         income_dfs  (list of DataFrames)
     │                                           │
     ├─ filter: all rows                         ├─ filter: exclude Cash rows
     │                                           │
     ├─ Cash rows → CashEvent stream             └─ EquityEvent stream (dividend only)
     │      │                                             │
     │      │ cumsum(TV) per date                         │
     │      ↓                                             ↓
     │  cash_snapshot                          income_snapshot
     │  (date, book_cost=qty=balance,          (date, sub_account,
     │   total_income=0)                        total_income cumsum)
     │                                                    │
     └─ Equity rows (buy/sell/lodgement)                  │
            │                                             │
            ↓                                             │
       equity_snapshot                                    │
       (date, sub_account,                               │
        book_cost+quantity cumsums)                       │
            │                                             │
            └────────────────── merge ───────────────────┘
                                    │
                              SubAccountSnapshot
                           (date, sub_account, book_cost,
                            quantity, total_income)
                          sorted by date, sub_account
```

---

## Inclusion Rules by Action

| Action    | Source                | book_cost | quantity | total_income | Cash balance |
|-----------|-----------------------|-----------|----------|--------------|--------------|
| buy       | capital only          | +TV       | +TQ      | 0            | n/a          |
| sell      | capital only          | +TV       | +TQ      | 0            | n/a          |
| lodgement | capital only          | −TV       | +TQ      | 0            | n/a          |
| dividend  | income (non-Cash)     | 0         | 0        | +TV          | n/a          |
| fee       | capital Cash only     | n/a       | n/a      | n/a          | +TV          |
| trading   | capital Cash only     | n/a       | n/a      | n/a          | +TV          |
| income    | capital Cash only     | n/a       | n/a      | n/a          | +TV          |
| deposit   | capital Cash only     | n/a       | n/a      | n/a          | +TV          |
| lodgement | capital Cash only     | n/a       | n/a      | n/a          | +TV (if Cash sub_account) |
