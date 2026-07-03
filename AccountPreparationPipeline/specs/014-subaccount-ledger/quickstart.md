# Quickstart: Sub-Account Consolidated Ledger (Feature 014)

## Scenario: Full portfolio consolidation (SIPP + ISA)

A portfolio owner has run `create_ledger` for four accounts and now wants a unified sub-account view.

```powershell
python pipeline.py create_subaccount_ledger `
    "C:\Investments\Portfolio_SubAccount_Ledger.xlsx" `
    --capital `
        "C:\Investments\HL_SIPP_Ledger.xlsx" `
        "C:\Investments\HL_ISA_Ledger.xlsx" `
    --income `
        "C:\Investments\HL_SIPP_Income_Ledger.xlsx" `
        "C:\Investments\HL_ISA_Income_Ledger.xlsx"
```

**Expected output** (`Portfolio_SubAccount_Ledger.xlsx`):

| date       | sub_account                | book_cost | quantity | total_income |
|------------|---------------------------|-----------|----------|--------------|
| 2018-07-12 | Barclays plc Ordinary 25p | 2288.89   | 1221.0   | 0.00         |
| 2018-07-12 | Cash                      | 7852.19   | 7852.19  | 0.00         |
| 2018-07-12 | iShares GBP Index Gilts   | 106.26    | 800.0    | 0.00         |
| ...        | ...                       | ...       | ...      | ...          |
| 2024-04-10 | HSBC FTSE 250 Index       | 12345.00  | 500.0    | 874.32       |
| 2024-04-10 | Cash                      | 15200.00  | 15200.00 | 0.00         |

Notes:
- "Cash" row: `quantity == book_cost`; `total_income == 0`
- Equity rows: `total_income` accumulates dividends from income ledgers
- All values are cumulative to the row's date

---

## Scenario: Capital ledger only (no income ledger)

Useful for checking position and cost basis without dividend income.

```powershell
python pipeline.py create_subaccount_ledger `
    "C:\Investments\ISA_SubAccount_Ledger.xlsx" `
    --capital "C:\Investments\HL_ISA_Ledger.xlsx"
```

Output will have `total_income = 0` on all rows (no dividend source).

---

## Integration into run_pipeline.ps1

A new step (Step 4) can be added after the existing Step 3 (`create_capital_ledger`) for each group
of capital+income accounts to be consolidated:

```powershell
# ── Step 4: Build consolidated sub-account ledger ─────────────────────────────
& $PythonExe $PipelinePy create_subaccount_ledger `
    $SubAccountLedgerPath `
    --capital $SIPPLedgerPath $ISALedgerPath `
    --income $SIPPIncomeLedgerPath $ISAIncomeLedgerPath
```
