"""Unit tests for the Risk page's pure histogram chart builder (024)."""

from __future__ import annotations

import plotly.graph_objects as go

from src.pages._risk_chart import build_figure


def test_build_figure_maps_pairs_to_bar_x_and_y() -> None:
    histogram = [(-25, 1), (-3, 4), (0, 12), (7, 9), (65, 1)]

    figure = build_figure(histogram)

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1
    bar = figure.data[0]
    assert list(bar.x) == [-25, -3, 0, 7, 65]
    assert list(bar.y) == [1, 4, 12, 9, 1]


def test_build_figure_empty_histogram_produces_empty_trace() -> None:
    figure = build_figure([])

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1
    assert list(figure.data[0].x) == []
    assert list(figure.data[0].y) == []
