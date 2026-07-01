from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.modes.consolidate_journals.parsers.hl import (
    HLFragmentParser,
    _map_action,
    _strip_dividend_suffix,
)
from src.modes.consolidate_journals.schema import ActionType

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "consolidate_journals"

ACCOUNT = "Test ISA"


class TestHeaderDiscovery:
    def test_finds_header_in_file_without_preamble(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        assert len(result.errors) == 0
        assert len(result.events) == 3

    def test_finds_header_after_preamble_rows(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_with_preamble.csv", ACCOUNT)
        assert len(result.errors) == 0
        assert len(result.events) == 3

    def test_no_header_returns_file_level_error(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "invalid_no_header.csv", ACCOUNT)
        assert len(result.events) == 0
        assert len(result.errors) == 1
        assert result.errors[0].line_number is None
        assert "header" in result.errors[0].message.lower()


class TestActionMapping:
    def test_b_reference_maps_to_buy(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        buy_events = [e for e in result.events if e.action == ActionType.BUY]
        assert len(buy_events) == 2
        refs = {e.reference for e in buy_events}
        assert "B12345" in refs
        assert "B11111" in refs

    def test_s_reference_maps_to_sell(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        sell_events = [e for e in result.events if e.action == ActionType.SELL]
        assert len(sell_events) == 1
        assert sell_events[0].reference == "S67890"

    def test_deposit_reference_maps_to_deposit(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib.csv", ACCOUNT)
        deposit_events = [e for e in result.events if e.action == ActionType.DEPOSIT]
        assert len(deposit_events) == 2

    def test_bacs_reference_maps_to_deposit(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib.csv", ACCOUNT)
        bacs_event = next(e for e in result.events if e.reference == "BACS")
        assert bacs_event.action == ActionType.DEPOSIT

    def test_contrib_reference_maps_to_deposit(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib_ref.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "contrib")
        assert event.action == ActionType.DEPOSIT

    def test_transfer_without_income_description_maps_to_deposit(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_transfer_uri.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "Transfer")
        assert event.action == ActionType.DEPOSIT

    def test_transfer_with_income_description_maps_to_income(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_income_transfer.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "Transfer")
        assert event.action == ActionType.INCOME

    def test_uri_reference_maps_to_income(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_transfer_uri.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "URI0745088")
        assert event.action == ActionType.INCOME

    def test_manage_fee_reference_maps_to_fee(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fee_interest.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "MANAGE FEE")
        assert event.action == ActionType.FEE

    def test_interest_reference_maps_to_income(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fee_interest.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "INTEREST")
        assert event.action == ActionType.INCOME

    def test_rdp_cr_reference_maps_to_income(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_rdp_cr.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "RDP CR")
        assert event.action == ActionType.INCOME

    def test_card_web_reference_maps_to_deposit(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_card_web.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "Card Web")
        assert event.action == ActionType.DEPOSIT

    def test_card_web_reference_is_case_insensitive(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_card_web.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "card web")
        assert event.action == ActionType.DEPOSIT

    def test_card_web_sub_account_is_cash(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_card_web.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "Card Web")
        assert event.sub_account == "Cash"

    def test_fpc_reference_maps_to_deposit(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fpc.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "FPC")
        assert event.action == ActionType.DEPOSIT

    def test_fpc_reference_is_case_insensitive(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fpc.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "fpc")
        assert event.action == ActionType.DEPOSIT

    def test_fpc_sub_account_is_cash(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fpc.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "FPC")
        assert event.sub_account == "Cash"

    def test_card_web_prefix_does_not_map_to_deposit(self) -> None:
        with pytest.raises(ValueError, match="Unknown action"):
            _map_action("Card Web2", "")

    def test_mixed_reference_file_parses_without_error(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_mixed_refs.csv", ACCOUNT)
        assert len(result.errors) == 0
        refs = {e.reference for e in result.events}
        assert "Card Web" in refs
        assert "Deposit" in refs
        assert "INTEREST" in refs

    def test_commission_reference_maps_to_income(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_commission.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "Commission")
        assert event.action == ActionType.INCOME

    def test_commission_reference_is_case_insensitive(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_commission.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "COMMISSION")
        assert event.action == ActionType.INCOME

    def test_commission_sub_account_is_cash(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_commission.csv", ACCOUNT)
        event = next(e for e in result.events if e.reference == "Commission")
        assert event.sub_account == "Cash"

    def test_correction_reference_maps_to_income(self) -> None:
        result = _map_action("CORRECTION", "Reverse LF Equity Income 12 22 Gross Loyalty")
        assert result == ActionType.INCOME

    def test_st_div_reference_maps_to_dividend(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_st_div.csv", ACCOUNT)
        assert len(result.errors) == 0
        assert all(e.action == ActionType.DIVIDEND for e in result.events)

    def test_ovr_cr_reference_maps_to_dividend(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_ovr_cr.csv", ACCOUNT)
        assert len(result.errors) == 0
        assert all(e.action == ActionType.DIVIDEND for e in result.events)

    def test_utc_cr_reference_maps_to_dividend(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_utc_cr.csv", ACCOUNT)
        assert len(result.errors) == 0
        assert all(e.action == ActionType.DIVIDEND for e in result.events)

    def test_loyaltyu_reference_maps_to_dividend(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_loyaltyu.csv", ACCOUNT)
        assert len(result.errors) == 0
        assert all(e.action == ActionType.DIVIDEND for e in result.events)

    def test_uto_cr_reference_maps_to_dividend(self) -> None:
        result = _map_action(
            "UTO CR",
            "Lindsell Train Global Equity Class D - Income (GBP) UT Offshore Dividend",
        )
        assert result == ActionType.DIVIDEND

    def test_loyaltyc_reference_maps_to_dividend(self) -> None:
        result = _map_action(
            "LOYALTYC",
            "LF Equity Income Class Z - Accumulation (GBP) 12 22 Gross Loyalty",
        )
        assert result == ActionType.DIVIDEND


class TestDividendSubAccount:
    def test_st_div_sub_account_strips_dividend_payment_suffix(self) -> None:
        result = _strip_dividend_suffix("ST DIV", "Barclays plc Ordinary 25p Dividend Payment")
        assert result == "Barclays plc Ordinary 25p"

    def test_ovr_cr_sub_account_strips_overseas_dividend_payment_suffix(self) -> None:
        result = _strip_dividend_suffix(
            "OVR CR", "Man Group plc ORD USD0.0342857142 Overseas Dividend Payment"
        )
        assert result == "Man Group plc ORD USD0.0342857142"

    def test_utc_cr_eql_suffix_stripped(self) -> None:
        result = _strip_dividend_suffix(
            "UTC CR", "HSBC FTSE 250 Index Class S - Income (GBP) Eql - UT Cash Payment"
        )
        assert result == "HSBC FTSE 250 Index Class S - Income (GBP)"

    def test_utc_cr_plain_suffix_stripped(self) -> None:
        result = _strip_dividend_suffix(
            "UTC CR", "HSBC FTSE 250 Index Class S - Income (GBP) UT Cash Payment"
        )
        assert result == "HSBC FTSE 250 Index Class S - Income (GBP)"

    def test_loyaltyu_sub_account_strips_04_26_suffix(self) -> None:
        result = _strip_dividend_suffix(
            "LOYALTYU",
            "JPMorgan Emerging Markets Class C - Accumulation (GBP) 04 26 Gross Loyalty",
        )
        assert result == "JPMorgan Emerging Markets Class C - Accumulation (GBP)"

    def test_loyaltyu_sub_account_strips_01_26_suffix(self) -> None:
        result = _strip_dividend_suffix(
            "LOYALTYU",
            "JPMorgan Emerging Markets Class C - Accumulation (GBP) 01 26 Gross Loyalty",
        )
        assert result == "JPMorgan Emerging Markets Class C - Accumulation (GBP)"

    def test_loyaltyu_sub_account_strips_07_25_suffix(self) -> None:
        result = _strip_dividend_suffix(
            "LOYALTYU",
            "JPMorgan Emerging Markets Class C - Accumulation (GBP) 07 25 Gross Loyalty",
        )
        assert result == "JPMorgan Emerging Markets Class C - Accumulation (GBP)"

    def test_st_div_fallback_when_suffix_absent(self) -> None:
        result = _strip_dividend_suffix("ST DIV", "Barclays plc Ordinary 25p")
        assert result == "Barclays plc Ordinary 25p"

    def test_st_div_fallback_when_description_equals_suffix_only(self) -> None:
        result = _strip_dividend_suffix("ST DIV", " Dividend Payment")
        assert result == "ST DIV"

    def test_uto_cr_eql_suffix_stripped(self) -> None:
        result = _strip_dividend_suffix(
            "UTO CR",
            "GS Global High Yield Portfolio Class R - Income (Hedged GBP)"
            " Eql - UT Offshore Dividend",
        )
        assert result == "GS Global High Yield Portfolio Class R - Income (Hedged GBP)"

    def test_uto_cr_plain_suffix_stripped(self) -> None:
        result = _strip_dividend_suffix(
            "UTO CR",
            "Lindsell Train Global Equity Class D - Income (GBP) UT Offshore Dividend",
        )
        assert result == "Lindsell Train Global Equity Class D - Income (GBP)"

    def test_loyaltyc_sub_account_strips_loyalty_suffix(self) -> None:
        result = _strip_dividend_suffix(
            "LOYALTYC",
            "LF Equity Income Class Z - Accumulation (GBP) 12 22 Gross Loyalty",
        )
        assert result == "LF Equity Income Class Z - Accumulation (GBP)"

    def test_loyaltyu_sub_account_strips_4_digit_year_suffix(self) -> None:
        result = _strip_dividend_suffix(
            "LOYALTYU",
            "Man Japan CoreAlpha Professional Class - Accumulation (GBP) 05 2016 Gross Loyalty",
        )
        assert result == "Man Japan CoreAlpha Professional Class - Accumulation (GBP)"

    def test_loyaltyu_non_matching_pattern_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="LOYALTYU"):
            _strip_dividend_suffix("LOYALTYU", "Some Fund 4 26 Gross Loyalty")

    def test_mixed_income_file_parses_without_error(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_mixed_income.csv", ACCOUNT)
        assert len(result.errors) == 0
        assert len(result.events) == 4
        assert all(e.action == ActionType.DIVIDEND for e in result.events)


class TestDateParsing:
    def test_settle_date_used_as_event_date(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        assert result.events[0].date == datetime.date(2024, 1, 17)

    def test_account_passthrough(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        assert all(e.account == ACCOUNT for e in result.events)

    def test_reference_passthrough(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        refs = {e.reference for e in result.events}
        assert "B12345" in refs


class TestDescriptionStripping:
    def test_strips_quantity_at_price_suffix(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        vanguard_event = next(e for e in result.events if "Vanguard" in e.sub_account)
        assert "@" not in vanguard_event.sub_account
        assert vanguard_event.sub_account == "Vanguard US Equity Index Fund Acc"

    def test_deposit_action_sub_account_is_cash(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib.csv", ACCOUNT)
        deposit_event = next(e for e in result.events if e.reference == "Deposit")
        assert deposit_event.sub_account == "Cash"

    def test_fee_action_sub_account_is_cash(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fee_interest.csv", ACCOUNT)
        fee_event = next(e for e in result.events if e.reference == "MANAGE FEE")
        assert fee_event.sub_account == "Cash"

    def test_income_action_sub_account_is_cash(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fee_interest.csv", ACCOUNT)
        interest_event = next(e for e in result.events if e.reference == "INTEREST")
        assert interest_event.sub_account == "Cash"

    def test_buy_action_sub_account_from_description(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        buy_event = next(e for e in result.events if e.reference == "B12345")
        assert buy_event.sub_account == "Vanguard US Equity Index Fund Acc"

    def test_fee_sale_suffix_stripped_from_sub_account(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_fee_sale.csv", ACCOUNT)
        assert len(result.errors) == 0
        event = result.events[0]
        assert event.sub_account == "BlackRock Consensus 85 Class I - Accumulation (GBP)"


class TestValueAndQuantity:
    def test_value_parsed_as_decimal(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        buy_event = next(e for e in result.events if e.reference == "B12345")
        assert buy_event.value == Decimal("-2000.00")

    def test_quantity_parsed_when_present(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        buy_event = next(e for e in result.events if e.reference == "B12345")
        assert buy_event.quantity == Decimal("10.00")

    def test_quantity_none_when_empty(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib.csv", ACCOUNT)
        deposit_event = next(e for e in result.events if e.reference == "Deposit")
        assert deposit_event.quantity is None


class TestErrorHandling:
    def test_bad_value_row_produces_error_with_line_number(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "invalid_bad_value.csv", ACCOUNT)
        assert len(result.errors) == 1
        assert result.errors[0].line_number is not None
        assert result.errors[0].line_number > 0

    def test_valid_row_after_bad_row_still_in_results(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "invalid_bad_value.csv", ACCOUNT)
        assert len(result.events) == 1
        assert result.events[0].reference == "S67890"

    def test_parser_never_raises(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "invalid_no_header.csv", ACCOUNT)
        assert result is not None
