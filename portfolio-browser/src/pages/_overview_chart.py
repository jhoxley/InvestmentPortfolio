"""Pure, side-effect-free helpers for the Overview page's chart (FR-009-FR-012).

Kept out of overview.py deliberately: overview.py calls `dash.register_page()`
at import time, which raises unless a Dash app has already been instantiated —
that makes overview.py unsafe to import from a plain unit test. These
functions have no such dependency, so they live here and overview.py imports
them for use in its layout/callbacks (see research.md #8 for the underlying
"purely presentational transform" rationale).

The date-range/shortcut helpers and `SHORTCUT_*` constants that used to live
in this module have moved to `src/components/date_range_controls.py`, now
shared with the Positions page (specs/018-positions-page/research.md #1) —
import them from there instead.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

# Fixed, stable metric -> color mapping (spec Assumptions: "a fixed, consistent
# color used everywhere it appears"). Known attribute names per the 0.4.0
# portfolio-analysis-service contract (contracts/portfolio-analysis-api.md).
ATTRIBUTE_COLORS: dict[str, str] = {
    "capital": "#1f77b4",
    "income": "#2ca02c",
    "book_cost": "#9467bd",
    "market_value": "#d62728",
    "pnl": "#ff7f0e",
}
DEFAULT_ATTRIBUTE_COLOR = "#7f7f7f"


def _color_for(attribute: str) -> str:
    """Return the fixed color for an attribute, falling back to a default.

    Args:
        attribute: The wire-format attribute name (e.g. "market_value").

    Returns:
        A hex color string, stable across calls for the same attribute.
    """
    return ATTRIBUTE_COLORS.get(attribute, DEFAULT_ATTRIBUTE_COLOR)


def _build_figure(entries: list[dict[str, Any]], toggled_attributes: list[str]) -> go.Figure:
    """Build a Plotly Figure with one line per toggled-on attribute (FR-009-FR-012).

    Args:
        entries: Raw `entries` from a TimeSeriesResponse (dicts with `date` plus
            one key per requested attribute) — plotted verbatim, no calculation.
        toggled_attributes: Attribute names to plot as their own line, in order.

    Returns:
        A styled Figure: one go.Scatter trace per attribute, a horizontal legend
        below the plot, GBP-formatted y-axis, and a per-point hover template
        showing date/metric/value.
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
                hovertemplate="%{x|%Y-%m-%d}<br>" + attribute + ": £%{y:,.2f}<extra></extra>",
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
            "title": "GBP",
            "tickprefix": "£",
            "tickformat": ",.0f",
            "showgrid": True,
            "gridcolor": "#e6e6e6",
        },
    )
    return fig
