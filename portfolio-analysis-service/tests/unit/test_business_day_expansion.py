"""Unit tests for the shared expand_business_days() reindex/ffill helper."""

from datetime import date, timedelta

import pandas as pd

from app.services.business_day_expansion import expand_business_days


def _next_saturday(ref: date) -> date:
    """Return the next Saturday on or after ref.

    Args:
        ref: Reference date.

    Returns:
        A Saturday date.
    """
    days_ahead = (5 - ref.weekday()) % 7
    return ref + timedelta(days=days_ahead)


class TestForwardFillsAcrossGapDays:
    """Values from a recorded date should propagate to subsequent days with no observation."""

    def test_forward_fills_across_gap_days(self) -> None:
        """A gap between two recorded dates is forward-filled from the earlier value."""
        d1 = date(2024, 1, 2)  # Tuesday
        d2 = date(2024, 1, 10)  # Wednesday
        df = pd.DataFrame({"date": [d1, d2], "value": [100.0, 110.0]})
        result = expand_business_days(df, ["value"], d1, d2)
        gap_day = date(2024, 1, 5)  # Friday, no recorded observation
        row = result[result["date"] == gap_day]
        assert len(row) == 1
        assert row.iloc[0]["value"] == 100.0


class TestFiltersResultToBusinessDaysOnly:
    """No Saturday or Sunday should appear in the output."""

    def test_filters_result_to_business_days_only(self) -> None:
        """Weekend dates are excluded from the expanded output."""
        d1 = date(2024, 1, 2)
        d2 = date(2024, 1, 10)
        df = pd.DataFrame({"date": [d1], "value": [100.0]})
        result = expand_business_days(df, ["value"], d1, d2)
        for d in result["date"]:
            assert d.weekday() < 5, f"Weekend date found in output: {d}"


class TestStartEqualsEndOnABusinessDay:
    """A single-day range on a business day produces exactly one row."""

    def test_start_equals_end_on_a_business_day_produces_one_row(self) -> None:
        """Start == end on a weekday yields a single-row result."""
        d1 = date(2024, 1, 2)  # Tuesday
        df = pd.DataFrame({"date": [d1], "value": [100.0]})
        result = expand_business_days(df, ["value"], d1, d1)
        assert len(result) == 1
        assert result.iloc[0]["date"] == d1
        assert result.iloc[0]["value"] == 100.0


class TestStartEqualsEndOnAWeekend:
    """A single-day range on a weekend produces an empty result."""

    def test_start_equals_end_on_a_weekend_produces_empty_result(self) -> None:
        """Start == end on a Saturday yields zero rows."""
        saturday = _next_saturday(date(2024, 1, 2))
        df = pd.DataFrame({"date": [saturday], "value": [100.0]})
        result = expand_business_days(df, ["value"], saturday, saturday)
        assert len(result) == 0


class TestReindexesOverFullCalendarRangeBeforeFiltering:
    """A weekend-only recorded observation still seeds forward-fill for the next business day."""

    def test_reindexes_over_full_calendar_range_before_filtering(self) -> None:
        """A Saturday-recorded value is still carried forward to the following Monday."""
        saturday = _next_saturday(date(2024, 1, 2))
        monday = saturday + timedelta(days=2)
        df = pd.DataFrame({"date": [saturday], "value": [100.0]})
        result = expand_business_days(df, ["value"], saturday, monday)
        monday_row = result[result["date"] == monday]
        assert len(monday_row) == 1
        assert monday_row.iloc[0]["value"] == 100.0
