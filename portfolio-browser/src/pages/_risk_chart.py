"""Pure, side-effect-free helper for the Risk page's histogram chart.

Mirrors `_performance_chart.py`'s structure and separation-of-concerns
rationale (kept out of risk.py so it stays importable from a plain unit
test), but renders a bar chart of basis-point buckets vs. day-counts rather
than a line chart of return measures over time.
"""

from __future__ import annotations

from collections import defaultdict

import plotly.graph_objects as go

from src.models.portfolio_analysis import HistogramStatistics, StdDevBand

_BUCKET_WIDTH_BP = 10

# Band color mapping (data-model.md's Band Color Mapping table). Fixed,
# in-code constants — this page's only consumer, not user-configurable
# (Constitution Principle IV; mirrors `_performance_chart.py`'s own
# PERFORMANCE_ATTRIBUTE_COLORS precedent).
_BAND_1_COLOR = "#2ca02c"  # mid-green: within sigma=1
_BAND_2_COLOR = "#d4c93b"  # mid-yellow: outside sigma=1, within sigma=2
_BAND_3_COLOR = "#ff7f0e"  # mid-orange: outside sigma=2, within sigma=3
_OUTSIDE_BANDS_COLOR = "#d62728"  # red: outside sigma=3
_NO_STD_DEV_COLOR = "#7f7f7f"  # neutral gray: std_dev_bands is empty (std dev undefined)


def _color_for_bucket(center_bp: int, std_dev_bands: list[StdDevBand]) -> str:
    """Return the color for a bucket, based on which std-dev band contains its center.

    Args:
        center_bp: The bucket's center value, in basis points.
        std_dev_bands: The response's `statistics.std_dev_bands`, in
            ascending sigma order (per the API's own contract). Bands are
            tested smallest-sigma-first so a bucket within the sigma=1 band
            is never mistakenly matched to the wider sigma=2/3 bands.

    Returns:
        `_BAND_1_COLOR`/`_BAND_2_COLOR`/`_BAND_3_COLOR` for a center within
        that band's `lower..upper`, `_OUTSIDE_BANDS_COLOR` when bands exist
        but none match, or `_NO_STD_DEV_COLOR` when `std_dev_bands` is empty
        (std dev undefined for too few observations).
    """
    if not std_dev_bands:
        return _NO_STD_DEV_COLOR
    band_colors = {1: _BAND_1_COLOR, 2: _BAND_2_COLOR, 3: _BAND_3_COLOR}
    for band in sorted(std_dev_bands, key=lambda b: b.sigma):
        if band.lower <= center_bp <= band.upper:
            return band_colors[band.sigma]
    return _OUTSIDE_BANDS_COLOR


def bucket_histogram(histogram: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Group raw per-basis-point observations into 10bp buckets, summing counts.

    Args:
        histogram: `[basis_point_bucket, day_count]` pairs from a
            ReturnHistogramResponse, at the API's own 1bp granularity.

    Returns:
        `(bucket_center_bp, total_count)` pairs, one per non-empty 10bp-wide
        bucket, sorted ascending by bucket center. Bucket boundaries are
        aligned to multiples of `_BUCKET_WIDTH_BP` via floor division
        (research.md #2), so every bp value maps to exactly one bucket with
        no gaps or overlaps.
    """
    totals: dict[int, int] = defaultdict(int)
    for bp, count in histogram:
        bucket_start = (bp // _BUCKET_WIDTH_BP) * _BUCKET_WIDTH_BP
        center = bucket_start + _BUCKET_WIDTH_BP // 2
        totals[center] += count
    return sorted(totals.items())


def build_figure(histogram: list[tuple[int, int]], statistics: HistogramStatistics) -> go.Figure:
    """Build a Plotly Figure with one bar per 10bp (0.1%) bucket.

    Args:
        histogram: `[basis_point_bucket, day_count]` pairs from a
            ReturnHistogramResponse, at the API's own 1bp granularity.
        statistics: The same response's `statistics` object (mean, median,
            and std_dev_bands drive the reference lines and bar coloring).

    Returns:
        A styled Figure: one go.Bar trace, x = each bucket's center
        (converted to percent), y = each bucket's summed count.
    """
    # The page only ever calls this once statistics.count > 0 (a count-0
    # response short-circuits to the shared empty state before build_figure
    # is invoked), and mean/median are only None when count == 0 per
    # HistogramStatistics's own contract — so both are always defined here.
    assert statistics.mean is not None
    assert statistics.median is not None

    buckets = bucket_histogram(histogram)
    x_values = [center / 100 for center, _ in buckets]
    y_values = [count for _, count in buckets]
    if statistics.std_dev_bands:
        colors = [_color_for_bucket(center, statistics.std_dev_bands) for center, _ in buckets]
    else:
        colors = [_NO_STD_DEV_COLOR] * len(buckets)
    fig = go.Figure(
        data=[
            go.Bar(
                x=x_values,
                y=y_values,
                width=_BUCKET_WIDTH_BP / 100,
                marker={"color": colors},
                hovertemplate="%{x:.2f}%: %{y} day(s)<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title={"text": "Daily Return Distribution", "font": {"size": 20}},
        template="plotly_white",
        font={"family": "Helvetica, Arial, sans-serif"},
        margin={"l": 60, "r": 30, "t": 60, "b": 60},
        xaxis={
            "title": "Return (%)",
            "ticksuffix": "%",
            "showgrid": True,
            "gridcolor": "#e6e6e6",
        },
        yaxis={"title": "Days", "showgrid": True, "gridcolor": "#e6e6e6"},
    )
    fig.add_vline(
        x=statistics.mean / 100,
        line_dash="dash",
        line_color="#2c2c2c",
        annotation_text="Mean",
        annotation_position="top",
    )
    fig.add_vline(
        x=statistics.median / 100,
        line_dash="dot",
        line_color="#555555",
        annotation_text="Median",
        annotation_position="bottom",
    )
    return fig
