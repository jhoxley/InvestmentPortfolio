"""Unit tests for CapitalLedgerExpander business-day expansion logic."""

from datetime import date

import pandas as pd
import pytest

from app.services.capital_ledger_expander import CapitalLedgerExpander


@pytest.fixture()
def expander() -> CapitalLedgerExpander:
    """Return a CapitalLedgerExpander instance.

    Returns:
        CapitalLedgerExpander ready for use in tests.
    """
    return CapitalLedgerExpander()


class TestForwardFillAcrossGapDays:
    """Tests that values are forward-filled across days with no recorded observation."""

    def test_forward_fill_across_gap_days(self, expander: CapitalLedgerExpander) -> None:
        """Values from a recorded date should propagate to subsequent days with no observation."""
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 2), date(2024, 1, 10)],
                "capital": [1000.0, 1200.0],
                "income": [0.0, 5.0],
                "book_value": [0.0, 900.0],
            }
        )
        result = expander.expand(df)
        gap_row = result[result["date"] == date(2024, 1, 5)]
        assert len(gap_row) == 1
        assert gap_row.iloc[0]["capital"] == 1000.0


class TestBusinessDaysOnlyInOutput:
    """Tests that the output contains only business days (Mon-Fri)."""

    def test_business_days_only_in_output(self, expander: CapitalLedgerExpander) -> None:
        """No Saturday or Sunday should appear in the expanded output."""
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 2), date(2024, 1, 10)],
                "capital": [1000.0, 1200.0],
                "income": [0.0, 5.0],
                "book_value": [0.0, 900.0],
            }
        )
        result = expander.expand(df)
        for d in result["date"]:
            assert d.weekday() < 5, f"Weekend date found in output: {d}"


class TestRangeBoundedToMinAndMaxRecordedDate:
    """Tests that the expansion range is [min(date), max(date)], not extended to today."""

    def test_range_bounded_to_min_and_max_recorded_date(
        self, expander: CapitalLedgerExpander
    ) -> None:
        """No rows should exist before the earliest or after the latest recorded date."""
        earliest = date(2024, 1, 2)
        latest = date(2024, 1, 10)
        df = pd.DataFrame(
            {
                "date": [earliest, latest],
                "capital": [1000.0, 1200.0],
                "income": [0.0, 5.0],
                "book_value": [0.0, 900.0],
            }
        )
        result = expander.expand(df)
        assert result["date"].min() == earliest
        assert result["date"].max() == latest


class TestSingleRecordedDateOnABusinessDay:
    """Tests that a single-row file on a business day produces a single-row result."""

    def test_single_recorded_date_on_a_business_day_produces_one_row(
        self, expander: CapitalLedgerExpander
    ) -> None:
        """A single recorded weekday date yields exactly one row."""
        d = date(2024, 1, 2)
        df = pd.DataFrame({"date": [d], "capital": [1000.0], "income": [0.0], "book_value": [0.0]})
        result = expander.expand(df)
        assert len(result) == 1
        assert result.iloc[0]["date"] == d


class TestNoGroupingOrClosureRuleApplied:
    """Tests that no sub-account grouping or closure rule is applied."""

    def test_no_grouping_or_closure_rule_applied(self, expander: CapitalLedgerExpander) -> None:
        """Output has no sub_account column and zero-valued rows are never dropped."""
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 2), date(2024, 1, 3)],
                "capital": [1000.0, 0.0],
                "income": [0.0, 0.0],
                "book_value": [0.0, 0.0],
            }
        )
        result = expander.expand(df)
        assert "sub_account" not in result.columns
        zero_row = result[result["date"] == date(2024, 1, 3)]
        assert len(zero_row) == 1
        assert zero_row.iloc[0]["capital"] == 0.0
