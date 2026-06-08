from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd

from src.modes.consolidate_journals.constants import JOURNAL_COLUMNS, OFFSET_SUFFIX
from src.modes.consolidate_journals.offset_generator import OffsetGenerator
from src.modes.consolidate_journals.schema import ActionType, JournalEvent


def _buy(
    reference: str = "B001",
    value: str = "1000.00",
    quantity: str = "10.00",
    date: str = "2024-01-15",
) -> JournalEvent:
    return JournalEvent(
        date=datetime.date.fromisoformat(date),
        account="ISA",
        sub_account="Vanguard Fund",
        action=ActionType.BUY,
        reference=reference,
        value=Decimal(value),
        quantity=Decimal(quantity),
    )


def _sell(
    reference: str = "S001",
    value: str = "-75.00",
    quantity: str = "50.00",
    date: str = "2024-02-20",
) -> JournalEvent:
    return JournalEvent(
        date=datetime.date.fromisoformat(date),
        account="ISA",
        sub_account="Barclays PLC",
        action=ActionType.SELL,
        reference=reference,
        value=Decimal(value),
        quantity=Decimal(quantity),
    )


def _deposit(reference: str = "Deposit") -> JournalEvent:
    return JournalEvent(
        date=datetime.date(2024, 1, 5),
        account="ISA",
        sub_account="Cash",
        action=ActionType.DEPOSIT,
        reference=reference,
        value=Decimal("500.00"),
        quantity=None,
    )


class TestGenerateFromList:
    def test_buy_produces_one_offset(self) -> None:
        offsets = OffsetGenerator().generate([_buy()])
        assert len(offsets) == 1

    def test_buy_offset_sub_account_is_cash(self) -> None:
        offset = OffsetGenerator().generate([_buy()])[0]
        assert offset.sub_account == "Cash"

    def test_buy_offset_action_is_trading(self) -> None:
        offset = OffsetGenerator().generate([_buy()])[0]
        assert offset.action == ActionType.TRADING

    def test_buy_offset_reference_has_suffix(self) -> None:
        offset = OffsetGenerator().generate([_buy(reference="B12345")])[0]
        assert offset.reference == "B12345-offset"

    def test_buy_offset_value_is_negated(self) -> None:
        offset = OffsetGenerator().generate([_buy(value="1000.00")])[0]
        assert offset.value == Decimal("-1000.00")

    def test_buy_offset_quantity_equals_negated_value(self) -> None:
        offset = OffsetGenerator().generate([_buy(value="1000.00", quantity="10.00")])[0]
        assert offset.quantity == Decimal("-1000.00")

    def test_buy_offset_date_matches_trade(self) -> None:
        buy = _buy(date="2024-03-15")
        offset = OffsetGenerator().generate([buy])[0]
        assert offset.date == datetime.date(2024, 3, 15)

    def test_buy_offset_account_matches_trade(self) -> None:
        offset = OffsetGenerator().generate([_buy()])[0]
        assert offset.account == "ISA"

    def test_sell_produces_offset_with_positive_value(self) -> None:
        # HL stores sell proceeds as negative; negating gives positive cash inflow
        offset = OffsetGenerator().generate([_sell(value="-75.00")])[0]
        assert offset.value == Decimal("75.00")

    def test_sell_offset_quantity_equals_negated_sell_value(self) -> None:
        offset = OffsetGenerator().generate([_sell(value="-75.00", quantity="50.00")])[0]
        assert offset.quantity == Decimal("75.00")

    def test_deposit_produces_no_offset(self) -> None:
        offsets = OffsetGenerator().generate([_deposit()])
        assert offsets == []

    def test_income_produces_no_offset(self) -> None:
        income = JournalEvent(
            date=datetime.date(2024, 1, 1),
            account="ISA",
            sub_account="Cash",
            action=ActionType.INCOME,
            reference="URI001",
            value=Decimal("10.00"),
            quantity=None,
        )
        assert OffsetGenerator().generate([income]) == []

    def test_fee_produces_no_offset(self) -> None:
        fee = JournalEvent(
            date=datetime.date(2024, 1, 1),
            account="ISA",
            sub_account="Cash",
            action=ActionType.FEE,
            reference="MANAGE FEE",
            value=Decimal("-5.00"),
            quantity=None,
        )
        assert OffsetGenerator().generate([fee]) == []

    def test_empty_input_returns_empty_list(self) -> None:
        assert OffsetGenerator().generate([]) == []

    def test_multiple_trades_produce_correct_count(self) -> None:
        events = [_buy("B001"), _sell("S001"), _deposit(), _buy("B002")]
        offsets = OffsetGenerator().generate(events)
        assert len(offsets) == 3

    def test_output_contains_no_none_quantity(self) -> None:
        offset = OffsetGenerator().generate([_buy()])[0]
        assert offset.quantity is not None


class TestGenerateFromDf:
    def _df_with_buy(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-15",
                    "account": "ISA",
                    "sub_account": "Vanguard Fund",
                    "action": "buy",
                    "reference": "B12345",
                    "value": 1000.0,
                    "quantity": 10.0,
                }
            ],
            columns=JOURNAL_COLUMNS,
        )

    def _df_with_sell(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "date": "2024-02-20",
                    "account": "ISA",
                    "sub_account": "Barclays PLC",
                    "action": "sell",
                    "reference": "S67890",
                    "value": -75.0,
                    "quantity": 50.0,
                }
            ],
            columns=JOURNAL_COLUMNS,
        )

    def test_buy_df_produces_offset(self) -> None:
        offsets = OffsetGenerator().generate_from_df(self._df_with_buy())
        assert len(offsets) == 1
        assert offsets[0].reference == "B12345" + OFFSET_SUFFIX

    def test_buy_df_offset_value_negated(self) -> None:
        offsets = OffsetGenerator().generate_from_df(self._df_with_buy())
        assert offsets[0].value == Decimal("-1000.0")

    def test_sell_df_offset_value_positive(self) -> None:
        offsets = OffsetGenerator().generate_from_df(self._df_with_sell())
        assert offsets[0].value == Decimal("75.0")

    def test_empty_df_returns_empty(self) -> None:
        empty = pd.DataFrame(columns=JOURNAL_COLUMNS)
        assert OffsetGenerator().generate_from_df(empty) == []

    def test_generate_from_df_matches_generate_from_list(self) -> None:
        df = self._df_with_buy()
        from_df = OffsetGenerator().generate_from_df(df)
        from_list = OffsetGenerator().generate([_buy(reference="B12345")])
        assert len(from_df) == len(from_list)
        assert from_df[0].reference == from_list[0].reference
        assert from_df[0].value == from_list[0].value
        assert from_df[0].quantity == from_list[0].quantity
