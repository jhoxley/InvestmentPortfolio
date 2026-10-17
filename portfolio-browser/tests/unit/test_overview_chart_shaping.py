"""Unit tests for the pure chart-shaping helpers in src/pages/_overview_chart.py.

No Dash app / browser required — these are plain functions taking/returning
dicts and plotly.graph_objects.Figure objects. The date-range/shortcut tests
that used to live here have moved to tests/unit/test_date_range_controls.py
(specs/018-positions-page/research.md #1).
"""

from __future__ import annotations

from datetime import date

from src.pages._overview_chart import (
    ATTRIBUTE_COLORS,
    DEFAULT_ATTRIBUTE_COLOR,
    _build_figure,
    _color_for,
)


def test_color_for_known_attribute_is_stable() -> None:
    first = _color_for("market_value")
    second = _color_for("market_value")
    assert first == second == ATTRIBUTE_COLORS["market_value"]


def test_color_for_unknown_attribute_falls_back_to_default() -> None:
    assert _color_for("some_future_attribute") == DEFAULT_ATTRIBUTE_COLOR


_ENTRIES = [
    {"date": date(2024, 1, 2), "market_value": 240120.11, "capital": 236634.5},
    {"date": date(2024, 1, 3), "market_value": 241000.0, "capital": 236634.5},
]


def test_build_figure_one_toggled_metric_produces_one_trace() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"])

    assert len(fig.data) == 1
    trace = fig.data[0]
    assert trace.name == "market_value"
    assert list(trace.x) == [date(2024, 1, 2), date(2024, 1, 3)]
    assert list(trace.y) == [240120.11, 241000.0]
    assert trace.line.color == ATTRIBUTE_COLORS["market_value"]


def test_build_figure_multiple_toggled_metrics_produce_distinct_colors() -> None:
    fig = _build_figure(_ENTRIES, ["market_value", "capital"])

    assert len(fig.data) == 2
    colors = {trace.name: trace.line.color for trace in fig.data}
    assert colors["market_value"] != colors["capital"]


def test_build_figure_legend_positioned_below_plot() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"])

    assert fig.layout.legend.orientation == "h"
    assert fig.layout.legend.y < 0


def test_build_figure_yaxis_is_gbp_formatted() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"])

    assert fig.layout.yaxis.tickprefix == "£"
