"""Pure, side-effect-free helpers for the Performance page's chart.

Mirrors `_overview_chart.py`'s own structure and separation-of-concerns
rationale (kept out of performance.py so it stays importable from a plain
unit test), but formats every value as a percentage return rather than a
GBP currency figure, since every Performance measure (ITD, ITD (Ann.), 1Y,
3Y, 5Y) is a return rate, not a monetary amount (specs/020-performance-
page-chart/research.md #6).
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

# Fixed, stable measure -> color mapping, mirroring _overview_chart.py's own
# ATTRIBUTE_COLORS/DEFAULT_ATTRIBUTE_COLOR shape. Known measure names per the
# portfolio-analysis-service 007-performance-endpoints contract.
PERFORMANCE_ATTRIBUTE_COLORS: dict[str, str] = {
    "ITD": "#1f77b4",
    "ITD (Ann.)": "#2ca02c",
    "1Y": "#d62728",
    "3Y": "#ff7f0e",
    "5Y": "#9467bd",
}
DEFAULT_PERFORMANCE_ATTRIBUTE_COLOR = "#7f7f7f"


def _color_for(attribute: str) -> str:
    """Return the fixed color for a performance measure, falling back to a default.

    Args:
        attribute: The wire-format measure name (e.g. "ITD").

    Returns:
        A hex color string, stable across calls for the same measure.
    """
    return PERFORMANCE_ATTRIBUTE_COLORS.get(attribute, DEFAULT_PERFORMANCE_ATTRIBUTE_COLOR)


def _build_figure(entries: list[dict[str, Any]], toggled_attributes: list[str]) -> go.Figure:
    """Build a Plotly Figure with one line per toggled-on performance measure.

    Args:
        entries: Raw `entries` from a performance TimeSeriesResponse (dicts
            with `date` plus one key per requested measure) — plotted
            verbatim, no calculation. A measure absent from an entry
            (insufficient history) is plotted as a gap (`None`), never
            backfilled or interpolated.
        toggled_attributes: Measure names to plot as their own line, in
            order.

    Returns:
        A styled Figure: one go.Scatter trace per measure, a horizontal
        legend below the plot, percentage-formatted y-axis, and a per-point
        hover template showing date/measure/value as a percentage.
    """
    dates = [entry["date"] for entry in entries]
    fig = go.Figure()
    for attribute in toggled_attributes:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=[entry.get(attribute) for entry in entries],
                mode="lines+markers",
                name=attribute,
                line={"color": _color_for(attribute), "width": 3},
                hovertemplate="%{x|%Y-%m-%d}<br>" + attribute + ": %{y:.1%}<extra></extra>",
            )
        )
    fig.update_layout(
        title={"text": "Account Performance", "font": {"size": 20}},
        template="plotly_white",
        font={"family": "Helvetica, Arial, sans-serif"},
        legend={"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
        hovermode="x unified",
        margin={"l": 60, "r": 30, "t": 60, "b": 80},
        xaxis={"title": "Date", "showgrid": True, "gridcolor": "#e6e6e6"},
        yaxis={
            "title": "Return",
            "tickformat": ".1%",
            "showgrid": True,
            "gridcolor": "#e6e6e6",
        },
    )
    return fig
