from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

from src.modes.consolidate_journals.parsers.hl import HLFragmentParser
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

    def test_deposit_reference_maps_to_contrib(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib.csv", ACCOUNT)
        contrib_events = [e for e in result.events if e.action == ActionType.CONTRIB]
        assert len(contrib_events) == 2

    def test_bacs_reference_maps_to_contrib(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib.csv", ACCOUNT)
        bacs_event = next(e for e in result.events if e.reference == "BACS")
        assert bacs_event.action == ActionType.CONTRIB


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

    def test_description_without_suffix_unchanged(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_contrib.csv", ACCOUNT)
        deposit_event = next(e for e in result.events if e.reference == "Deposit")
        assert deposit_event.sub_account == "Bank transfer"


class TestValueAndQuantity:
    def test_value_parsed_as_decimal(self) -> None:
        parser = HLFragmentParser()
        result = parser.parse(DATA_DIR / "valid_hl_simple.csv", ACCOUNT)
        buy_event = next(e for e in result.events if e.reference == "B12345")
        assert buy_event.value == Decimal("2000.00")

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
