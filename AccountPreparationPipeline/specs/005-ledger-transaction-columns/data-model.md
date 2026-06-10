# Data Model: Ledger Transaction Columns

**Feature**: 005-ledger-transaction-columns
**Date**: 2026-06-08

## Schema Change Summary

This feature changes the **output schema** of `create_ledger`. The **input schema** (seven-column
journal produced by `consolidate_journals`) is unchanged.

## Input Schema (unchanged)

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Settlement date |
| `account` | string | Account name |
| `sub_account` | string | Position name |
| `action` | string | Event action |
| `reference` | string | Transaction reference |
| `value` | decimal | Raw transaction value |
| `quantity` | decimal | Units (blank for Cash) |

## Output Schema (new — 9 columns)

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Carried through unchanged |
| `account` | string | Carried through unchanged |
| `sub_account` | string | Carried through unchanged |
| `action` | string | Carried through unchanged |
| `reference` | string | Carried through unchanged |
| `Account Value` | decimal | Running cumulative sum of sign-adjusted values for this (account, sub_account) group up to this row. Formerly the `value` column. |
| `Account Quantity` | decimal | Running cumulative sum of sign-adjusted quantities for this (account, sub_account) group up to this row. Formerly the `quantity` column. |
| `Transaction Value` | decimal | The sign-adjusted value contribution of this specific event — the delta applied to Account Value on this row. |
| `Transaction Quantity` | decimal | The sign-adjusted quantity contribution of this specific event — the delta applied to Account Quantity on this row. |

## Invariant

For every row `i` in the output, within each (account, sub_account) group:

```
Account Value[i] = Account Value[i−1] + Transaction Value[i]
Account Quantity[i] = Account Quantity[i−1] + Transaction Quantity[i]
```

Where `Account Value[i−1] = 0` for the first row of any (account, sub_account) group.

## New Constants (`create_ledger/constants.py`)

| Constant | Value |
|----------|-------|
| `LEDGER_COL_ACCOUNT_VALUE` | `"Account Value"` |
| `LEDGER_COL_ACCOUNT_QUANTITY` | `"Account Quantity"` |
| `LEDGER_COL_TRANSACTION_VALUE` | `"Transaction Value"` |
| `LEDGER_COL_TRANSACTION_QUANTITY` | `"Transaction Quantity"` |
| `LEDGER_COLUMNS` | `["date", "account", "sub_account", "action", "reference", "Account Value", "Account Quantity", "Transaction Value", "Transaction Quantity"]` |

## Numeric Formatting

| Column | Format |
|--------|--------|
| `Account Value` | `NUMBER_FORMAT_VALUE` (`#,##0.00`) |
| `Account Quantity` | `NUMBER_FORMAT_QUANTITY` (`#,##0.######`) |
| `Transaction Value` | `NUMBER_FORMAT_VALUE` (`#,##0.00`) |
| `Transaction Quantity` | `NUMBER_FORMAT_QUANTITY` (`#,##0.######`) |

## Engine Transformation (updated)

```
Input: JOURNAL_COLUMNS (7 cols)

1. Validate JOURNAL_COLUMNS present
2. Cash rule: quantity ← value for Cash+blank-qty rows
3. adj_value ← sign-adjusted value (negate buy/sell)
4. adj_quantity ← sign-adjusted quantity (negate sell)
5. Stable sort by (account, sub_account, date)
6. Account Value ← groupby cumsum(adj_value)
7. Account Quantity ← groupby cumsum(adj_quantity)
8. Transaction Value ← adj_value  [retain, do not drop]
9. Transaction Quantity ← adj_quantity  [retain, do not drop]
10. Drop original value, quantity, adj_value, adj_quantity
11. Return LEDGER_COLUMNS (9 cols)
```

## Breaking Change

**Column renames**: consumers of the `create_ledger` output that reference columns by name
(`value`, `quantity`) must update to `Account Value`, `Account Quantity`.

**Two new columns**: `Transaction Value` and `Transaction Quantity` are appended; consumers
must handle the wider schema.
