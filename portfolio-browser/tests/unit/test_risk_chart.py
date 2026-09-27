"""Unit tests for the Risk page's pure histogram chart builder (024, 025)."""

from __future__ import annotations

import plotly.graph_objects as go

from src.models.portfolio_analysis import HistogramStatistics, StdDevBand
from src.pages._risk_chart import (
    _BAND_1_COLOR,
    _BAND_2_COLOR,
    _BAND_3_COLOR,
    _NO_STD_DEV_COLOR,
    _OUTSIDE_BANDS_COLOR,
    _color_for_bucket,
    bucket_histogram,
    build_figure,
)

_EXAMPLE_BANDS = [
    StdDevBand(sigma=1, multiple=14.2, lower=-10, upper=18),
    StdDevBand(sigma=2, multiple=28.4, lower=-24, upper=32),
    StdDevBand(sigma=3, multiple=42.6, lower=-38, upper=46),
]


def _statistics(**overrides: object) -> HistogramStatistics:
    defaults: dict[str, object] = {
        "count": 27,
        "mean": 4.1,
        "median": 3.0,
        "mode": 0,
        "minimum": -25,
        "maximum": 65,
        "std_dev": 14.2,
        "std_dev_bands": [],
        "skewness": 1.8,
        "kurtosis": 6.2,
    }
    defaults.update(overrides)
    return HistogramStatistics.model_validate(defaults)


def test_bucket_histogram_groups_into_10bp_buckets_and_sums_counts() -> None:
    histogram = [(-25, 1), (-24, 2), (-3, 4), (0, 12), (7, 9), (65, 1)]

    buckets = bucket_histogram(histogram)

    # (bp // 10) * 10 + 5: -25 -> -30+5=-25; -24 -> -30+5=-25; -3 -> -10+5=-5;
    # 0 -> 0+5=5; 7 -> 0+5=5; 65 -> 60+5=65.
    assert buckets == [(-25, 3), (-5, 4), (5, 21), (65, 1)]


def test_bucket_histogram_empty_list_returns_empty_list() -> None:
    assert bucket_histogram([]) == []


def test_bucket_histogram_single_value_returns_single_bucket() -> None:
    assert bucket_histogram([(42, 7)]) == [(45, 7)]


def test_build_figure_signature_accepts_statistics() -> None:
    figure = build_figure([(-25, 1), (0, 12), (65, 1)], _statistics())

    assert isinstance(figure, go.Figure)


def test_build_figure_bars_use_percent_centers() -> None:
    # -25 and -24 both fall in the bucket centered at -25bp; 7 falls in the
    # bucket centered at 5bp. Centers convert to percent via /100.
    histogram = [(-25, 1), (-24, 2), (7, 9)]

    figure = build_figure(histogram, _statistics())

    assert list(figure.data[0].x) == [-0.25, 0.05]
    assert figure.data[0].width == 0.1
    assert figure.layout.xaxis.ticksuffix == "%"


def _vline_shapes(figure: go.Figure) -> list:
    return [
        shape
        for shape in figure.layout.shapes
        if shape.type == "line" and shape.x0 == shape.x1
    ]


def test_build_figure_adds_mean_and_median_vlines() -> None:
    stats = _statistics(mean=10.0, median=-5.0)

    figure = build_figure([(-25, 1), (0, 12), (65, 1)], stats)

    lines = _vline_shapes(figure)
    assert len(lines) == 2
    xs = sorted(line.x0 for line in lines)
    assert xs == [-0.05, 0.10]
    assert lines[0].line.dash != lines[1].line.dash or lines[0].line.color != lines[1].line.color


def test_build_figure_draws_both_lines_when_mean_equals_median() -> None:
    stats = _statistics(mean=5.0, median=5.0)

    figure = build_figure([(-25, 1), (0, 12), (65, 1)], stats)

    lines = _vline_shapes(figure)
    assert len(lines) == 2


# --- band coloring (025 US3) --------------------------------------------------


def test_color_for_bucket_within_sigma1_is_band1_color() -> None:
    assert _color_for_bucket(0, _EXAMPLE_BANDS) == _BAND_1_COLOR


def test_color_for_bucket_outside_sigma1_within_sigma2_is_band2_color() -> None:
    assert _color_for_bucket(25, _EXAMPLE_BANDS) == _BAND_2_COLOR


def test_color_for_bucket_outside_sigma2_within_sigma3_is_band3_color() -> None:
    assert _color_for_bucket(40, _EXAMPLE_BANDS) == _BAND_3_COLOR


def test_color_for_bucket_outside_sigma3_is_outside_bands_color() -> None:
    assert _color_for_bucket(50, _EXAMPLE_BANDS) == _OUTSIDE_BANDS_COLOR


def test_color_for_bucket_no_bands_is_neutral_color() -> None:
    assert _color_for_bucket(0, []) == _NO_STD_DEV_COLOR
    assert _color_for_bucket(999, []) == _NO_STD_DEV_COLOR


def test_build_figure_colors_bars_per_band() -> None:
    stats = _statistics(std_dev_bands=_EXAMPLE_BANDS)
    histogram = [(0, 1), (25, 1), (40, 1), (50, 1)]

    figure = build_figure(histogram, stats)

    colors = list(figure.data[0].marker.color)
    buckets = bucket_histogram(histogram)
    expected = [_color_for_bucket(center, _EXAMPLE_BANDS) for center, _ in buckets]
    assert colors == expected


def test_build_figure_uses_neutral_color_when_std_dev_undefined() -> None:
    stats = _statistics(std_dev_bands=[])
    histogram = [(0, 1), (25, 1), (40, 1), (50, 1)]

    figure = build_figure(histogram, stats)

    colors = list(figure.data[0].marker.color)
    assert colors == [_NO_STD_DEV_COLOR] * len(colors)
