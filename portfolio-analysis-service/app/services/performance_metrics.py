"""Computes ITD, ITD (Ann.), 1Y, 3Y, and 5Y from an account's daily portfolio return series."""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def compute_performance_measures(daily_returns_df: pd.DataFrame) -> pd.DataFrame:
    """Compute all five performance measures over the full given daily-return history.

    Every measure is computed over the *entire* input series before any caller slices
    the result down to a requested display window — this is what makes trailing and
    inception-to-date look-back correct regardless of the requested window size.
    Wherever pandas' `rolling`/`expanding` default `min_periods` behaviour cannot yet
    produce a value (not enough preceding history), the corresponding cell is left as
    `NaN` rather than filled or dropped here; the caller is responsible for omitting
    not-yet-computable measures from its response.

    Args:
        daily_returns_df: DataFrame with columns [date, daily_return], sorted by date,
            with no gaps (one row per business day).

    Returns:
        DataFrame with columns [date, ITD, "ITD (Ann.)", "1Y", "3Y", "5Y"].
    """
    sorted_df = daily_returns_df.sort_values("date").reset_index(drop=True)
    growth = 1 + sorted_df["daily_return"]

    itd = growth.expanding().apply(lambda w: w.prod(), raw=True) - 1
    elapsed = pd.Series(range(1, len(growth) + 1))
    itd_ann = (1 + itd) ** (260 / elapsed) - 1

    one_y = growth.rolling(window=260).apply(lambda w: w.prod(), raw=True) - 1

    three_y_cumprod = growth.rolling(window=780).apply(lambda w: w.prod(), raw=True)
    three_y = three_y_cumprod ** (1 / 3) - 1

    five_y_cumprod = growth.rolling(window=1300).apply(lambda w: w.prod(), raw=True)
    five_y = five_y_cumprod ** (1 / 5) - 1

    result = pd.DataFrame(
        {
            "date": sorted_df["date"],
            "ITD": itd,
            "ITD (Ann.)": itd_ann,
            "1Y": one_y,
            "3Y": three_y,
            "5Y": five_y,
        }
    )

    logger.info("performance_measures_complete", row_count=len(result))
    return result
