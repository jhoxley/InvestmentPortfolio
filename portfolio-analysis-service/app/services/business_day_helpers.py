"""Shared, stateless business-day reference-point helpers.

Factored out of `TimeseriesDateResolver` (014) so the staleness/rebuild path can reuse
the exact same "prior business day" semantics without duplicating the logic.
"""

from datetime import date

import pandas as pd


def business_day_before(today: date) -> date:
    """Return the business day strictly before today (T-1).

    Args:
        today: The current date.

    Returns:
        The business day immediately preceding today.
    """
    result: date = pd.bdate_range(end=today, periods=2)[0].date()
    return result


def most_recent_business_day_on_or_before(today: date) -> date:
    """Return the most recent business day on or before today.

    Args:
        today: The current date.

    Returns:
        today itself if it is a business day, otherwise the preceding business day.
    """
    result: date = pd.bdate_range(end=today, periods=1)[0].date()
    return result
