"""Unit tests for basis-point rounding and histogram bucketing."""

import math
import random
import time

import pandas as pd
import pytest

from app.services.return_histogram import (
    build_histogram,
    compute_statistics,
    round_half_away_from_zero,
    to_basis_points,
)


class TestRoundHalfAwayFromZero:
    """Halves round away from zero — never banker's rounding."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0.5, 1),
            (-0.5, -1),
            (1.5, 2),
            (2.5, 3),
            (-2.5, -3),
            (0.4, 0),
            (-0.4, 0),
            (10.4, 10),
            (-25.0, -25),
        ],
    )
    def test_rounds_half_away_from_zero(self, value: float, expected: int) -> None:
        """Each value rounds to the documented integer."""
        result = round_half_away_from_zero(pd.Series([value]))

        assert result.iloc[0] == expected

    def test_result_is_integer_typed(self) -> None:
        """The rounded series has an integer dtype."""
        result = round_half_away_from_zero(pd.Series([1.4, -2.6]))

        assert pd.api.types.is_integer_dtype(result)


class TestToBasisPoints:
    """Daily returns convert to integer basis points."""

    @pytest.mark.parametrize(
        ("daily_return", "expected"),
        [
            (0.0010, 10),
            (0.00104, 10),
            (0.0011, 11),
            (-0.0025, -25),
            (0.0065, 65),
            (0.0, 0),
            (0.000004, 0),
            (-0.000004, 0),
        ],
    )
    def test_ordinary_values(self, daily_return: float, expected: int) -> None:
        """Ordinary returns round to the nearest whole basis point."""
        assert to_basis_points(pd.Series([daily_return])).iloc[0] == expected

    @pytest.mark.parametrize(
        ("daily_return", "expected"),
        [
            (0.00005, 1),
            (0.00015, 2),
            (0.00025, 3),
            (-0.00005, -1),
            (-0.00025, -3),
        ],
    )
    def test_decimal_halves_are_not_lost_to_floating_point_noise(
        self, daily_return: float, expected: int
    ) -> None:
        """Returns that are exact decimal halves in bps round away from zero."""
        assert to_basis_points(pd.Series([daily_return])).iloc[0] == expected


class TestBuildHistogram:
    """Bucketing produces a sparse, ascending list of (bucket, count) pairs."""

    def test_spec_example(self) -> None:
        """Returns 0.0010, 0.00104, 0.0011, -0.0025, 0.0010 give three buckets."""
        bps = to_basis_points(pd.Series([0.0010, 0.00104, 0.0011, -0.0025, 0.0010]))

        assert build_histogram(bps) == [(-25, 1), (10, 3), (11, 1)]

    def test_zero_count_buckets_are_omitted(self) -> None:
        """Only observed buckets appear — no padding between -5 and 5."""
        result = build_histogram(pd.Series([-5, 5, 5]))

        assert result == [(-5, 1), (5, 2)]

    def test_sorted_ascending_regardless_of_input_order(self) -> None:
        """Buckets are ordered from most negative to most positive."""
        result = build_histogram(pd.Series([12, -3, 0, 7]))

        assert [bucket for bucket, _ in result] == [-3, 0, 7, 12]

    def test_empty_input_gives_empty_histogram(self) -> None:
        """No observations means no buckets."""
        assert build_histogram(pd.Series([], dtype="int64")) == []

    def test_buckets_and_counts_are_plain_python_ints(self) -> None:
        """Values are JSON-serialisable Python ints, not numpy scalars."""
        result = build_histogram(pd.Series([1, 1, 2]))

        assert all(type(bucket) is int and type(count) is int for bucket, count in result)

    def test_counts_sum_to_number_of_observations(self) -> None:
        """Every observation lands in exactly one bucket."""
        bps = pd.Series([3, 3, -1, 0, 0, 0, 9])

        assert sum(count for _, count in build_histogram(bps)) == len(bps)


def _independent_sample_moments(values: list[int]) -> tuple[float, float, float, float]:
    """Compute mean, sample std, adjusted skewness and sample excess kurtosis by formula.

    Args:
        values: Observations.

    Returns:
        (mean, sample standard deviation, skewness, excess kurtosis).
    """
    n = len(values)
    mean = sum(values) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))
    z = [(x - mean) / std for x in values]
    skew = n / ((n - 1) * (n - 2)) * sum(v**3 for v in z)
    kurt = n * (n + 1) / ((n - 1) * (n - 2) * (n - 3)) * sum(v**4 for v in z) - 3 * (
        (n - 1) ** 2
    ) / ((n - 2) * (n - 3))
    return mean, std, skew, kurt


class TestComputeStatistics:
    """Distribution statistics over the rounded basis point observations."""

    def test_spec_example_basic_statistics(self) -> None:
        """Observations -10, 0, 0, 10, 20 give the documented basics."""
        stats = compute_statistics(pd.Series([-10, 0, 0, 10, 20]))

        assert stats.count == 5
        assert stats.minimum == -10
        assert stats.maximum == 20
        assert stats.mean == pytest.approx(4.0, rel=1e-9)
        assert stats.median == pytest.approx(0.0)
        assert stats.mode == 0

    def test_std_dev_and_bands(self) -> None:
        """Sample std dev, plus multiples and band edges for 1, 2 and 3 sigma."""
        stats = compute_statistics(pd.Series([-10, 0, 0, 10, 20]))
        expected_std = math.sqrt(520 / 4)

        assert stats.std_dev == pytest.approx(expected_std, rel=1e-9)
        assert [band.sigma for band in stats.std_dev_bands] == [1, 2, 3]
        for band in stats.std_dev_bands:
            assert band.multiple == pytest.approx(band.sigma * expected_std, rel=1e-9)
            assert band.lower == pytest.approx(4.0 - band.sigma * expected_std, rel=1e-9)
            assert band.upper == pytest.approx(4.0 + band.sigma * expected_std, rel=1e-9)

    def test_skewness_and_kurtosis_match_independent_formulas(self) -> None:
        """Adjusted skewness and sample excess kurtosis agree with hand formulas."""
        values = [-10, 0, 0, 10, 20, 35, -4]
        _, _, skew, kurt = _independent_sample_moments(values)

        stats = compute_statistics(pd.Series(values))

        assert stats.skewness == pytest.approx(skew, rel=1e-9)
        assert stats.kurtosis == pytest.approx(kurt, rel=1e-9)

    def test_mode_tie_reports_smallest_bucket(self) -> None:
        """Buckets 5 and -3 both occur twice; the smaller bucket wins."""
        stats = compute_statistics(pd.Series([5, 5, -3, -3, 9]))

        assert stats.mode == -3

    def test_median_of_even_count_is_midpoint(self) -> None:
        """The median of 1, 2, 3, 4 is 2.5."""
        assert compute_statistics(pd.Series([1, 2, 3, 4])).median == pytest.approx(2.5)

    def test_zero_observations_gives_nulls_and_zero_count(self) -> None:
        """Nothing observed: count 0, everything else null, no bands."""
        stats = compute_statistics(pd.Series([], dtype="int64"))

        assert stats.count == 0
        assert stats.mean is None
        assert stats.median is None
        assert stats.mode is None
        assert stats.minimum is None
        assert stats.maximum is None
        assert stats.std_dev is None
        assert stats.std_dev_bands == []
        assert stats.skewness is None
        assert stats.kurtosis is None

    def test_single_observation(self) -> None:
        """One observation: location statistics defined, dispersion undefined."""
        stats = compute_statistics(pd.Series([7]))

        assert (stats.count, stats.mean, stats.median, stats.mode) == (1, 7.0, 7.0, 7)
        assert (stats.minimum, stats.maximum) == (7, 7)
        assert stats.std_dev is None
        assert stats.std_dev_bands == []
        assert stats.skewness is None
        assert stats.kurtosis is None

    def test_two_observations_have_std_dev_but_no_skewness(self) -> None:
        """Skewness needs at least 3 observations."""
        stats = compute_statistics(pd.Series([0, 10]))

        assert stats.std_dev == pytest.approx(math.sqrt(50))
        assert len(stats.std_dev_bands) == 3
        assert stats.skewness is None
        assert stats.kurtosis is None

    def test_three_observations_have_skewness_but_no_kurtosis(self) -> None:
        """Kurtosis needs at least 4 observations."""
        stats = compute_statistics(pd.Series([0, 5, 20]))

        assert stats.skewness is not None
        assert stats.kurtosis is None

    def test_constant_series_collapses_bands_and_nulls_shape_statistics(self) -> None:
        """Zero variance: std dev 0, bands sit on the mean, skewness/kurtosis undefined."""
        stats = compute_statistics(pd.Series([4, 4, 4, 4, 4]))

        assert stats.std_dev == 0.0
        assert all(b.lower == b.upper == 4.0 and b.multiple == 0.0 for b in stats.std_dev_bands)
        assert stats.skewness is None
        assert stats.kurtosis is None

    def test_output_contains_no_nan_or_infinity(self) -> None:
        """Every numeric field is finite or None, so JSON serialisation is safe."""
        for values in ([], [1], [1, 2], [1, 2, 3], [3, 3, 3, 3], [-10, 0, 0, 10, 20]):
            dumped = compute_statistics(pd.Series(values, dtype="int64")).model_dump()
            flat = [dumped[k] for k in dumped if k != "std_dev_bands"]
            for band in dumped["std_dev_bands"]:
                flat.extend(band.values())
            assert all(v is None or math.isfinite(v) for v in flat)


def test_ten_years_of_daily_returns_are_processed_quickly() -> None:
    """Rounding, bucketing and statistics over ~2,600 observations take well under a second."""
    rng = random.Random(42)
    returns = pd.Series([rng.gauss(0.0004, 0.01) for _ in range(2_600)])

    start = time.perf_counter()
    bps = to_basis_points(returns)
    histogram = build_histogram(bps)
    stats = compute_statistics(bps)
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0
    assert stats.count == 2_600
    assert sum(count for _, count in histogram) == 2_600
