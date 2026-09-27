"""Pure functions for bucketing daily returns into whole basis points."""

import math

import pandas as pd

from app.models.risk import HistogramStatistics, StdDevBand

BPS_PER_UNIT_RETURN = 10_000
_FLOAT_NOISE_DECIMALS = 9
_SIGMA_LEVELS = (1, 2, 3)
_MIN_OBS_STD_DEV = 2
_MIN_OBS_SKEWNESS = 3
_MIN_OBS_KURTOSIS = 4


def round_half_away_from_zero(values: pd.Series) -> pd.Series:
    """Round to the nearest integer, with exact halves rounding away from zero.

    Deliberately not `Series.round()`, which uses banker's rounding (0.5 -> 0, 2.5 -> 2).

    Args:
        values: Numeric values to round.

    Returns:
        Integer series: 0.5 -> 1, -0.5 -> -1, 2.5 -> 3, -2.5 -> -3.
    """
    sign = (values > 0).astype("int64") - (values < 0).astype("int64")
    magnitude = (values.abs() + 0.5) // 1
    return (sign * magnitude).astype("int64")


def to_basis_points(daily_returns: pd.Series) -> pd.Series:
    """Convert fractional daily returns to integer basis points.

    The product is pre-rounded to 9 decimals to strip binary floating-point noise, so a
    return that is a decimal half in basis points (e.g. 0.00015, which multiplies out to
    1.4999999999999998) still rounds away from zero as expected.

    Args:
        daily_returns: Daily returns as fractions (0.01 = 1%).

    Returns:
        Integer basis points (1 bp = 0.01% = 1/10,000).
    """
    scaled = (daily_returns * BPS_PER_UNIT_RETURN).round(_FLOAT_NOISE_DECIMALS)
    return round_half_away_from_zero(scaled)


def build_histogram(bps: pd.Series) -> list[tuple[int, int]]:
    """Count observations per basis point bucket.

    Args:
        bps: Integer basis point observations, one per business day.

    Returns:
        (bucket, count) pairs sorted by bucket ascending; buckets with no observations are
        omitted. Empty input gives an empty list.
    """
    counts = bps.value_counts().sort_index()
    return [(int(bucket), int(count)) for bucket, count in counts.items()]


def _finite_or_none(value: float) -> float | None:
    """Return the value as a float, or None when it is NaN or infinite.

    Args:
        value: A numeric statistic.

    Returns:
        The float value, or None if it is not finite.
    """
    number = float(value)
    return number if math.isfinite(number) else None


def compute_statistics(bps: pd.Series) -> HistogramStatistics:
    """Compute distribution statistics over integer basis point observations.

    Sample (ddof=1) standard deviation, adjusted Fisher-Pearson skewness and sample excess
    kurtosis. A statistic that is undefined for the available observations is None: standard
    deviation needs 2 observations, skewness 3, kurtosis 4, and skewness/kurtosis are also
    undefined when there is no variance.

    Args:
        bps: Integer basis point observations, one per business day. May be empty.

    Returns:
        HistogramStatistics; with no observations only count (0) is populated.
    """
    count = len(bps)
    if count == 0:
        return HistogramStatistics(
            count=0,
            mean=None,
            median=None,
            mode=None,
            minimum=None,
            maximum=None,
            std_dev=None,
            std_dev_bands=[],
            skewness=None,
            kurtosis=None,
        )

    mean = float(bps.mean())
    std_dev = _finite_or_none(bps.std(ddof=1)) if count >= _MIN_OBS_STD_DEV else None
    has_variance = std_dev is not None and std_dev > 0

    bands = (
        [
            StdDevBand(
                sigma=sigma,
                multiple=sigma * std_dev,
                lower=mean - sigma * std_dev,
                upper=mean + sigma * std_dev,
            )
            for sigma in _SIGMA_LEVELS
        ]
        if std_dev is not None
        else []
    )
    skewness = _finite_or_none(bps.skew()) if has_variance and count >= _MIN_OBS_SKEWNESS else None
    kurtosis = _finite_or_none(bps.kurt()) if has_variance and count >= _MIN_OBS_KURTOSIS else None

    return HistogramStatistics(
        count=count,
        mean=mean,
        median=float(bps.median()),
        mode=int(bps.mode().min()),
        minimum=int(bps.min()),
        maximum=int(bps.max()),
        std_dev=std_dev,
        std_dev_bands=bands,
        skewness=skewness,
        kurtosis=kurtosis,
    )
