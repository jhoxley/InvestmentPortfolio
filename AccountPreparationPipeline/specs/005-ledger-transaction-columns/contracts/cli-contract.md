# Contract: CLI — create_ledger Mode (schema extension)

**Feature**: 005-ledger-transaction-columns
**Date**: 2026-06-08
**Type**: CLI behaviour contract (delta from feature 003 contract)

## Overview

No changes to the CLI invocation signature. The change is entirely in the **output XLSX schema**.

## Invocation (unchanged)

```
python pipeline.py create_ledger INPUT_PATH OUTPUT_PATH
```

## Arguments (unchanged)

| Position | Name | Description |
|----------|------|-------------|
| 1 | `INPUT_PATH` | Consolidated journal XLSX (7-column schema) |
| 2 | `OUTPUT_PATH` | Ledger XLSX — now written with 9-column schema |

## Output XLSX Schema Change

**Before (feature 003)**: 7 columns — `date`, `account`, `sub_account`, `action`, `reference`,
`value`, `quantity`

**After (feature 005)**: 9 columns — `date`, `account`, `sub_account`, `action`, `reference`,
`Account Value`, `Account Quantity`, `Transaction Value`, `Transaction Quantity`

## Exit Codes (unchanged)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Invalid input (missing file, bad schema) |
| 3 | Unhandled failure |

## Console Output (unchanged)

```
Ledger written: 492 rows processed -> data/group_sipp_ledger.xlsx
```

## Breaking Change Notice

Consumers that read the ledger XLSX by column name (`value`, `quantity`) will receive a
`KeyError` after this upgrade. Update column references to `Account Value` and `Account
Quantity` respectively. The two new columns `Transaction Value` and `Transaction Quantity`
are additive.
