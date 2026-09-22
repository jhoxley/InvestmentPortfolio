"""Unit tests for the pure chart-shaping helpers in src/pages/_projection_chart.py.

No Dash app / browser required — these are plain functions taking/returning
dicts and plotly.graph_objects.Figure objects, mirroring
tests/unit/test_performance_chart_shaping.py's own structure.
"""

from __future__ import annotations

from datetime import date

from src.pages._projection_chart import (
    DEFAULT_PROJECTION_SERIES_COLOR,
    HISTORICAL_SERIES_LABEL,
    PROJECTION_SERIES_COLORS,
    _build_figure,
)

_HISTORICAL_ONLY = [
    {"date": date(2016, 4, 30), "position": "Historical", "market_value": 10000.0},
    {"date": date(2026, 9, 22), "position": "Historical", "market_value": 48000.0},
]

_HISTORICAL_PLUS_ONE_RETURN = [
    *_HISTORICAL_ONLY,
    {"date": date(2036, 9, 22), "position": "3Y", "market_value": 71000.0},
]

_HISTORICAL_PLUS_TWO_RETURNS = [
    *_HISTORICAL_PLUS_ONE_RETURN,
    {"date": date(2036, 9, 22), "position": "5Y", "market_value": 78000.0},
]


def test_build_figure_historical_only_produces_one_trace() -> None:
    fig = _build_figure(_HISTORICAL_ONLY)

    assert len(fig.data) == 1
    trace = fig.data[0]
    assert trace.name == HISTORICAL_SERIES_LABEL
    assert list(trace.x) == [date(2016, 4, 30), date(2026, 9, 22)]
    assert list(trace.y) == [10000.0, 48000.0]
    assert trace.line.color == PROJECTION_SERIES_COLORS[HISTORICAL_SERIES_LABEL]


def test_build_figure_historical_trace_is_solid() -> None:
    fig = _build_figure(_HISTORICAL_ONLY)

    assert fig.data[0].line.dash == "solid"


def test_build_figure_one_return_produces_two_traces() -> None:
    fig = _build_figure(_HISTORICAL_PLUS_ONE_RETURN)

    assert len(fig.data) == 2
    names = {trace.name for trace in fig.data}
    assert names == {"Historical", "3Y"}


def test_build_figure_projected_trace_is_dashed() -> None:
    fig = _build_figure(_HISTORICAL_PLUS_ONE_RETURN)

    projected = next(trace for trace in fig.data if trace.name == "3Y")
    assert projected.line.dash == "dash"


def test_build_figure_historical_always_appears_first() -> None:
    fig = _build_figure(_HISTORICAL_PLUS_TWO_RETURNS)

    assert fig.data[0].name == HISTORICAL_SERIES_LABEL


def test_build_figure_multiple_returns_produce_distinct_colors() -> None:
    fig = _build_figure(_HISTORICAL_PLUS_TWO_RETURNS)

    colors = {trace.name: trace.line.color for trace in fig.data}
    assert len({colors["Historical"], colors["3Y"], colors["5Y"]}) == 3


def test_build_figure_every_projected_line_starts_at_the_same_point() -> None:
    """FR-011: every projected line begins at the start date's market value."""
    entries = [
        {"date": date(2026, 9, 22), "position": "Historical", "market_value": 48000.0},
        {"date": date(2026, 9, 22), "position": "3Y", "market_value": 48000.0},
        {"date": date(2026, 9, 22), "position": "5Y", "market_value": 48000.0},
        {"date": date(2036, 9, 22), "position": "3Y", "market_value": 71000.0},
        {"date": date(2036, 9, 22), "position": "5Y", "market_value": 78000.0},
    ]
    fig = _build_figure(entries)

    three_y = next(trace for trace in fig.data if trace.name == "3Y")
    five_y = next(trace for trace in fig.data if trace.name == "5Y")
    assert three_y.y[0] == 48000.0
    assert five_y.y[0] == 48000.0


def test_build_figure_unknown_series_label_falls_back_to_default_color() -> None:
    entries = [{"date": date(2026, 9, 22), "position": "Some Future Return", "market_value": 1.0}]

    fig = _build_figure(entries)

    assert fig.data[0].line.color == DEFAULT_PROJECTION_SERIES_COLOR


def test_build_figure_hover_template_uses_currency_format() -> None:
    fig = _build_figure(_HISTORICAL_ONLY)

    assert "£%{y:,.2f}" in fig.data[0].hovertemplate


def test_build_figure_legend_positioned_below_plot() -> None:
    fig = _build_figure(_HISTORICAL_ONLY)

    assert fig.layout.legend.orientation == "h"
    assert fig.layout.legend.y < 0


def test_build_figure_empty_entries_produces_no_traces() -> None:
    fig = _build_figure([])

    assert len(fig.data) == 0
