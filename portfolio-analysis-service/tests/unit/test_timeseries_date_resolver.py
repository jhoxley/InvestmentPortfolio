"""Unit tests for TimeseriesDateResolver date defaulting and business-day adjustment."""

from datetime import date

import pytest

from app.exceptions import FutureEndDateError, InvalidDateRangeError
from app.services.timeseries_date_resolver import TimeseriesDateResolver


@pytest.fixture()
def resolver() -> TimeseriesDateResolver:
    """Return a TimeseriesDateResolver instance.

    Returns:
        TimeseriesDateResolver ready for use in tests.
    """
    return TimeseriesDateResolver()


class TestBusinessDayInputUnchanged:
    """A start/end that already falls on a business day is left unchanged."""

    def test_business_day_input_unchanged(self, resolver: TimeseriesDateResolver) -> None:
        """Explicit weekday start/end pass through untouched."""
        today = date(2024, 6, 14)  # Friday
        start = date(2024, 1, 2)  # Tuesday
        end = date(2024, 1, 10)  # Wednesday
        resolved_start, resolved_end = resolver.resolve(
            raw_start=start,
            raw_end=end,
            today=today,
            required_source_earliest_dates=[date(2023, 1, 1)],
        )
        assert resolved_start == start
        assert resolved_end == end


class TestWeekendStartAdjustsForwardToMonday:
    """A weekend start date is adjusted forward to the following Monday."""

    def test_weekend_start_adjusts_forward_to_monday(
        self, resolver: TimeseriesDateResolver
    ) -> None:
        """A Saturday start becomes the following Monday."""
        today = date(2024, 6, 14)
        saturday = date(2024, 1, 6)
        monday = date(2024, 1, 8)
        resolved_start, _ = resolver.resolve(
            raw_start=saturday,
            raw_end=date(2024, 1, 10),
            today=today,
            required_source_earliest_dates=[date(2023, 1, 1)],
        )
        assert resolved_start == monday


class TestWeekendEndAdjustsForwardCappedAtTodayWhenTodayIsAWeekend:
    """A weekend end date that would roll past today is capped back to today's business day."""

    def test_weekend_end_adjusts_forward_capped_at_today_when_today_is_a_weekend(
        self, resolver: TimeseriesDateResolver
    ) -> None:
        """When today is a Saturday, an end of that same Saturday is capped, not rolled to Monday."""
        saturday_today = date(2024, 1, 6)
        friday_before = date(2024, 1, 5)
        _, resolved_end = resolver.resolve(
            raw_start=date(2024, 1, 2),
            raw_end=saturday_today,
            today=saturday_today,
            required_source_earliest_dates=[date(2023, 1, 1)],
        )
        assert resolved_end == friday_before
        assert resolved_end <= saturday_today


class TestDefaultEndIsTheBusinessDayBeforeToday:
    """When end is omitted, it defaults to the business day before today (T-1)."""

    def test_default_end_is_the_business_day_before_today(
        self, resolver: TimeseriesDateResolver
    ) -> None:
        """A Friday today defaults end to Thursday."""
        friday_today = date(2024, 1, 12)
        thursday = date(2024, 1, 11)
        _, resolved_end = resolver.resolve(
            raw_start=date(2024, 1, 2),
            raw_end=None,
            today=friday_today,
            required_source_earliest_dates=[date(2023, 1, 1)],
        )
        assert resolved_end == thursday


class TestDefaultStartIsTheLaterOfMultipleRequiredSourcesEarliestDates:
    """When start is omitted, it defaults to the later of the required sources' earliest dates."""

    def test_default_start_is_the_later_of_multiple_required_sources_earliest_dates(
        self, resolver: TimeseriesDateResolver
    ) -> None:
        """The later (max) of two distinct source earliest dates is used as the default start."""
        today = date(2024, 6, 14)
        earlier = date(2020, 1, 2)
        later = date(2021, 3, 1)
        resolved_start, _ = resolver.resolve(
            raw_start=None,
            raw_end=date(2024, 1, 10),
            today=today,
            required_source_earliest_dates=[earlier, later],
        )
        assert resolved_start == later


class TestResolvedStartAfterResolvedEndRaises:
    """A resolved start after the resolved end raises InvalidDateRangeError."""

    def test_resolved_start_after_resolved_end_raises_invalid_date_range_error(
        self, resolver: TimeseriesDateResolver
    ) -> None:
        """An explicit start after an explicit end is rejected."""
        today = date(2024, 6, 14)
        with pytest.raises(InvalidDateRangeError):
            resolver.resolve(
                raw_start=date(2024, 2, 1),
                raw_end=date(2024, 1, 1),
                today=today,
                required_source_earliest_dates=[date(2023, 1, 1)],
            )


class TestFutureEndDateRaises:
    """A supplied end date later than today raises FutureEndDateError before any adjustment."""

    def test_future_end_date_raises_future_end_date_error(
        self, resolver: TimeseriesDateResolver
    ) -> None:
        """An end date after today is rejected outright."""
        today = date(2024, 6, 14)
        with pytest.raises(FutureEndDateError):
            resolver.resolve(
                raw_start=date(2024, 1, 2),
                raw_end=date(2024, 6, 15),
                today=today,
                required_source_earliest_dates=[date(2023, 1, 1)],
            )
