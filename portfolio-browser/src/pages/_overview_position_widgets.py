"""Pure, side-effect-free helpers for Overview's two new position
visualizations (FR-002, FR-002a, FR-005-FR-008, FR-012, FR-013).

Kept out of overview.py deliberately, mirroring _overview_chart.py and
_positions_chart.py: overview.py calls `dash.register_page()` at import
time, which raises unless a Dash app has already been instantiated — that
makes overview.py unsafe to import from a plain unit test. These functions
have no such dependency.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from dash import dash_table

from src.components.value_formatting import _format_attribute_value

# Gradient endpoints (FR-008). Specific shades are a visual-design detail
# (spec Assumptions) — these satisfy the described ordinal behavior
# (brightest winner -> palest winner, palest loser -> brightest loser).
_WINNER_BRIGHT = "#1e8f3e"
_WINNER_PALE = "#eaf7ee"
_LOSER_PALE = "#eaf1fb"
_LOSER_BRIGHT = "#1c5fc9"

_MAX_PER_GROUP = 5

# Pie layout: on-slice callout labels were dropped (crowded the chart with
# long position names, per user report after 019 shipped) in favor of a
# vertical legend below the chart, sized to the number of positions so it
# never overlaps/shrinks the pie itself regardless of how many positions an
# account holds.
_PIE_AREA_HEIGHT = 320  # px reserved for the pie itself, fixed regardless of legend size
_LEGEND_ROW_HEIGHT = 22  # px per legend entry (one position per row)
_MIN_FIGURE_HEIGHT = 380


def _build_pie_figure(entries: list[dict[str, Any]]) -> go.Figure:
    """Build a pie chart of position weights by market value (FR-002).

    Args:
        entries: Single-date per-position entries (dicts with `position`
            and `market_value`) from a PositionTimeSeriesResponse. A
            position with a missing, zero, or negative `market_value` is
            excluded (FR-012) — a non-positive share cannot be meaningfully
            drawn as a slice of a whole.

    Returns:
        A `go.Figure` with one `go.Pie` trace, no on-slice text (a hover
        tooltip showing the exact position name, market value, and
        percentage — plus the legend's color-to-name mapping — are
        sufficient to identify a slice without crowding the chart with
        callout labels for potentially dozens of long position names). The
        legend is a vertical list positioned below the pie (not to the
        right, where it would cover half the chart), and the figure's own
        height grows with the number of positions so the legend always has
        room without shrinking the pie.
    """
    qualifying = [
        (e["position"], e["market_value"])
        for e in entries
        if e.get("market_value") is not None and e["market_value"] > 0
    ]
    labels = [position for position, _ in qualifying]
    values = [value for _, value in qualifying]

    figure_height = max(
        _MIN_FIGURE_HEIGHT, _PIE_AREA_HEIGHT + len(labels) * _LEGEND_ROW_HEIGHT
    )
    pie_fraction = _PIE_AREA_HEIGHT / figure_height

    pie = go.Pie(
        labels=labels,
        values=values,
        textinfo="none",
        hovertemplate="%{label}<br>Market value: £%{value:,.2f}<br>%{percent}<extra></extra>",
        domain={"y": [1 - pie_fraction, 1]},
    )
    fig = go.Figure(data=[pie])
    fig.update_layout(
        title={"text": "Position Weights", "font": {"size": 18}},
        template="plotly_white",
        font={"family": "Helvetica, Arial, sans-serif"},
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        legend={
            "orientation": "v",
            "y": 1 - pie_fraction - 0.02,
            "yanchor": "top",
            "x": 0.5,
            "xanchor": "center",
        },
        height=figure_height,
    )
    return fig


def _rank_positions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank positions by profit/loss and split into winner/loser groups (FR-006, FR-012, FR-013).

    Args:
        entries: Single-date per-position entries (dicts with `position`,
            `pnl`, and optionally `book_cost`). A position with no recorded
            `pnl` is excluded (FR-012).

    Returns:
        One dict per included position — at most the 5 highest-`pnl`
        ("winner") and 5 lowest-`pnl` ("loser") when at least 10 qualifying
        positions exist (any positions strictly between those two groups
        are omitted entirely, per FR-006's "highest 5"/"lowest 5", not
        "everything else"); when fewer than 10 qualify, every one appears
        exactly once, split as evenly as possible (an odd leftover joins
        the winners group, FR-013). Each dict holds `position`, `pnl`,
        `book_cost`, `group` (`"winner"`/`"loser"`), and `rank_index` — a
        0-based index counted from each group's "brightest" end: index 0
        is the *best* winner, but index 0 is the *worst* loser (the reverse
        of the losers' own mildest-first display order), so
        `_gradient_color` always anchors the single worst position to the
        brightest shade regardless of how many losers are present.
    """
    qualifying = [e for e in entries if e.get("pnl") is not None]
    ranked = sorted(qualifying, key=lambda e: (-e["pnl"], e["position"]))
    n = len(ranked)

    if n >= 2 * _MAX_PER_GROUP:
        winners = ranked[:_MAX_PER_GROUP]
        losers = ranked[-_MAX_PER_GROUP:]
    else:
        winner_count = -(-n // 2)  # ceil(n / 2)
        winners = ranked[:winner_count]
        losers = ranked[winner_count:]

    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(winners):
        rows.append(
            {
                "position": entry["position"],
                "pnl": entry["pnl"],
                "book_cost": entry.get("book_cost"),
                "group": "winner",
                "rank_index": index,
            }
        )
    loser_count = len(losers)
    for display_index, entry in enumerate(losers):
        rows.append(
            {
                "position": entry["position"],
                "pnl": entry["pnl"],
                "book_cost": entry.get("book_cost"),
                "group": "loser",
                # Reversed vs. display order: the worst loser (last in
                # `losers`, since `losers` stays in descending-pnl order)
                # must get rank_index 0 (brightest) — see docstring.
                "rank_index": loser_count - 1 - display_index,
            }
        )
    return rows


def _gradient_color(index: int, group_size: int, bright_hex: str, pale_hex: str) -> str:
    """Linearly interpolate a row's background color between two endpoints (FR-008, FR-013).

    Args:
        index: 0-based rank within the group (0 = brightest end).
        group_size: Total rows in this group.
        bright_hex: Color for `index == 0`.
        pale_hex: Color for `index == group_size - 1`.

    Returns:
        `bright_hex` when `index == 0` (including the `group_size == 1`
        case — a lone row always reads as the extreme, not a mid-gradient
        shade), `pale_hex` at the opposite end, and a linearly interpolated
        hex color in between.
    """
    if group_size <= 1:
        return bright_hex
    t = index / (group_size - 1)
    bright_rgb = tuple(int(bright_hex[i : i + 2], 16) for i in (1, 3, 5))
    pale_rgb = tuple(int(pale_hex[i : i + 2], 16) for i in (1, 3, 5))
    blended = tuple(round(b + (p - b) * t) for b, p in zip(bright_rgb, pale_rgb, strict=True))
    return f"#{blended[0]:02x}{blended[1]:02x}{blended[2]:02x}"


def _build_winners_losers_table(entries: list[dict[str, Any]]) -> Any:
    """Build the "Biggest winners and losers" table component (FR-005, FR-007, FR-008).

    Returns `Any` rather than `dash_table.DataTable`: see
    `_positions_chart.py::_build_comparison_table`'s docstring for why
    (Dash's own generated component module shadows the class name with an
    identically-named submodule, which mypy resolves as a module rather
    than a type).

    Args:
        entries: Single-date per-position entries (dicts with `position`,
            `pnl`, `book_cost`).

    Returns:
        A `dash_table.DataTable` with `position`/`pnl`/`book_cost` columns
        and one `style_data_conditional` entry per row, mapping each row's
        `rank_index`/`group` to its gradient background color.
    """
    rows = _rank_positions(entries)

    data = [
        {
            "position": row["position"],
            "pnl": _format_attribute_value("pnl", row["pnl"]),
            "book_cost": (
                _format_attribute_value("book_cost", row["book_cost"])
                if row["book_cost"] is not None
                else "—"
            ),
        }
        for row in rows
    ]

    winner_count = sum(1 for row in rows if row["group"] == "winner")
    loser_count = sum(1 for row in rows if row["group"] == "loser")

    style_data_conditional: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        if row["group"] == "winner":
            color = _gradient_color(row["rank_index"], winner_count, _WINNER_BRIGHT, _WINNER_PALE)
        else:
            color = _gradient_color(row["rank_index"], loser_count, _LOSER_BRIGHT, _LOSER_PALE)
        style_data_conditional.append(
            {"if": {"row_index": row_index}, "backgroundColor": color}
        )

    return dash_table.DataTable(  # type: ignore[attr-defined]
        id="overview-winners-losers-table",
        columns=[
            {"name": "Position", "id": "position"},
            {"name": "Profit/Loss", "id": "pnl"},
            {"name": "Book Cost", "id": "book_cost"},
        ],
        data=data,
        style_data_conditional=style_data_conditional,
        style_cell={"textAlign": "right", "padding": "6px"},
        style_cell_conditional=[{"if": {"column_id": "position"}, "textAlign": "left"}],
        style_header={"fontWeight": "bold"},
    )
