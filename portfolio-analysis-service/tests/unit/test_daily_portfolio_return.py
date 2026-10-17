"""Unit tests for compute_daily_portfolio_return's aggregation and gap-filling behaviour."""

from datetime import date

import pandas as pd
import pytest

from app.services.daily_portfolio_return import compute_daily_portfolio_return


def _ladder_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal long-format ladder DataFrame from explicit rows.

    Args:
        rows: List of dicts with keys date, sub_account, weighted_position_return.

    Returns:
        DataFrame with columns [date, sub_account, weighted_position_return].
    """
    return pd.DataFrame(rows)


class TestSumsWeightedPositionReturnAcrossPositionsPerDate:
    """The daily return for a date is the sum of every position's weighted return that day."""

    def test_sums_weighted_position_return_across_positions_per_date(self) -> None:
        """Two sub-accounts on the same date sum to the spec.md worked example (0.0065)."""
        ladder_df = _ladder_df(
            [
                {
                    "date": date(2024, 3, 4),
                    "sub_account": "Equities A",
                    "weighted_position_return": 0.011,
                },
                {
                    "date": date(2024, 3, 4),
                    "sub_account": "Equities B",
                    "weighted_position_return": -0.0045,
                },
            ]
        )

        result = compute_daily_portfolio_return(
            ladder_df, from_date=date(2024, 3, 4), through_date=date(2024, 3, 4)
        )

        row = result[result["date"] == date(2024, 3, 4)].iloc[0]
        assert row["daily_return"] == pytest.approx(0.0065)


class TestZeroFillsDatesWithNoLadderRowsNotForwardFill:
    """A gap date with no ladder rows sums to 0.0, never a repeat of the prior day's value."""

    def test_zero_fills_dates_with_no_ladder_rows_not_forward_fill(self) -> None:
        """A gap business day between two recorded dates is exactly 0.0, not forward-filled."""
        ladder_df = _ladder_df(
            [
                {
                    "date": date(2024, 3, 4),
                    "sub_account": "Equities A",
                    "weighted_position_return": 0.02,
                },
                {
                    "date": date(2024, 3, 6),
                    "sub_account": "Equities A",
                    "weighted_position_return": 0.01,
                },
            ]
        )

        result = compute_daily_portfolio_return(
            ladder_df, from_date=date(2024, 3, 4), through_date=date(2024, 3, 6)
        )

        gap_row = result[result["date"] == date(2024, 3, 5)].iloc[0]
        assert gap_row["daily_return"] == 0.0
        assert gap_row["daily_return"] != 0.02


class TestNeverPadsBeforeLaddersEarliestDate:
    """The returned series starts exactly at from_date, never earlier."""

    def test_never_pads_before_ladders_earliest_date(self) -> None:
        """The first row's date equals the given from_date exactly."""
        ladder_df = _ladder_df(
            [
                {
                    "date": date(2024, 3, 6),
                    "sub_account": "Cash",
                    "weighted_position_return": 0.0,
                }
            ]
        )

        result = compute_daily_portfolio_return(
            ladder_df, from_date=date(2024, 3, 4), through_date=date(2024, 3, 6)
        )

        assert result["date"].min() == date(2024, 3, 4)


class TestExtendsThroughDateBeyondLaddersLastRecordedRowAsZero:
    """Trailing business days beyond the ladder's last recorded row are present and zero."""

    def test_extends_through_date_beyond_ladders_last_recorded_row_as_zero(self) -> None:
        """A through_date later than the ladder's last row yields zero-return trailing days."""
        ladder_df = _ladder_df(
            [
                {
                    "date": date(2024, 3, 4),
                    "sub_account": "Cash",
                    "weighted_position_return": 0.05,
                }
            ]
        )

        result = compute_daily_portfolio_return(
            ladder_df, from_date=date(2024, 3, 4), through_date=date(2024, 3, 6)
        )

        trailing_row = result[result["date"] == date(2024, 3, 6)].iloc[0]
        assert trailing_row["daily_return"] == 0.0
        assert result["date"].max() == date(2024, 3, 6)


class TestSinglePositionLadderMatchesThatPositionsWeightedReturn:
    """With a single sub-account, the daily return trivially equals its own weighted return."""

    def test_single_position_ladder_matches_that_positions_weighted_return(self) -> None:
        """One sub-account's daily_return equals its own weighted_position_return each date."""
        ladder_df = _ladder_df(
            [
                {
                    "date": date(2024, 3, 4),
                    "sub_account": "Equities A",
                    "weighted_position_return": 0.02,
                },
                {
                    "date": date(2024, 3, 5),
                    "sub_account": "Equities A",
                    "weighted_position_return": -0.01,
                },
            ]
        )

        result = compute_daily_portfolio_return(
            ladder_df, from_date=date(2024, 3, 4), through_date=date(2024, 3, 5)
        )

        by_date = dict(zip(result["date"], result["daily_return"], strict=True))
        assert by_date[date(2024, 3, 4)] == pytest.approx(0.02)
        assert by_date[date(2024, 3, 5)] == pytest.approx(-0.01)
