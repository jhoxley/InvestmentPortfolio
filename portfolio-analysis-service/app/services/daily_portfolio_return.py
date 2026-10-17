"""Aggregates a position ladder into one account-level daily portfolio return per business day."""

from datetime import date

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def compute_daily_portfolio_return(
    ladder_df: pd.DataFrame, from_date: date, through_date: date
) -> pd.DataFrame:
    """Sum weighted_position_return across positions per date, zero-filling gaps.

    A date with no ladder rows at all sums to 0.0 by definition of "sum over an empty
    set" — this is never forward-filled from the previous day's value, since a
    forward-filled return would incorrectly repeat a stale non-zero figure into every
    downstream cumulative-product calculation.

    Args:
        ladder_df: Long-format ladder with columns [date, sub_account,
            weighted_position_return], one row per (date, sub_account).
        from_date: First date of the returned series (inclusive) — never padded earlier
            than this, so downstream rolling/expanding windows correctly see "not enough
            history" rather than synthetic zero-return history.
        through_date: Last date of the returned series (inclusive); may extend beyond
            the ladder's own last recorded row.

    Returns:
        DataFrame with columns [date, daily_return], one row per business day between
        from_date and through_date inclusive, sorted by date.
    """
    aggregated = ladder_df.groupby("date", as_index=False)["weighted_position_return"].sum()
    aggregated = aggregated.rename(columns={"weighted_position_return": "daily_return"})

    business_days = pd.bdate_range(start=from_date, end=through_date)
    indexed = aggregated.set_index(pd.DatetimeIndex(pd.to_datetime(aggregated["date"])))
    reindexed = indexed[["daily_return"]].reindex(business_days).fillna(0.0)
    reindexed["date"] = reindexed.index.date

    result = reindexed[["date", "daily_return"]].reset_index(drop=True)

    logger.info("daily_portfolio_return_complete", row_count=len(result))
    return result
