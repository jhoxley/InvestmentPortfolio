"""Pure, side-effect-free helpers for the Positions page's chart and table
(FR-007, FR-008, FR-008a, FR-015-FR-019, FR-025).

Kept out of positions.py deliberately, mirroring _overview_chart.py:
positions.py calls `dash.register_page()` at import time, which raises
unless a Dash app has already been instantiated — that makes positions.py
unsafe to import from a plain unit test. These functions have no such
dependency.
"""

from __future__ import annotations

import colorsys
import hashlib
from datetime import date
from typing import Any

import plotly.graph_objects as go
from dash import dash_table

_PALETTE_SIZE = 50
_MISSING_VALUE_DISPLAY = "—"  # em dash

# Attribute-aware value formatting (FR-008a, research.md #6a). `quantity` is
# a share count, not a currency value; every other currently known Positions
# attribute (market_value, income, book_cost, pnl, close_price) is monetary.
# Currency is the fallback for any attribute not in this set, matching
# _overview_chart.py's ATTRIBUTE_COLORS/DEFAULT_ATTRIBUTE_COLOR
# fixed-mapping-with-default shape.
_PLAIN_NUMERIC_ATTRIBUTES = frozenset({"quantity"})


def _format_attribute_value(attribute_name: str, value: float) -> str:
    """Format a numeric attribute value for display (FR-008a).

    Args:
        attribute_name: The wire-format attribute name (e.g. "market_value").
        value: The raw numeric value to format.

    Returns:
        `"£1,234.50"`-style for monetary attributes; `"25.00"`-style (no
        currency symbol) for `quantity`.
    """
    if attribute_name in _PLAIN_NUMERIC_ATTRIBUTES:
        return f"{value:,.2f}"
    return f"£{value:,.2f}"


def _generate_palette(size: int) -> list[str]:
    """Pre-generate `size` high-contrast colors evenly spaced around the HSL hue wheel.

    Args:
        size: Number of colors to generate.

    Returns:
        A list of hex color strings, in a fixed order determined purely by
        `size` (no randomness) — index `i` is always the same color for a
        given `size`.
    """
    colors = []
    for i in range(size):
        hue = i / size
        # Alternate lightness between two bands so adjacent hue-steps don't
        # read as near-identical (research.md #5).
        lightness = 0.42 if i % 2 == 0 else 0.62
        saturation = 0.65
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        colors.append(f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}")
    return colors


_PALETTE = _generate_palette(_PALETTE_SIZE)


