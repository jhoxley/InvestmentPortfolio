"""Pure, side-effect-free helper for the Risk page's histogram chart.

Mirrors `_performance_chart.py`'s structure and separation-of-concerns
rationale (kept out of risk.py so it stays importable from a plain unit
test), but renders a bar chart of basis-point buckets vs. day-counts rather
than a line chart of return measures over time.
"""

from __future__ import annotations

import plotly.graph_objects as go


def build_figure(histogram: list[tuple[int, int]]) -> go.Figure:
    """Build a Plotly Figure with one bar per basis-point bucket.

    Args:
        histogram: `[basis_point_bucket, day_count]` pairs from a
            ReturnHistogramResponse, plotted verbatim in the given order — no
            calculation, sorting, or re-bucketing.

    Returns:
        A styled Figure: one go.Bar trace, x = each pair's bucket, y = each
        pair's count.
    """
    x_values = [pair[0] for pair in histogram]
    y_values = [pair[1] for pair in histogram]
    fig = go.Figure(
        data=[
            go.Bar(
                x=x_values,
                y=y_values,
                marker={"color": "#1f77b4"},
                hovertemplate="%{x} bps: %{y} day(s)<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title={"text": "Daily Return Distribution", "font": {"size": 20}},
        template="plotly_white",
        font={"family": "Helvetica, Arial, sans-serif"},
        margin={"l": 60, "r": 30, "t": 60, "b": 60},
        xaxis={"title": "Return (bps)", "showgrid": True, "gridcolor": "#e6e6e6"},
        yaxis={"title": "Days", "showgrid": True, "gridcolor": "#e6e6e6"},
    )
    return fig
