"""Unit tests for compute_performance_measures's ITD/ITD (Ann.)/1Y/3Y/5Y formulas."""

from datetime import date

import pandas as pd
import pytest

from app.services.performance_metrics import compute_performance_measures


def _daily_returns_df(returns: list[float]) -> pd.DataFrame:
    """Build a daily_return DataFrame of consecutive business days from a list of returns.

    Args:
        returns: Daily return values, oldest first.

    Returns:
        DataFrame with columns [date, daily_return].
    """
    dates = pd.bdate_range(start=date(2020, 1, 1), periods=len(returns))
    return pd.DataFrame({"date": [d.date() for d in dates], "daily_return": returns})


class TestItdIsExpandingCumulativeProductMinusOne:
    """ITD at each date is the cumulative product of (1 + daily_return) since inception, minus 1."""

    def test_itd_is_expanding_cumulative_product_minus_one(self) -> None:
        """ITD matches an independently hand-computed expanding cumulative product."""
        returns = [0.0, 0.02, -0.01, 0.03, 0.01]
        df = _daily_returns_df(returns)

        result = compute_performance_measures(df)

        expected = []
        running = 1.0
        for r in returns:
            running *= 1 + r
            expected.append(running - 1)
        for actual, exp in zip(result["ITD"], expected, strict=True):
            assert actual == pytest.approx(exp)


class TestItdIsZeroOnFirstRecordedDate:
    """The first row's daily_return is 0.0, so ITD and ITD (Ann.) are both exactly 0.0."""

    def test_itd_is_zero_on_first_recorded_date(self) -> None:
        """First row is 0.0 for both ITD and ITD (Ann.)."""
        df = _daily_returns_df([0.0, 0.02, -0.01])

        result = compute_performance_measures(df)

        first_row = result.iloc[0]
        assert first_row["ITD"] == 0.0
        assert first_row["ITD (Ann.)"] == 0.0


class TestItdAnnualizedUses260DayYearAndElapsedRowCount:
    """ITD (Ann.) annualizes ITD using a 260-trading-day year and 1-indexed elapsed rows."""

    def test_itd_annualized_uses_260_day_year_and_elapsed_row_count(self) -> None:
        """ITD (Ann.) at row i equals (1 + ITD[i]) ** (260 / (i + 1)) - 1."""
        returns = [0.0, 0.02, -0.01, 0.03, 0.01]
        df = _daily_returns_df(returns)

        result = compute_performance_measures(df)

        for i, row in result.iterrows():
            expected = (1 + row["ITD"]) ** (260 / (i + 1)) - 1
            assert row["ITD (Ann.)"] == pytest.approx(expected)


class TestOneYIsRolling260DayCumulativeProductNotAnnualized:
    """1Y is the trailing 260-business-day cumulative product, minus 1, unscaled."""

    def test_1y_is_rolling_260_day_cumulative_product_not_annualized(self) -> None:
        """The last row's 1Y equals the cumulative product of the trailing 260 returns."""
        returns = [0.001 * (i % 7 - 3) for i in range(300)]
        df = _daily_returns_df(returns)

        result = compute_performance_measures(df)

        trailing = returns[-260:]
        running = 1.0
        for r in trailing:
            running *= 1 + r
        expected = running - 1
        assert result.iloc[-1]["1Y"] == pytest.approx(expected)


class TestThreeYIsRolling780DayCumulativeProductAnnualizedByOneThirdPower:
    """3Y is the trailing 780-day cumulative product, annualized by the 1/3 power."""

    def test_3y_is_rolling_780_day_cumulative_product_annualized_by_one_third_power(self) -> None:
        """The last row's 3Y equals the trailing-780-day cumprod raised to 1/3, minus 1."""
        returns = [0.0005 * (i % 11 - 5) for i in range(800)]
        df = _daily_returns_df(returns)

        result = compute_performance_measures(df)

        trailing = returns[-780:]
        running = 1.0
        for r in trailing:
            running *= 1 + r
        expected = running ** (1 / 3) - 1
        assert result.iloc[-1]["3Y"] == pytest.approx(expected)


class TestFiveYIsRolling1300DayCumulativeProductAnnualizedByOneFifthPower:
    """5Y is the trailing 1300-day cumulative product, annualized by the 1/5 power."""

    def test_5y_is_rolling_1300_day_cumulative_product_annualized_by_one_fifth_power(self) -> None:
        """The last row's 5Y equals the trailing-1300-day cumprod raised to 1/5, minus 1."""
        returns = [0.0003 * (i % 13 - 6) for i in range(1350)]
        df = _daily_returns_df(returns)

        result = compute_performance_measures(df)

        trailing = returns[-1300:]
        running = 1.0
        for r in trailing:
            running *= 1 + r
        expected = running ** (1 / 5) - 1
        assert result.iloc[-1]["5Y"] == pytest.approx(expected)


class TestTrailingMeasuresAreNanBeforeEnoughHistoryExists:
    """Pandas rolling's default min_periods is what produces the "not yet computable" signal."""

    def test_trailing_measures_are_nan_before_enough_history_exists(self) -> None:
        """1Y is NaN for every row of a series shorter than 260 rows, real once it reaches 260."""
        short_returns = [0.001] * 259
        short_df = _daily_returns_df(short_returns)
        short_result = compute_performance_measures(short_df)
        assert short_result["1Y"].isna().all()

        exact_returns = [0.001] * 260
        exact_df = _daily_returns_df(exact_returns)
        exact_result = compute_performance_measures(exact_df)
        assert not pd.isna(exact_result.iloc[-1]["1Y"])

    def test_3y_and_5y_are_nan_before_their_windows_are_satisfied(self) -> None:
        """3Y/5Y are NaN until 780/1300 rows of history exist, respectively."""
        returns_779 = [0.001] * 779
        result_779 = compute_performance_measures(_daily_returns_df(returns_779))
        assert result_779["3Y"].isna().all()

        returns_780 = [0.001] * 780
        result_780 = compute_performance_measures(_daily_returns_df(returns_780))
        assert not pd.isna(result_780.iloc[-1]["3Y"])

        returns_1299 = [0.001] * 1299
        result_1299 = compute_performance_measures(_daily_returns_df(returns_1299))
        assert result_1299["5Y"].isna().all()

        returns_1300 = [0.001] * 1300
        result_1300 = compute_performance_measures(_daily_returns_df(returns_1300))
        assert not pd.isna(result_1300.iloc[-1]["5Y"])


class TestNarrowWindowSliceMatchesWideWindowComputationForSameDate:
    """Look-back must use the full history, not just what's in the requested window."""

    def test_narrow_window_slice_matches_wide_window_computation_for_same_date(self) -> None:
        """A date needing full history is NaN when computed from a too-short input series."""
        returns = [0.001 * (i % 5 - 2) for i in range(800)]
        full_df = _daily_returns_df(returns)
        full_result = compute_performance_measures(full_df)

        narrow_start_index = 400
        narrow_df = full_df.iloc[narrow_start_index:].reset_index(drop=True)
        narrow_result = compute_performance_measures(narrow_df)

        target_date = full_df.iloc[799]["date"]
        wide_value = full_result[full_result["date"] == target_date].iloc[0]["3Y"]
        narrow_value = narrow_result[narrow_result["date"] == target_date].iloc[0]["3Y"]

        assert not pd.isna(wide_value)
        assert pd.isna(narrow_value)
        assert wide_value != narrow_value
