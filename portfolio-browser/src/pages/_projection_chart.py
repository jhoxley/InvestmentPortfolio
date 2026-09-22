"""Pure, side-effect-free helpers for the Projection page's chart (022).

Mirrors `_performance_chart.py`'s own structure and separation-of-concerns
rationale, but plots `market_value` (a currency figure) grouped by *series
label* — one trace per distinct `position` value in the response, where
`"Historical"` is the account's real history and every other label is a
requested return's projected line (specs/022-projection-page/research.md
#1). The historical trace is drawn solid; every projected trace is drawn
dashed, so the two categories are visually distinguishable even before
reading the legend (FR-011).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import plotly.graph_objects as go


def _years_after(start: date, years: int) -> date:
    """Return the exact calendar-date offset `years` after `start` (FR-004).

    Mirrors `src/components/date_range_controls._years_before`'s leap-day
    handling, forward instead of backward. Lives here (not in `projection.py`)
    so it stays importable from a plain unit test without triggering that
    module's `dash.register_page()` call, mirroring why this module exists
    at all (see the module docstring).

    Args:
        start: The reference date.
        years: Number of years to add.

    Returns:
        `start` with `years` added to the year, falling back to 28 February
        when `start` is a leap day (29 Feb) and the target year is not
        itself a leap year.
    """
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)

HISTORICAL_SERIES_LABEL = "Historical"

# Fixed, stable series-label -> color mapping. "Ann. ITD"/"1Y"/"3Y"/"5Y" reuse
# _performance_chart.py's own palette for the three shared keys so the same
# return reads as the same color on both pages; "Ann. ITD" gets its own entry
# since Performance's own palette keys that concept "ITD (Ann.)" instead
# (research.md #5 — same calculation, different display label on this page).
PROJECTION_SERIES_COLORS: dict[str, str] = {
    HISTORICAL_SERIES_LABEL: "#1f77b4",
    "Ann. ITD": "#2ca02c",
    "1Y": "#d62728",
    "3Y": "#ff7f0e",
    "5Y": "#9467bd",
}
DEFAULT_PROJECTION_SERIES_COLOR = "#7f7f7f"


def _color_for(series_label: str) -> str:
    """Return the fixed color for a series label, falling back to a default.

    Args:
        series_label: `"Historical"` or a requested return's display label.

    Returns:
        A hex color string, stable across calls for the same label.
    """
    return PROJECTION_SERIES_COLORS.get(series_label, DEFAULT_PROJECTION_SERIES_COLOR)


def _series_labels_in_order(entries: list[dict[str, Any]]) -> list[str]:
    """Return every distinct `position` (series label) present, Historical first.

    Args:
        entries: Raw `entries` from a projection `PositionTimeSeriesResponse`.

    Returns:
        `"Historical"` first (if present), then every other label in first-
        seen order — so trace order (and therefore legend order and z-order)
        is deterministic regardless of the response's own row ordering.
    """
    seen: list[str] = []
    for entry in entries:
        label = entry["position"]
        if label not in seen:
            seen.append(label)
    if HISTORICAL_SERIES_LABEL in seen:
        seen.remove(HISTORICAL_SERIES_LABEL)
        seen.insert(0, HISTORICAL_SERIES_LABEL)
    return seen


def _build_figure(entries: list[dict[str, Any]]) -> go.Figure:
    """Build a Plotly Figure with one line per distinct series label present.

    Args:
        entries: Raw `entries` from a projection `PositionTimeSeriesResponse`
            — plotted verbatim, no calculation (Principle I). Grouped by
            `position` (the series label); each group's `date`/`market_value`
            pairs become one trace.

    Returns:
        A styled Figure: one `go.Scatter` trace per series label (solid for
        `"Historical"`, dashed for every projected return), a horizontal
        legend below the plot, currency-formatted y-axis, and a per-point
        hover template showing date/series/value.
    """
    fig = go.Figure()
    for label in _series_labels_in_order(entries):
        series_entries = [e for e in entries if e["position"] == label]
        is_historical = label == HISTORICAL_SERIES_LABEL
        fig.add_trace(
            go.Scatter(
                x=[e["date"] for e in series_entries],
                y=[e.get("market_value") for e in series_entries],
                mode="lines+markers",
                name=label,
                line={
                    "color": _color_for(label),
                    "width": 3,
                    "dash": "solid" if is_historical else "dash",
                },
                hovertemplate="%{x|%Y-%m-%d}<br>" + label + ": £%{y:,.2f}<extra></extra>",
            )
        )
    fig.update_layout(
        title={"text": "Portfolio Value Projection", "font": {"size": 20}},
        template="plotly_white",
        font={"family": "Helvetica, Arial, sans-serif"},
        legend={"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
        hovermode="x unified",
        margin={"l": 60, "r": 30, "t": 60, "b": 80},
        xaxis={"title": "Date", "showgrid": True, "gridcolor": "#e6e6e6"},
        yaxis={
            "title": "Market Value (£)",
            "tickformat": ",.0f",
            "showgrid": True,
            "gridcolor": "#e6e6e6",
        },
    )
    return fig
