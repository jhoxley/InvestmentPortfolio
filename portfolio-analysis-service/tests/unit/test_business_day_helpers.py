"""Unit tests for the shared business-day reference-point helpers (014)."""

from datetime import date

from app.services.business_day_helpers import (
    business_day_before,
    most_recent_business_day_on_or_before,
)


class TestBusinessDayBefore:
    """business_day_before returns T-1 relative to today."""

    def test_business_day_before_a_tuesday_is_monday(self) -> None:
        """T-1 for a Tuesday is the preceding Monday."""
        tuesday = date(2026, 11, 10)
        assert business_day_before(tuesday) == date(2026, 11, 9)

    def test_business_day_before_a_monday_is_the_prior_friday(self) -> None:
        """T-1 for a Monday skips the weekend back to Friday."""
        monday = date(2026, 11, 9)
        assert business_day_before(monday) == date(2026, 11, 6)


class TestMostRecentBusinessDayOnOrBefore:
    """most_recent_business_day_on_or_before returns today itself when today is a business day."""

    def test_returns_today_when_today_is_a_business_day(self) -> None:
        """A Tuesday is returned unchanged."""
        tuesday = date(2026, 11, 10)
        assert most_recent_business_day_on_or_before(tuesday) == tuesday

    def test_returns_the_preceding_friday_when_today_is_a_saturday(self) -> None:
        """A Saturday rolls back to the preceding Friday."""
        saturday = date(2026, 11, 14)
        assert most_recent_business_day_on_or_before(saturday) == date(2026, 11, 13)


class TestResolverStillUsesTheSharedHelpers:
    """TimeseriesDateResolver's own behaviour is unchanged after the T012 refactor."""

    def test_resolver_default_end_still_matches_business_day_before(self) -> None:
        """The resolver's default end date still equals business_day_before(today)."""
        from app.services.timeseries_date_resolver import TimeseriesDateResolver

        today = date(2026, 11, 10)
        resolver = TimeseriesDateResolver()
        _start, end = resolver.resolve(
            raw_start=date(2026, 1, 2),
            raw_end=None,
            today=today,
            required_source_earliest_dates=[date(2026, 1, 2)],
        )
        assert end == business_day_before(today)
