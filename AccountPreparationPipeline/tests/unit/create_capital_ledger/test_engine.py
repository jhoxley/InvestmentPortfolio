from __future__ import annotations

import pandas as pd
import pytest

from src.modes.create_capital_ledger.engine import CapitalLedgerEngine
from src.modes.create_ledger.constants import (
    LEDGER_COL_TRANSACTION_ID,
    LEDGER_COL_TRANSACTION_VALUE,
)

_COLS = [
    LEDGER_COL_TRANSACTION_ID,
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    "Account Value",
    "Account Quantity",
    LEDGER_COL_TRANSACTION_VALUE,
    "Transaction Quantity",
]


def _row(
    tid: str,
    date: str,
    action: str,
    value: float,
    sub_account: str = "Cash",
) -> dict:
    return {
        LEDGER_COL_TRANSACTION_ID: tid,
        "date": date,
        "account": "Test ISA",
        "sub_account": sub_account,
        "action": action,
        "reference": "REF",
        "Account Value": value,
        "Account Quantity": value,
        LEDGER_COL_TRANSACTION_VALUE: value,
        "Transaction Quantity": value,
    }


def _df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=_COLS)


class TestCapitalLedgerEngine:
    def test_deposit_rows_accumulate_capital(self) -> None:
        df = _df(
            _row("00001-001", "2024-01-10", "deposit", 5000.0),
            _row("00002-001", "2024-02-15", "deposit", 3000.0),
        )
        result = CapitalLedgerEngine().run(df)
        capitals = result.set_index("date")["capital"]
        assert float(capitals["2024-01-10"]) == pytest.approx(5000.0)
        assert float(capitals["2024-02-15"]) == pytest.approx(8000.0)

    def test_income_rows_accumulate_income(self) -> None:
        df = _df(
            _row("00001-001", "2024-01-10", "income", 100.0),
            _row("00002-001", "2024-02-15", "income", 50.0),
        )
        result = CapitalLedgerEngine().run(df)
        incomes = result.set_index("date")["income"]
        assert float(incomes["2024-01-10"]) == pytest.approx(100.0)
        assert float(incomes["2024-02-15"]) == pytest.approx(150.0)

    def test_buy_sell_rows_accumulate_book_value(self) -> None:
        df = _df(
            _row("00001-001", "2024-03-20", "buy", -1000.0, sub_account="Fund A"),
            _row("00002-001", "2024-03-20", "buy", -2000.0, sub_account="Fund B"),
            _row("00003-001", "2024-04-10", "sell", 800.0, sub_account="Fund A"),
        )
        result = CapitalLedgerEngine().run(df)
        bvs = result.set_index("date")["book_value"]
        assert float(bvs["2024-03-20"]) == pytest.approx(-3000.0)
        assert float(bvs["2024-04-10"]) == pytest.approx(-2200.0)

    def test_forward_fill_capital_on_dates_with_no_deposit(self) -> None:
        df = _df(
            _row("00001-001", "2024-01-10", "deposit", 5000.0),
            _row("00002-001", "2024-03-20", "buy", -1000.0, sub_account="Fund A"),
        )
        result = CapitalLedgerEngine().run(df)
        capitals = result.set_index("date")["capital"]
        assert float(capitals["2024-01-10"]) == pytest.approx(5000.0)
        assert float(capitals["2024-03-20"]) == pytest.approx(5000.0)

    def test_forward_fill_all_columns_start_at_zero(self) -> None:
        df = _df(
            _row("00001-001", "2024-03-20", "buy", -1000.0, sub_account="Fund A"),
        )
        result = CapitalLedgerEngine().run(df)
        row = result.iloc[0]
        assert float(row["capital"]) == pytest.approx(0.0)
        assert float(row["income"]) == pytest.approx(0.0)
        assert float(row["book_value"]) == pytest.approx(-1000.0)

    def test_non_qualifying_actions_excluded(self) -> None:
        df = _df(
            _row("00001-001", "2024-01-10", "deposit", 5000.0),
            _row("00002-001", "2024-01-10", "trading", 999.0),
            _row("00003-001", "2024-02-15", "dividend", 50.0),
        )
        result = CapitalLedgerEngine().run(df)
        assert len(result) == 1
        assert float(result.iloc[0]["capital"]) == pytest.approx(5000.0)
        assert float(result.iloc[0]["income"]) == pytest.approx(0.0)

    def test_one_row_per_date_in_output(self) -> None:
        df = _df(
            _row("00001-001", "2024-03-20", "buy", -1000.0, sub_account="Fund A"),
            _row("00002-001", "2024-03-20", "buy", -2000.0, sub_account="Fund B"),
        )
        result = CapitalLedgerEngine().run(df)
        assert len(result) == 1
        assert float(result.iloc[0]["book_value"]) == pytest.approx(-3000.0)

    def test_empty_result_when_no_qualifying_rows(self) -> None:
        df = _df(
            _row("00001-001", "2024-01-10", "trading", 999.0),
            _row("00002-001", "2024-02-15", "dividend", 50.0),
        )
        result = CapitalLedgerEngine().run(df)
        assert len(result) == 0
        assert list(result.columns) == ["date", "capital", "income", "book_value"]

    def test_output_columns(self) -> None:
        df = _df(_row("00001-001", "2024-01-10", "deposit", 5000.0))
        result = CapitalLedgerEngine().run(df)
        assert list(result.columns) == ["date", "capital", "income", "book_value"]

    def test_transaction_id_order_used_for_accumulation(self) -> None:
        df = _df(
            _row("00004-001", "2024-03-20", "buy", -2000.0, sub_account="Fund B"),
            _row("00003-001", "2024-03-20", "buy", -1000.0, sub_account="Fund A"),
        )
        result = CapitalLedgerEngine().run(df)
        assert len(result) == 1
        assert float(result.iloc[0]["book_value"]) == pytest.approx(-3000.0)