def _color_for_position(position_name: str) -> str:
    """Return a stable, deterministic color for a position name (FR-015).

    Uses `hashlib.sha256` (not Python's built-in `hash()`, which is salted
    per-process and therefore not stable across process restarts) modulo
    the pre-generated palette size, so the same position always maps to the
    same color regardless of process, selection, or date range
    (`/speckit-clarify` Q3).

    Args:
        position_name: The position's display name.

    Returns:
        A hex color string from the pre-generated palette.
    """
    digest = hashlib.sha256(position_name.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % _PALETTE_SIZE
    return _PALETTE[index]


def _hover_value_format(attribute: str) -> str:
    """Return the plotly hovertemplate fragment for one attribute's value (FR-008a).

    Args:
        attribute: The wire-format attribute name.

    Returns:
        `"£%{y:,.2f}"` for monetary attributes, `"%{y:,.2f}"` for `quantity`.
    """
    if attribute in _PLAIN_NUMERIC_ATTRIBUTES:
        return "%{y:,.2f}"
    return "£%{y:,.2f}"


def _trace_name(position: str, attribute: str, multi_attribute: bool) -> str:
    """Return a trace's legend/hover name (FR-016a).

    Args:
        position: The position this trace belongs to.
        attribute: The attribute this trace plots.
        multi_attribute: Whether more than one attribute is currently
            selected — triggers the "Position — Attribute" dual label
            regardless of how many positions are selected (corrected scope,
            `/speckit-analyze` U1 fix).

    Returns:
        `"{position} — {attribute}"` when `multi_attribute`, else just
        `position`.
    """
    if multi_attribute:
        return f"{position} — {attribute}"
    return position


def _build_figure(
    entries: list[dict[str, Any]], attributes: list[str], stacked: bool
) -> go.Figure:
    """Build a Plotly Figure with one line per (position, attribute) pair (FR-007, FR-008).

    Args:
        entries: Raw per-position `entries` from a PositionTimeSeriesResponse
            (dicts with `date`, `position`, plus one key per requested
            attribute) — plotted verbatim, no calculation. Only positions
            present here are plotted (FR-025's exclusion is inherent: a
            position with zero entries simply never appears).
        attributes: Attribute names to plot, in order.
        stacked: When `True`, render as a stacked area chart (`stackgroup`);
            when `False`, render as a line chart — matches the Overview
            page's own line-chart style, subject to FR-008a formatting.

    Returns:
        A styled Figure: one `go.Scatter` trace per (position, attribute)
        pair, colored by position (FR-015), with a dual "Position —
        Attribute" label whenever more than one attribute is selected
        (FR-016a).
    """
    positions = sorted({entry["position"] for entry in entries})
    multi_attribute = len(attributes) > 1

    fig = go.Figure()
    for attribute in attributes:
        for position in positions:
            rows = [e for e in entries if e["position"] == position and attribute in e]
            dates = [row["date"] for row in rows]
            values = [row[attribute] for row in rows]
            name = _trace_name(position, attribute, multi_attribute)
            color = _color_for_position(position)
            trace_kwargs: dict[str, Any] = {
                "x": dates,
                "y": values,
                "name": name,
                "line": {"color": color, "width": 3},
                "hovertemplate": (
                    "%{x|%Y-%m-%d}<br>"
                    + name
                    + ": "
                    + _hover_value_format(attribute)
                    + "<extra></extra>"
                ),
            }
            if stacked:
                trace_kwargs["mode"] = "lines"
                trace_kwargs["stackgroup"] = "positions"
            else:
                trace_kwargs["mode"] = "lines+markers"
            fig.add_trace(go.Scatter(**trace_kwargs))

    # A shared y-axis can only sensibly show one unit's formatting; fall back
    # to plain numeric ticks unless every selected attribute is monetary
    # (FR-008a) — a per-trace hover template always shows the correct
    # per-attribute unit regardless of the axis' own formatting.
    all_monetary = all(a not in _PLAIN_NUMERIC_ATTRIBUTES for a in attributes)
    yaxis: dict[str, Any] = {"showgrid": True, "gridcolor": "#e6e6e6"}
    if all_monetary:
        yaxis.update({"title": "GBP", "tickprefix": "£", "tickformat": ",.0f"})
    else:
        yaxis.update({"title": "Value", "tickformat": ",.0f"})

    fig.update_layout(
        title={"text": "Position Performance", "font": {"size": 20}},
        template="plotly_white",
        font={"family": "Helvetica, Arial, sans-serif"},
        legend={"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
        hovermode="x unified",
        margin={"l": 60, "r": 30, "t": 60, "b": 80},
        xaxis={"title": "Date", "showgrid": True, "gridcolor": "#e6e6e6"},
        yaxis=yaxis,
    )
    return fig


def _shading_for(to_value: float | None, from_value: float | None) -> str:
    """Return the up/down/flat shading category for a to/from value pair (FR-019).

    Args:
        to_value: The value on the "To" date, or `None` if absent.
        from_value: The value on the "From" date, or `None` if absent.

    Returns:
        `"up"` if `to_value > from_value`, `"down"` if `<`, `"flat"` if
        equal or if either value is absent (no meaningful comparison).
    """
    if to_value is None or from_value is None:
        return "flat"
    if to_value > from_value:
        return "up"
    if to_value < from_value:
        return "down"
    return "flat"


def _build_comparison_rows(
    entries: list[dict[str, Any]],
    attributes: list[str],
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    """Derive one comparison-table row per position with data (FR-017-FR-019, FR-025).

    A purely presentational transform (constitution Principle I's
    carve-out) — every value is read verbatim from `entries`, not computed
    from raw transaction/price data.

    Args:
        entries: Raw per-position `entries` from a PositionTimeSeriesResponse.
        attributes: Currently selected attribute names, in order.
        from_date: The query's resolved "From" date.
        to_date: The query's resolved "To" date.

    Returns:
        One dict per position present in `entries` (FR-025's exclusion is
        inherent), each with `"position"`, and per attribute:
        `"{attribute}"` / `"{attribute}_prev"` (formatted display strings,
        `"—"` if the value is absent for that date) and
        `"_{attribute}_shading"` (`"up"`/`"down"`/`"flat"`, computed from
        the *unformatted* numeric values).
    """
    positions = sorted({entry["position"] for entry in entries})
    rows: list[dict[str, Any]] = []
    for position in positions:
        row: dict[str, Any] = {"position": position}
        for attribute in attributes:
            to_value = next(
                (
                    e[attribute]
                    for e in entries
                    if e["position"] == position and e["date"] == to_date and attribute in e
                ),
                None,
            )
            from_value = next(
                (
                    e[attribute]
                    for e in entries
                    if e["position"] == position and e["date"] == from_date and attribute in e
                ),
                None,
            )
            row[attribute] = (
                _format_attribute_value(attribute, to_value)
                if to_value is not None
                else _MISSING_VALUE_DISPLAY
            )
            row[f"{attribute}_prev"] = (
                _format_attribute_value(attribute, from_value)
                if from_value is not None
                else _MISSING_VALUE_DISPLAY
            )
            row[f"_{attribute}_shading"] = _shading_for(to_value, from_value)
        rows.append(row)
    return rows


_SHADING_COLORS = {
    "up": "#d4f4dd",  # pastel light green
    "down": "#fbdada",  # pastel light red
}


def _build_comparison_table(
    entries: list[dict[str, Any]],
    attributes: list[str],
    from_date: date,
    to_date: date,
) -> Any:
    """Build the comparison table component (FR-017-FR-019).

    Returns `Any` rather than `dash_table.DataTable`: Dash's own generated
    component module shadows the class name with an identically-named
    submodule (`dash.dash_table.DataTable`), which mypy resolves as a
    module rather than a type — a known Dash/mypy interaction, not specific
    to this function.

    Args:
        entries: Raw per-position `entries` from a PositionTimeSeriesResponse.
        attributes: Currently selected attribute names, in order.
        from_date: The query's resolved "From" date.
        to_date: The query's resolved "To" date.

    Returns:
        A `dash_table.DataTable` with one column pair per attribute (current
        value + `"{attribute} (prev)"`) and `style_data_conditional` shading
        the current-value column light green/light red per FR-019 (left
        unshaded when the shading category is `"flat"`).
    """
    rows = _build_comparison_rows(entries, attributes, from_date, to_date)

    columns = [{"name": "Position", "id": "position"}]
    for attribute in attributes:
        columns.append({"name": attribute, "id": attribute})
        columns.append({"name": f"{attribute} (prev)", "id": f"{attribute}_prev"})

    style_data_conditional: list[dict[str, Any]] = []
    for attribute in attributes:
        for category, color in _SHADING_COLORS.items():
            style_data_conditional.append(
                {
                    "if": {
                        "filter_query": f"{{_{attribute}_shading}} = {category!r}",
                        "column_id": attribute,
                    },
                    "backgroundColor": color,
                }
            )

    return dash_table.DataTable(  # type: ignore[attr-defined]
        id="positions-comparison-table",
        columns=columns,
        data=rows,
        style_data_conditional=style_data_conditional,
        style_cell={"textAlign": "right", "padding": "6px"},
        style_cell_conditional=[{"if": {"column_id": "position"}, "textAlign": "left"}],
        style_header={"fontWeight": "bold"},
    )
