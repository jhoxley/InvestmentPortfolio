"""Unit tests for the pure chart-shaping helpers in src/pages/_performance_chart.py.

No Dash app / browser required — these are plain functions taking/returning
dicts and plotly.graph_objects.Figure objects, mirroring
tests/unit/test_overview_chart_shaping.py's own structure (specs/020-
performance-page-chart/research.md #6).
"""

from __future__ import annotations

from datetime import date

from src.pages._performance_chart import (
    DEFAULT_PERFORMANCE_ATTRIBUTE_COLOR,
    PERFORMANCE_ATTRIBUTE_COLORS,
    _build_figure,
)

_ENTRIES = [
    {"date": date(2024, 1, 2), "ITD": 0.183, "1Y": 0.071},
    {"date": date(2024, 1, 3), "ITD": 0.187, "1Y": 0.069},
]


def test_build_figure_one_toggled_measure_produces_one_trace() -> None:
    fig = _build_figure(_ENTRIES, ["ITD"])

    assert len(fig.data) == 1
    trace = fig.data[0]
    assert trace.name == "ITD"
    assert list(trace.x) == [date(2024, 1, 2), date(2024, 1, 3)]
    assert list(trace.y) == [0.183, 0.187]
    assert trace.line.color == PERFORMANCE_ATTRIBUTE_COLORS["ITD"]


def test_build_figure_multiple_toggled_measures_produce_distinct_colors() -> None:
    fig = _build_figure(_ENTRIES, ["ITD", "1Y"])

    assert len(fig.data) == 2
    colors = {trace.name: trace.line.color for trace in fig.data}
    assert colors["ITD"] != colors["1Y"]


def test_build_figure_unknown_measure_falls_back_to_default_color() -> None:
    fig = _build_figure(_ENTRIES, ["some_future_measure"])

    assert fig.data[0].line.color == DEFAULT_PERFORMANCE_ATTRIBUTE_COLOR


def test_build_figure_yaxis_is_percentage_formatted() -> None:
    fig = _build_figure(_ENTRIES, ["ITD"])

    assert fig.layout.yaxis.tickformat == ".1%"


def test_build_figure_hover_template_uses_percentage_format() -> None:
    fig = _build_figure(_ENTRIES, ["ITD"])

    assert "%{y:.1%}" in fig.data[0].hovertemplate


def test_build_figure_legend_positioned_below_plot() -> None:
    fig = _build_figure(_ENTRIES, ["ITD"])

    assert fig.layout.legend.orientation == "h"
    assert fig.layout.legend.y < 0


def test_build_figure_missing_measure_leaves_gap_not_error() -> None:
    entries_with_gap = [
        {"date": date(2024, 1, 2), "ITD": 0.183},
        {"date": date(2024, 1, 3), "ITD": 0.187, "5Y": 0.062},
    ]

    fig = _build_figure(entries_with_gap, ["ITD", "5Y"])

    five_y_trace = next(trace for trace in fig.data if trace.name == "5Y")
    assert list(five_y_trace.y) == [None, 0.062]
