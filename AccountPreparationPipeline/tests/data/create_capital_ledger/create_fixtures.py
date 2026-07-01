"""Run once to regenerate the XLSX fixtures for create_capital_ledger BDD and unit tests."""

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

_SIMPLE_ROWS = [
    (
        "00001-001",
        "2024-01-10",
        "Test ISA",
        "Cash",
        "deposit",
        "Deposit",
        5000.00,
        5000.00,
        5000.00,
        5000.00,
    ),
    (
        "00002-001",
        "2024-02-15",
        "Test ISA",
        "Cash",
        "income",
        "Commission",
        5120.00,
        5120.00,
        120.00,
        120.00,
    ),
    (
        "00003-001",
        "2024-03-20",
        "Test ISA",
        "Fund A",
        "buy",
        "B00001",
        4120.00,
        10.00,
        -1000.00,
        10.00,
    ),
    (
        "00004-001",
        "2024-03-20",
        "Test ISA",
        "Fund B",
        "buy",
        "B00002",
        2120.00,
        20.00,
        -2000.00,
        20.00,
    ),
    (
        "00005-001",
        "2024-04-10",
        "Test ISA",
        "Fund A",
        "sell",
        "S00001",
        2920.00,
        5.00,
        800.00,
        -5.00,
    ),
]

_EXTRA_ROWS = [
    (
        "00006-001",
        "2024-03-20",
        "Test ISA",
        "Cash",
        "trading",
        "B00001-offset",
        3120.00,
        3120.00,
        1000.00,
        1000.00,
    ),
    (
        "00007-001",
        "2024-02-15",
        "Test ISA",
        "Fund C",
        "dividend",
        "ST DIV",
        50.00,
        50.00,
        50.00,
        50.00,
    ),
]


def _make_df(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=LEDGER_COLUMNS)


def main() -> None:
    simple = _make_df(_SIMPLE_ROWS)
    simple.to_excel(HERE / "simple_ledger.xlsx", index=False, engine="openpyxl")
    print("Written: simple_ledger.xlsx")

    mixed = _make_df(_SIMPLE_ROWS + _EXTRA_ROWS)
    mixed.to_excel(HERE / "mixed_actions_ledger.xlsx", index=False, engine="openpyxl")
    print("Written: mixed_actions_ledger.xlsx")


if __name__ == "__main__":
    main()
