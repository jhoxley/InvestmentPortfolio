from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd

from src.modes.consolidate_journals.constants import DEPOSIT_SUFFIX, JOURNAL_COLUMNS, OFFSET_SUFFIX
from src.modes.consolidate_journals.offset_generator import OffsetGenerator
from src.modes.consolidate_journals.schema import ActionType, JournalEvent


def _buy(
    reference: str = "B001",
    value: str = "-1000.00",
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
    value: str = "75.00",
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


def _dividend(
    reference: str = "ST DIV",
    value: str = "64.71",
    date: str = "2026-03-31",
) -> JournalEvent:
    return JournalEvent(
        date=datetime.date.fromisoformat(date),
        account="ISA Income",
        sub_account="Barclays plc Ordinary 25p",
        action=ActionType.DIVIDEND,
        reference=reference,
        value=Decimal(value),
        quantity=Decimal(value),
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

    def test_buy_offset_value_mirrors_trade(self) -> None:
        offset = OffsetGenerator().generate([_buy(value="-1000.00")])[0]
        assert offset.value == Decimal("-1000.00")

    def test_buy_offset_quantity_mirrors_trade_value(self) -> None:
        offset = OffsetGenerator().generate([_buy(value="-1000.00", quantity="10.00")])[0]
        assert offset.quantity == Decimal("-1000.00")

    def test_buy_offset_date_matches_trade(self) -> None:
        buy = _buy(date="2024-03-15")
        offset = OffsetGenerator().generate([buy])[0]
        assert offset.date == datetime.date(2024, 3, 15)

    def test_buy_offset_account_matches_trade(self) -> None:
        offset = OffsetGenerator().generate([_buy()])[0]
        assert offset.account == "ISA"

    def test_sell_offset_value_mirrors_trade(self) -> None:
        offset = OffsetGenerator().generate([_sell(value="75.00")])[0]
        assert offset.value == Decimal("75.00")

    def test_sell_offset_quantity_mirrors_trade_value(self) -> None:
        offset = OffsetGenerator().generate([_sell(value="75.00", quantity="50.00")])[0]
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


class TestOffsetGeneratorDividend:
    def test_generate_returns_offset_for_dividend_event(self) -> None:
        offsets = OffsetGenerator().generate([_dividend()])
        assert len(offsets) == 1
        offset = offsets[0]
        assert offset.sub_account == "Cash"
        assert offset.action == ActionType.TRADING
        assert offset.reference == "ST DIV-offset"
        assert offset.value == Decimal("64.71")
        assert offset.quantity == Decimal("64.71")
        assert offset.value > 0  # SC-002: dividend offset value must be positive
        assert offset.quantity > 0  # SC-002: dividend offset quantity must be positive

    def test_generate_skips_non_offset_actions(self) -> None:
        def _make(action: ActionType) -> JournalEvent:
            return JournalEvent(
                date=datetime.date(2026, 3, 31),
                account="ISA",
                sub_account="Cash",
                action=action,
                reference="REF",
                value=Decimal("100.00"),
                quantity=None,
            )

        for action in (ActionType.DEPOSIT, ActionType.INCOME, ActionType.FEE, ActionType.TRADING):
            result = OffsetGenerator().generate([_make(action)])
            assert result == [], f"Expected no offset for action {action}"

    def test_generate_returns_offset_for_all_dividend_reference_types(self) -> None:
        events = [
            _dividend(reference="ST DIV"),
            _dividend(reference="OVR CR"),
            _dividend(reference="UTC CR"),
            _dividend(reference="UTO CR"),
            _dividend(reference="LOYALTYU"),
            _dividend(reference="LOYALTYC"),
        ]
        offsets = OffsetGenerator().generate(events)
        assert len(offsets) == 6
        refs = {o.reference for o in offsets}
        assert refs == {
            "ST DIV-offset",
            "OVR CR-offset",
            "UTC CR-offset",
            "UTO CR-offset",
            "LOYALTYU-offset",
            "LOYALTYC-offset",
        }


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
                    "value": -1000.0,
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
                    "value": 75.0,
                    "quantity": 50.0,
                }
            ],
            columns=JOURNAL_COLUMNS,
        )

    def test_buy_df_produces_offset(self) -> None:
        offsets = OffsetGenerator().generate_from_df(self._df_with_buy())
        assert len(offsets) == 1
        assert offsets[0].reference == "B12345" + OFFSET_SUFFIX

    def test_buy_df_offset_value_mirrors_trade(self) -> None:
        offsets = OffsetGenerator().generate_from_df(self._df_with_buy())
        assert offsets[0].value == Decimal("-1000.0")

    def test_sell_df_offset_value_mirrors_trade(self) -> None:
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


