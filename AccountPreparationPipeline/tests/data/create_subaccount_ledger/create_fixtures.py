"""Run once to regenerate the XLSX fixtures for create_subaccount_ledger BDD tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

LEDGER_COLUMNS = [
    "Transaction ID",
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    "Account Value",
    "Account Quantity",
    "Transaction Value",
    "Transaction Quantity",
]

HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# capital_ledger_a.xlsx - SIPP-like capital ledger
# Barclays plc: buy + lodgement on 2024-01-10, buy on 2024-03-15, sell on 2024-06-01
# Cash: deposit on 2024-01-10, trading offsets on 2024-01-10 and 2024-03-15
#
# Expected "Barclays plc" cumulative output:
#   2024-01-10: book_cost = buy(+200) + negate_lodgement(-(-500)) = 700; qty = 100+300 = 400
#   2024-03-15: book_cost = 700+150 = 850; qty = 450
#   2024-06-01: book_cost = 850+(-75) = 775; qty = 425
#
# Expected Cash cumulative output:
#   2024-01-10: 5000 + (-200) = 4800
#   2024-03-15: 4800 + (-150) = 4650
# ---------------------------------------------------------------------------
_CAPITAL_A_ROWS = [
    ("00001-001", "2024-01-10", "HL SIPP", "Cash", "deposit", "REF001", 5000.00, 0, 5000.00, 0),
    (
        "00002-001",
        "2024-01-10",
        "HL SIPP",
        "Barclays plc",
        "buy",
        "REF002",
        200.00,
        100,
        200.00,
        100,
    ),
    (
        "00002-002",
        "2024-01-10",
        "HL SIPP",
        "Cash",
        "trading",
        "REF002-offset",
        4800.00,
        0,
        -200.00,
        0,
    ),
    (
        "00003-001",
        "2024-01-10",
        "HL SIPP",
        "Barclays plc",
        "lodgement",
        "REF003",
        700.00,
        400,
        -500.00,
        300,
    ),
    (
        "00004-001",
        "2024-03-15",
        "HL SIPP",
        "Barclays plc",
        "buy",
        "REF004",
        850.00,
        450,
        150.00,
        50,
    ),
    (
        "00004-002",
        "2024-03-15",
        "HL SIPP",
        "Cash",
        "trading",
        "REF004-offset",
        4650.00,
        0,
        -150.00,
        0,
    ),
    (
        "00005-001",
        "2024-06-01",
        "HL SIPP",
        "Barclays plc",
        "sell",
        "REF005",
        775.00,
        425,
        -75.00,
        -25,
    ),
]

# ---------------------------------------------------------------------------
# capital_ledger_b.xlsx - second capital ledger with overlapping and distinct sub-accounts
# "Barclays plc" also held in ISA (overlapping); "HSBC Fund" is distinct.
#
# Expected merged "Barclays plc" (a + b combined):
#   2024-01-10: book_cost=700, qty=400 (capital_a only)
#   2024-02-01: book_cost=875, qty=450 (+175 / +50 from capital_b)
#   2024-03-15: book_cost=1025, qty=500 (+150 / +50 from capital_a)
#   2024-06-01: book_cost=950, qty=475 (-75 / -25 from capital_a)
# ---------------------------------------------------------------------------
_CAPITAL_B_ROWS = [
    ("00010-001", "2024-02-01", "HL ISA", "Barclays plc", "buy", "REF010", 175.00, 50, 175.00, 50),
    ("00011-001", "2024-02-01", "HL ISA", "HSBC Fund", "buy", "REF011", 300.00, 200, 300.00, 200),
    (
        "00011-002",
        "2024-02-01",
        "HL ISA",
        "Cash",
        "deposit",
        "REF011-dep",
        2000.00,
        0,
        2000.00,
        0,
    ),
]

# ---------------------------------------------------------------------------
# income_ledger_a.xlsx - income ledger with dividends and Cash rows
# Dividends for "Barclays plc": TV=25 on 2024-04-01, TV=30 on 2024-07-01
# Cash rows (income action): MUST be excluded from output (FR-007)
#
# Expected "Barclays plc" total_income: 2024-04-01 -> 25.00; 2024-07-01 -> 55.00
# ---------------------------------------------------------------------------
_INCOME_A_ROWS = [
    (
        "00020-001",
        "2024-04-01",
        "HL SIPP Income",
        "Barclays plc",
        "dividend",
        "DIV001",
        25.00,
        425,
        25.00,
        425,
    ),
    (
        "00020-002",
        "2024-04-01",
        "HL SIPP Income",
        "Cash",
        "income",
        "DIV001-cash",
        25.00,
        0,
        25.00,
        0,
    ),
    (
        "00021-001",
        "2024-07-01",
        "HL SIPP Income",
        "Barclays plc",
        "dividend",
        "DIV002",
        55.00,
        425,
        30.00,
        425,
    ),
    (
        "00021-002",
        "2024-07-01",
        "HL SIPP Income",
        "Cash",
        "income",
        "DIV002-cash",
        55.00,
        0,
        30.00,
        0,
    ),
]


def _make_df(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=LEDGER_COLUMNS)


def main() -> None:
    capital_a = _make_df(_CAPITAL_A_ROWS)
    capital_a.to_excel(HERE / "capital_ledger_a.xlsx", index=False, engine="openpyxl")
    print(f"Written: capital_ledger_a.xlsx ({len(capital_a)} rows)")

    capital_b = _make_df(_CAPITAL_B_ROWS)
    capital_b.to_excel(HERE / "capital_ledger_b.xlsx", index=False, engine="openpyxl")
    print(f"Written: capital_ledger_b.xlsx ({len(capital_b)} rows)")

    income_a = _make_df(_INCOME_A_ROWS)
    income_a.to_excel(HERE / "income_ledger_a.xlsx", index=False, engine="openpyxl")
    print(f"Written: income_ledger_a.xlsx ({len(income_a)} rows)")


if __name__ == "__main__":
    main()
