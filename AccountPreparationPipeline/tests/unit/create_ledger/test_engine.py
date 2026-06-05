from __future__ import annotations

import pandas as pd
import pytest

from src.modes.consolidate_journals.constants import JOURNAL_COLUMNS
from src.modes.create_ledger.engine import LedgerEngine


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=JOURNAL_COLUMNS)


def _row(
    date: str = "2024-01-01",
    account: str = "ISA",
    sub_account: str = "Vanguard Fund",
    action: str = "buy",
    reference: str = "B001",
    value: float = 1000.0,
    quantity: float | None = 10.0,
) -> dict:
    return {
        "date": date,
        "account": account,
        "sub_account": sub_account,
        "action": action,
        "reference": reference,
        "value": value,
        "quantity": quantity,
    }


class TestBuyEvents:
    def test_single_buy_negates_value(self) -> None:
        df = _make_df([_row(value=1000.0, quantity=10.0)])
        result = LedgerEngine().run(df)
        assert result.iloc[0]["value"] == pytest.approx(-1000.0)

    def test_single_buy_quantity_unchanged(self) -> None:
        df = _make_df([_row(value=1000.0, quantity=10.0)])
        result = LedgerEngine().run(df)
        assert result.iloc[0]["quantity"] == pytest.approx(10.0)

    def test_two_buys_cumulate_value(self) -> None:
        df = _make_df(
            [
                _row(date="2024-01-01", value=1000.0, quantity=10.0, reference="B001"),
                _row(date="2024-01-02", value=500.0, quantity=5.0, reference="B002"),
            ]
        )
        result = LedgerEngine().run(df)
        assert result.iloc[0]["value"] == pytest.approx(-1000.0)
        assert result.iloc[1]["value"] == pytest.approx(-1500.0)

    def test_two_buys_cumulate_quantity(self) -> None:
        df = _make_df(
            [
                _row(date="2024-01-01", value=1000.0, quantity=10.0, reference="B001"),
                _row(date="2024-01-02", value=500.0, quantity=5.0, reference="B002"),
            ]
        )
        result = LedgerEngine().run(df)
        assert result.iloc[1]["quantity"] == pytest.approx(15.0)


class TestSellEvents:
    def test_sell_negates_value(self) -> None:
        df = _make_df([_row(action="sell", value=500.0, quantity=5.0, reference="S001")])
        result = LedgerEngine().run(df)
        assert result.iloc[0]["value"] == pytest.approx(-500.0)

    def test_sell_negates_quantity(self) -> None:
        df = _make_df([_row(action="sell", value=500.0, quantity=5.0, reference="S001")])
        result = LedgerEngine().run(df)
        assert result.iloc[0]["quantity"] == pytest.approx(-5.0)

    def test_buy_then_sell_reduces_quantity(self) -> None:
        df = _make_df(
            [
                _row(
                    date="2024-01-01", action="buy", value=1000.0, quantity=10.0, reference="B001"
                ),
                _row(date="2024-01-02", action="sell", value=300.0, quantity=3.0, reference="S001"),
            ]
        )
        result = LedgerEngine().run(df)
        assert result.iloc[1]["quantity"] == pytest.approx(7.0)

    def test_buy_then_sell_cumulates_value(self) -> None:
        df = _make_df(
            [
                _row(
                    date="2024-01-01", action="buy", value=1000.0, quantity=10.0, reference="B001"
                ),
                _row(date="2024-01-02", action="sell", value=300.0, quantity=3.0, reference="S001"),
            ]
        )
        result = LedgerEngine().run(df)
        assert result.iloc[1]["value"] == pytest.approx(-1300.0)


class TestCashRows:
    def test_blank_quantity_filled_from_value(self) -> None:
        df = _make_df([_row(sub_account="Cash", action="deposit", value=1000.0, quantity=None)])
        result = LedgerEngine().run(df)
        assert result.iloc[0]["quantity"] == pytest.approx(1000.0)

    def test_cash_value_not_negated(self) -> None:
        df = _make_df([_row(sub_account="Cash", action="deposit", value=1000.0, quantity=None)])
        result = LedgerEngine().run(df)
        assert result.iloc[0]["value"] == pytest.approx(1000.0)

    def test_two_cash_deposits_cumulate_both_columns(self) -> None:
        df = _make_df(
            [
                _row(
                    date="2024-01-01",
                    sub_account="Cash",
                    action="deposit",
                    value=1000.0,
                    quantity=None,
                    reference="Deposit",
                ),
                _row(
                    date="2024-01-02",
                    sub_account="Cash",
                    action="deposit",
                    value=500.0,
                    quantity=None,
                    reference="Deposit",
                ),
            ]
        )
        result = LedgerEngine().run(df)
        assert result.iloc[1]["value"] == pytest.approx(1500.0)
        assert result.iloc[1]["quantity"] == pytest.approx(1500.0)


class TestPositionIsolation:
    def test_two_positions_accumulate_independently(self) -> None:
        df = _make_df(
            [
                _row(sub_account="Fund A", value=1000.0, quantity=10.0, reference="B001"),
                _row(sub_account="Fund B", value=2000.0, quantity=20.0, reference="B002"),
            ]
        )
        result = LedgerEngine().run(df)
        fund_a = result[result["sub_account"] == "Fund A"].iloc[0]
        fund_b = result[result["sub_account"] == "Fund B"].iloc[0]
        assert fund_a["value"] == pytest.approx(-1000.0)
        assert fund_b["value"] == pytest.approx(-2000.0)


class TestRowCountAndSchema:
    def test_row_count_preserved(self) -> None:
        df = _make_df([_row(reference=f"B00{i}") for i in range(5)])
        result = LedgerEngine().run(df)
        assert len(result) == 5

    def test_output_columns_match_journal_columns(self) -> None:
        df = _make_df([_row()])
        result = LedgerEngine().run(df)
        assert list(result.columns) == JOURNAL_COLUMNS

    def test_action_column_unchanged(self) -> None:
        df = _make_df(
            [
                _row(action="buy", reference="B001"),
                _row(action="sell", reference="S001"),
            ]
        )
        result = LedgerEngine().run(df)
        assert list(result["action"]) == ["buy", "sell"]

    def test_reference_column_unchanged(self) -> None:
        df = _make_df([_row(reference="B12345")])
        result = LedgerEngine().run(df)
        assert result.iloc[0]["reference"] == "B12345"

    def test_missing_column_raises_value_error(self) -> None:
        df = pd.DataFrame({"date": ["2024-01-01"], "value": [100.0]})
        with pytest.raises(ValueError, match="missing"):
            LedgerEngine().run(df)