def _lodgement(
    reference: str = "L003538235",
    value: str = "-2288.89",
    date: str = "2018-07-12",
) -> JournalEvent:
    return JournalEvent(
        date=datetime.date.fromisoformat(date),
        account="ISA",
        sub_account="Barclays plc Ordinary 25p",
        action=ActionType.LODGEMENT,
        reference=reference,
        value=Decimal(value),
        quantity=Decimal("1221"),
    )


class TestLodgementCompanions:
    def _companions(self, ref: str = "L003538235", value: str = "-2288.89") -> list[JournalEvent]:
        return OffsetGenerator().generate([_lodgement(reference=ref, value=value)])

    def test_lodgement_produces_two_companions(self) -> None:
        assert len(self._companions()) == 2

    def test_lodgement_deposit_action(self) -> None:
        companions = self._companions()
        assert any(c.action == ActionType.DEPOSIT for c in companions)

    def test_lodgement_deposit_sub_account_is_cash(self) -> None:
        companions = self._companions()
        deposit = next(c for c in companions if c.action == ActionType.DEPOSIT)
        assert deposit.sub_account == "Cash"

    def test_lodgement_deposit_reference_has_deposit_suffix(self) -> None:
        companions = self._companions(ref="L003538235")
        deposit = next(c for c in companions if c.action == ActionType.DEPOSIT)
        assert deposit.reference == "L003538235" + DEPOSIT_SUFFIX

    def test_lodgement_deposit_value_is_negated(self) -> None:
        companions = self._companions(value="-2288.89")
        deposit = next(c for c in companions if c.action == ActionType.DEPOSIT)
        assert deposit.value == Decimal("2288.89")

    def test_lodgement_deposit_sum_with_lodgement_is_zero(self) -> None:
        lodgement = _lodgement(value="-2288.89")
        companions = OffsetGenerator().generate([lodgement])
        deposit = next(c for c in companions if c.action == ActionType.DEPOSIT)
        assert lodgement.value + deposit.value == Decimal("0")

    def test_lodgement_deposit_quantity_is_none(self) -> None:
        companions = self._companions()
        deposit = next(c for c in companions if c.action == ActionType.DEPOSIT)
        assert deposit.quantity is None

    def test_lodgement_trading_action(self) -> None:
        companions = self._companions()
        assert any(c.action == ActionType.TRADING for c in companions)

    def test_lodgement_trading_sub_account_is_cash(self) -> None:
        companions = self._companions()
        trading = next(c for c in companions if c.action == ActionType.TRADING)
        assert trading.sub_account == "Cash"

    def test_lodgement_trading_reference_has_offset_suffix(self) -> None:
        companions = self._companions(ref="L003538235")
        trading = next(c for c in companions if c.action == ActionType.TRADING)
        assert trading.reference == "L003538235" + OFFSET_SUFFIX

    def test_lodgement_trading_value_mirrors_lodgement(self) -> None:
        companions = self._companions(value="-2288.89")
        trading = next(c for c in companions if c.action == ActionType.TRADING)
        assert trading.value == Decimal("-2288.89")

    def test_lodgement_trading_quantity_is_none(self) -> None:
        companions = self._companions()
        trading = next(c for c in companions if c.action == ActionType.TRADING)
        assert trading.quantity is None

    def test_lodgement_date_account_inherited(self) -> None:
        lodgement = _lodgement(date="2018-07-12")
        companions = OffsetGenerator().generate([lodgement])
        assert len(companions) == 2
        for c in companions:
            assert c.date == datetime.date(2018, 7, 12)
            assert c.account == "ISA"

    def test_two_lodgements_produce_four_companions(self) -> None:
        companions = OffsetGenerator().generate(
            [_lodgement(reference="L001"), _lodgement(reference="L002")]
        )
        assert len(companions) == 4

    def test_mixed_events_lodgement_and_buy(self) -> None:
        companions = OffsetGenerator().generate([_buy(), _lodgement()])
        assert len(companions) == 3

    def test_generate_from_df_lodgement(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "date": "2018-07-12",
                    "account": "ISA",
                    "sub_account": "Barclays plc Ordinary 25p",
                    "action": "lodgement",
                    "reference": "L003538235",
                    "value": -2288.89,
                    "quantity": 1221.0,
                }
            ],
            columns=JOURNAL_COLUMNS,
        )
        companions = OffsetGenerator().generate_from_df(df)
        assert len(companions) == 2
        assert any(c.action == ActionType.DEPOSIT for c in companions)
        assert any(c.action == ActionType.TRADING for c in companions)
