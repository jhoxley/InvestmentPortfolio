"""Calendar-period aggregation of an expanded business-day time series frame."""

from datetime import date

import pandas as pd

from app.models.periodicity import PERIOD_ALIAS, Periodicity


def aggregate_last_observation(
    df: pd.DataFrame, periodicity: Periodicity, resolved_start: date
) -> pd.DataFrame:
    """Reduce a per-business-day frame to one row per calendar-aligned window.

    Each window keeps the **whole last row** recorded within it, so every attribute on an
    aggregated row is drawn from the same source date. The row is then re-dated to the
    window's start business day, clamped up to `resolved_start` for the first window so no
    reported date can precede the response's stated start of range. Windows containing no
    row simply never form a group, so an empty window is omitted rather than returned with
    nulls.

    The reported date is a function of the calendar period and `resolved_start` alone —
    never of the frame's contents — so two positions aggregated separately align on
    identical window dates.

    Args:
        df: A frame with a `date` column of `datetime.date`, one row per business day,
            already forward-filled and clipped to the resolved date range (i.e. the output
            of `expand_business_days`, plus any derived columns such as `pnl`).
        periodicity: The requested aggregation interval. `Periodicity.DAY` is the identity.
        resolved_start: The resolved start of the requested range, used to clamp the first
            window's reported date.

    Returns:
        A frame with the same columns in the same order, one row per non-empty window,
        sorted ascending by `date`, with a reset index. The caller's frame is not mutated.
    """
    alias = PERIOD_ALIAS.get(periodicity)
    if alias is None or df.empty:
        return df

    working = df.sort_values("date").reset_index(drop=True)
    periods = pd.to_datetime(working["date"]).dt.to_period(alias).rename("_period")

    last_rows = working.groupby(periods, sort=True).tail(1)
    window_dates = [
        _window_start_date(period, resolved_start) for period in periods.loc[last_rows.index]
    ]

    result = last_rows.copy()
    result["date"] = window_dates
    return result[list(df.columns)].sort_values("date").reset_index(drop=True)


def _window_start_date(period: pd.Period, resolved_start: date) -> date:
    """Return the business day a window is reported on.

    Args:
        period: The calendar period the window represents.
        resolved_start: The resolved start of the requested range.

    Returns:
        The first business day on or after the period's calendar start, having first
        clamped that start up to `resolved_start`.
    """
    anchor = max(period.start_time.date(), resolved_start)
    adjusted: date = pd.bdate_range(start=anchor, periods=1)[0].date()
    return adjusted
