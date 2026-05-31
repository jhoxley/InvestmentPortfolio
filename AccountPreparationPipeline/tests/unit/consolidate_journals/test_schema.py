from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.modes.consolidate_journals.schema import (
    ActionType,
    ConsolidationSummary,
    JournalEvent,
    ParseError,
    ParseResult,
)


class TestActionType:
    def test_buy_string_value(self) -> None:
        assert ActionType.BUY == "buy"

    def test_sell_string_value(self) -> None:
        assert ActionType.SELL == "sell"

    def test_contrib_string_value(self) -> None:
        assert ActionType.CONTRIB == "contrib"

    def test_withdrawal_string_value(self) -> None:
        assert ActionType.WITHDRAWAL == "withdrawal"

    def test_all_values_are_strings(self) -> None:
        for member in ActionType:
            assert isinstance(member.value, str)

    def test_str_cast_returns_value(self) -> None:
        assert str(ActionType.BUY) == "buy"


class TestJournalEvent:
    def _make(self, **overrides: object) -> JournalEvent:
        defaults: dict[str, object] = {
            "date": datetime.date(2024, 1, 15),
            "account": "My ISA",
            "sub_account": "Vanguard US Equity",
            "action": ActionType.BUY,
            "reference": "B12345",
            "value": Decimal("2000.00"),
            "quantity": Decimal("10.00"),
        }
        defaults.update(overrides)
        return JournalEvent(**defaults)  # type: ignore[arg-type]

    def test_is_frozen(self) -> None:
        event = self._make()
        with pytest.raises((AttributeError, TypeError)):
            event.account = "other"  # type: ignore[misc]

    def test_quantity_can_be_none(self) -> None:
        event = self._make(quantity=None)
        assert event.quantity is None

    def test_all_fields_stored(self) -> None:
        event = self._make()
        assert event.date == datetime.date(2024, 1, 15)
        assert event.account == "My ISA"
        assert event.sub_account == "Vanguard US Equity"
        assert event.action == ActionType.BUY
        assert event.reference == "B12345"
        assert event.value == Decimal("2000.00")
        assert event.quantity == Decimal("10.00")


class TestParseError:
    def test_is_frozen(self) -> None:
        err = ParseError(
            file_path=Path("test.csv"),
            line_number=5,
            message="bad value",
        )
        with pytest.raises((AttributeError, TypeError)):
            err.message = "other"  # type: ignore[misc]

    def test_line_number_can_be_none(self) -> None:
        err = ParseError(file_path=Path("test.csv"), line_number=None, message="no header")
        assert err.line_number is None

    def test_fields_stored(self) -> None:
        p = Path("fragment.csv")
        err = ParseError(file_path=p, line_number=7, message="test error")
        assert err.file_path == p
        assert err.line_number == 7
        assert err.message == "test error"


class TestParseResult:
    def test_events_and_errors_always_present(self) -> None:
        result = ParseResult(events=[], errors=[])
        assert result.events == []
        assert result.errors == []

    def test_is_frozen(self) -> None:
        result = ParseResult(events=[], errors=[])
        with pytest.raises((AttributeError, TypeError)):
            result.events = []  # type: ignore[misc]

    def test_stores_events_and_errors(self) -> None:
        event = JournalEvent(
            date=datetime.date(2024, 1, 1),
            account="acc",
            sub_account="sub",
            action=ActionType.SELL,
            reference="S1",
            value=Decimal("100"),
            quantity=None,
        )
        err = ParseError(file_path=Path("f.csv"), line_number=1, message="oops")
        result = ParseResult(events=[event], errors=[err])
        assert len(result.events) == 1
        assert len(result.errors) == 1


class TestConsolidationSummary:
    def test_is_frozen(self) -> None:
        s = ConsolidationSummary(
            files_processed=1, events_inserted=0, events_merged=0, events_removed=0, errors=[]
        )
        with pytest.raises((AttributeError, TypeError)):
            s.files_processed = 5  # type: ignore[misc]

    def test_all_counts_accessible(self) -> None:
        s = ConsolidationSummary(
            files_processed=3,
            events_inserted=10,
            events_merged=2,
            events_removed=0,
            errors=[],
        )
        assert s.files_processed == 3
        assert s.events_inserted == 10
        assert s.events_merged == 2
        assert s.events_removed == 0
        assert s.errors == []
