"""Pure, side-effect-free helpers for the Overview page's chart (FR-003, FR-004, FR-009-FR-012).

Kept out of overview.py deliberately: overview.py calls `dash.register_page()`
at import time, which raises unless a Dash app has already been instantiated —
that makes overview.py unsafe to import from a plain unit test. These
functions have no such dependency, so they live here and overview.py imports
them for use in its layout/callbacks (see research.md #8 for the underlying
"purely presentational transform" rationale).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import plotly.graph_objects as go

from src.models.portfolio_analysis import AccountSummary

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

_WEEKDAY_MONDAY = 0
_WEEKDAY_SATURDAY = 5
_WEEKDAY_SUNDAY = 6

# Reporting Period Shortcut codes (017; data-model.md's "Reporting Period
# Shortcut" entity). Fixed, spec-defined set — not user-configurable.
SHORTCUT_YTD = "ytd"
SHORTCUT_1Y = "1y"
SHORTCUT_3Y = "3y"
SHORTCUT_5Y = "5y"
SHORTCUT_ALL = "all"
_SHORTCUT_YEAR_OFFSETS = {SHORTCUT_1Y: 1, SHORTCUT_3Y: 3, SHORTCUT_5Y: 5}


def _color_for(attribute: str) -> str:
    """Return the fixed color for an attribute, falling back to a default.

    Args:
        attribute: The wire-format attribute name (e.g. "market_value").

    Returns:
        A hex color string, stable across calls for the same attribute.
    """
    return ATTRIBUTE_COLORS.get(attribute, DEFAULT_ATTRIBUTE_COLOR)


def _last_business_day(today: date) -> date:
    """Return the most recently completed business day before `today` (FR-004).

    Standard Monday-Friday definition, no public-holiday calendar (spec
    Assumptions).

    Args:
        today: The reference "today" date.

    Returns:
        The most recent weekday strictly before `today`.
    """
    candidate = today - timedelta(days=1)
    while candidate.weekday() in (_WEEKDAY_SATURDAY, _WEEKDAY_SUNDAY):
        candidate -= timedelta(days=1)
    return candidate


def _earliest_from_date(account: AccountSummary) -> date:
    """Return the earliest `from_date` across an account's ingested resources (FR-003).

    Args:
        account: The selected account summary.

    Returns:
        The minimum `from_date` of whichever of `capital_ledger`/`position_ladder`
        is present (never both `None` per the API's own contract).
    """
    candidates = [
        r.from_date for r in (account.capital_ledger, account.position_ladder) if r is not None
    ]
    return min(candidates)


def _years_before(today: date, years: int) -> date:
    """Return the exact calendar-date offset `years` before `today`.

    Args:
        today: The reference date.
        years: Number of years to subtract.

    Returns:
        `today` with `years` subtracted from the year, falling back to 28
        February when `today` is a leap day (29 Feb) and the target year
        is not itself a leap year.
    """
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def _shortcut_from_date(code: str, account: AccountSummary, today: date) -> date:
    """Compute (and clamp) a Reporting Period Shortcut's "from" date (FR-002-FR-006, FR-008).

    Args:
        code: One of `SHORTCUT_YTD`, `SHORTCUT_1Y`, `SHORTCUT_3Y`, `SHORTCUT_5Y`,
            `SHORTCUT_ALL`.
        account: The currently selected account (for the clamp floor and
            `SHORTCUT_ALL`'s own value).
        today: The reference "today" date.

    Returns:
        The computed date, never earlier than `account`'s own
        `_earliest_from_date` (FR-008) — a no-op clamp for `SHORTCUT_ALL`,
        since that *is* the earliest date already.

    Raises:
        ValueError: `code` is not one of the five known shortcut codes.
    """
    earliest = _earliest_from_date(account)
    if code == SHORTCUT_ALL:
        return earliest
    if code == SHORTCUT_YTD:
        computed = date(today.year, 1, 1)
    elif code in _SHORTCUT_YEAR_OFFSETS:
        computed = _years_before(today, _SHORTCUT_YEAR_OFFSETS[code])
    else:
        raise ValueError(f"Unknown shortcut code: {code!r}")
    return max(computed, earliest)


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
