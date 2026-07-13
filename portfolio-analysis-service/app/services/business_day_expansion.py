"""Shared business-day calendar reindex/forward-fill expansion helper."""

from datetime import date

import pandas as pd


def expand_business_days(
    df: pd.DataFrame, value_columns: list[str], start: date, end: date
) -> pd.DataFrame:
    """Reindex a sparse date-indexed DataFrame over business days, forward-filling gaps.

    Reindexes over the full calendar range first (so a weekend-only recorded value can
    still seed forward-fill for the next business day), then filters the result down to
    business days (Mon-Fri) only. The calendar range starts at the earlier of `start` and
    the source data's own earliest date, so a source row entirely before `start` (the
    source hasn't been refreshed in a while) can still seed forward-fill instead of
    yielding nulls.

    Args:
        df: Input DataFrame with a `date` column and the given value_columns.
        value_columns: Names of the columns to forward-fill.
        start: First date of the expansion range (inclusive).
        end: Last date of the expansion range (inclusive).

    Returns:
        DataFrame with columns `["date", *value_columns]`, one row per business day
        between start and end (inclusive), sorted by date.
    """
    business_days = pd.bdate_range(start=start, end=end)

    indexed = df.sort_values("date").set_index(pd.DatetimeIndex(pd.to_datetime(df["date"])))
    indexed = indexed[value_columns]

    calendar_start = min(start, indexed.index.min().date()) if not indexed.empty else start
    calendar_days = pd.date_range(start=calendar_start, end=end)

    reindexed = indexed.reindex(calendar_days).ffill()
    reindexed = reindexed.loc[reindexed.index.isin(business_days)]
    reindexed["date"] = reindexed.index.date

    result = reindexed[["date", *value_columns]].reset_index(drop=True)
    return result
