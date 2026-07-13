"""Date defaulting and business-day adjustment for the time series endpoint."""

from datetime import date

import pandas as pd

from app.exceptions import FutureEndDateError, InvalidDateRangeError


class TimeseriesDateResolver:
    """Resolves the effective [start, end] range for a time series request.

    `today` is always passed in explicitly (never read from the system clock inside
    this class), so every rule — including the rare "today is itself a weekend"
    edge case — is deterministically testable.
    """

    def resolve(
        self,
        raw_start: date | None,
        raw_end: date | None,
        today: date,
        required_source_earliest_dates: list[date],
    ) -> tuple[date, date]:
        """Resolve the raw request inputs into a concrete, business-day-aligned range.

        Args:
            raw_start: The caller-supplied start date, or None to default (FR-006).
            raw_end: The caller-supplied end date, or None to default (FR-007).
            today: The current date.
            required_source_earliest_dates: Each required source's own earliest
                recorded date, used to compute the default start.

        Returns:
            (resolved_start, resolved_end), both business days, start <= end.

        Raises:
            FutureEndDateError: If raw_end is supplied and later than today (FR-010).
            InvalidDateRangeError: If the resolved start is after the resolved end,
                whether from explicit inputs or business-day adjustment (FR-009).
        """
        if raw_end is not None and raw_end > today:
            raise FutureEndDateError(end=raw_end, today=today)

        end = raw_end if raw_end is not None else self._business_day_before(today)
        start = raw_start if raw_start is not None else max(required_source_earliest_dates)

        resolved_start = self._adjust_forward_capped_at_today(start, today)
        resolved_end = self._adjust_forward_capped_at_today(end, today)

        if resolved_start > resolved_end:
            raise InvalidDateRangeError(start=resolved_start, end=resolved_end)

        return resolved_start, resolved_end

    def _adjust_forward_capped_at_today(self, d: date, today: date) -> date:
        """Adjust a date forward to the next business day, capped backward at today.

        Args:
            d: The date to adjust.
            today: The current date.

        Returns:
            The next business day on/after d, or the most recent business day on/before
            today if that adjustment would otherwise land after today (FR-008).
        """
        adjusted: date = pd.bdate_range(start=d, periods=1)[0].date()
        if adjusted > today:
            return self._most_recent_business_day_on_or_before(today)
        return adjusted

    def _business_day_before(self, today: date) -> date:
        """Return the business day strictly before today (T-1).

        Args:
            today: The current date.

        Returns:
            The business day immediately preceding today.
        """
        result: date = pd.bdate_range(end=today, periods=2)[0].date()
        return result

    def _most_recent_business_day_on_or_before(self, today: date) -> date:
        """Return the most recent business day on or before today.

        Args:
            today: The current date.

        Returns:
            today itself if it is a business day, otherwise the preceding business day.
        """
        result: date = pd.bdate_range(end=today, periods=1)[0].date()
        return result
