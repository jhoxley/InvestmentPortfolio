"""Unit tests for the pure pie/ranking/gradient/table-shaping helpers in
src/pages/_overview_position_widgets.py.

No Dash app / browser required — these are plain functions taking/returning
dicts, plotly.graph_objects.Figure objects, and dash_table.DataTable objects.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.pages._overview_position_widgets import (
    _build_pie_figure,
    _build_winners_losers_table,
    _gradient_color,
    _rank_positions,
)

# --- Pie chart shaping (FR-002, FR-002a, FR-012) -----------------------------


def test_build_pie_figure_one_slice_per_position() -> None:
    entries = [
        {"position": "Apple Inc", "market_value": 700.0},
        {"position": "Cash", "market_value": 300.0},
    ]
    fig = _build_pie_figure(entries)

    assert len(fig.data) == 1
    pie = fig.data[0]
    assert set(pie.labels) == {"Apple Inc", "Cash"}
    assert sum(pie.values) == 1000.0


def test_build_pie_figure_excludes_non_positive_or_missing_market_value() -> None:
    entries: list[dict[str, Any]] = [
        {"position": "Apple Inc", "market_value": 700.0},
        {"position": "Zero Corp", "market_value": 0.0},
        {"position": "Negative Corp", "market_value": -50.0},
        {"position": "No Data Corp"},
    ]
    fig = _build_pie_figure(entries)

    pie = fig.data[0]
    assert set(pie.labels) == {"Apple Inc"}


def test_build_pie_figure_has_no_on_slice_text() -> None:
    """No callout labels on the slices themselves (crowds the chart with

    long position names) — identification is via hover + the legend's
    color-to-name mapping only.
    """
    entries = [
        {"position": "Big Holding", "market_value": 950.0},
        {"position": "Small Holding", "market_value": 50.0},
    ]
    fig = _build_pie_figure(entries)
    pie = fig.data[0]

    assert pie.textinfo == "none"


def test_build_pie_figure_legend_is_vertical_below_the_chart() -> None:
    entries = [
        {"position": "Big Holding", "market_value": 950.0},
        {"position": "Small Holding", "market_value": 50.0},
    ]
    fig = _build_pie_figure(entries)

    assert fig.layout.legend.orientation == "v"
    assert fig.layout.legend.x == 0.5
    assert fig.layout.legend.xanchor == "center"
    # Positioned below the pie's own domain, not to the right of it.
    assert fig.layout.legend.y < fig.data[0].domain.y[0] + 0.05


def test_build_pie_figure_height_grows_with_position_count() -> None:
    few_entries = [{"position": f"P{i}", "market_value": 10.0} for i in range(3)]
    many_entries = [{"position": f"P{i}", "market_value": 10.0} for i in range(30)]

    few_fig = _build_pie_figure(few_entries)
    many_fig = _build_pie_figure(many_entries)

    assert many_fig.layout.height > few_fig.layout.height


def test_build_pie_figure_pie_domain_height_is_constant_regardless_of_position_count() -> None:
    """The pie itself never shrinks to make room for a long legend — only

    the figure's total height (and therefore the legend's own space) grows.
    """
    few_entries = [{"position": f"P{i}", "market_value": 10.0} for i in range(3)]
    many_entries = [{"position": f"P{i}", "market_value": 10.0} for i in range(30)]

    few_fig = _build_pie_figure(few_entries)
    many_fig = _build_pie_figure(many_entries)

    few_pie_px = (1 - few_fig.data[0].domain.y[0]) * few_fig.layout.height
    many_pie_px = (1 - many_fig.data[0].domain.y[0]) * many_fig.layout.height
    assert few_pie_px == pytest.approx(many_pie_px, abs=1.0)


def test_build_pie_figure_hover_includes_name_value_and_percent_for_every_slice() -> None:
    entries = [
        {"position": "Big Holding", "market_value": 980.0},
        {"position": "Tiny Holding", "market_value": 20.0},
    ]
    fig = _build_pie_figure(entries)
    pie = fig.data[0]

    assert "%{label}" in pie.hovertemplate
    assert "%{percent}" in pie.hovertemplate
    assert "%{value" in pie.hovertemplate


def test_build_pie_figure_empty_when_no_qualifying_positions() -> None:
    fig = _build_pie_figure([])
    assert len(fig.data) == 1
    assert list(fig.data[0].labels) == []


# --- Ranking / tie-break / group-split (FR-006, FR-012, FR-013) -------------


def _entries_for(pnls: dict[str, float]) -> list[dict]:
    return [{"position": name, "pnl": pnl} for name, pnl in pnls.items()]


def test_rank_positions_sorts_descending_by_pnl() -> None:
    entries = _entries_for({"A": 10.0, "B": 30.0, "C": 20.0})
    rows = _rank_positions(entries)
    assert [r["position"] for r in rows] == ["B", "C", "A"]


def test_rank_positions_ties_broken_ascending_by_name() -> None:
    entries = _entries_for({"Zeta": 10.0, "Alpha": 10.0, "Mid": 10.0})
    rows = _rank_positions(entries)
    assert [r["position"] for r in rows] == ["Alpha", "Mid", "Zeta"]


def test_rank_positions_excludes_missing_pnl() -> None:
    entries: list[dict[str, Any]] = [
        {"position": "Has Pnl", "pnl": 10.0},
        {"position": "No Pnl"},
    ]
    rows = _rank_positions(entries)
    assert [r["position"] for r in rows] == ["Has Pnl"]


def test_rank_positions_with_10_or_more_splits_top5_bottom5() -> None:
    pnls = {f"P{i}": float(i) for i in range(1, 13)}  # P1..P12, pnl 1..12
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)

    winners = [r for r in rows if r["group"] == "winner"]
    losers = [r for r in rows if r["group"] == "loser"]
    assert len(winners) == 5
    assert len(losers) == 5
    assert [r["position"] for r in winners] == ["P12", "P11", "P10", "P9", "P8"]
    # Bottom 5 by pnl overall (P1..P5), displayed mildest-first (P5), worst-last (P1).
    # P6/P7 are neither top 5 nor bottom 5, so are excluded entirely (only 10 rows total).
    assert [r["position"] for r in losers] == ["P5", "P4", "P3", "P2", "P1"]
    assert len(rows) == 10


def test_rank_positions_fewer_than_10_splits_evenly_no_duplicates() -> None:
    pnls = {f"P{i}": float(i) for i in range(1, 7)}  # 6 positions, pnl 1..6
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)

    assert len(rows) == 6
    winners = [r for r in rows if r["group"] == "winner"]
    losers = [r for r in rows if r["group"] == "loser"]
    assert len(winners) == 3
    assert len(losers) == 3
    all_positions = [r["position"] for r in rows]
    assert len(set(all_positions)) == 6  # no duplicates


def test_rank_positions_odd_leftover_joins_winners() -> None:
    pnls = {f"P{i}": float(i) for i in range(1, 6)}  # 5 positions, pnl 1..5
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)

    winners = [r for r in rows if r["group"] == "winner"]
    losers = [r for r in rows if r["group"] == "loser"]
    assert len(winners) == 3  # ceil(5/2)
    assert len(losers) == 2  # floor(5/2)


def test_rank_positions_single_loser_group_size_one() -> None:
    pnls = {"Winner": 10.0, "Winner2": 5.0, "Loser": -20.0}
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)
    losers = [r for r in rows if r["group"] == "loser"]
    assert len(losers) == 1
    assert losers[0]["position"] == "Loser"


def test_rank_positions_winner_rank_index_counts_from_best() -> None:
    pnls = {f"P{i}": float(i) for i in range(1, 13)}
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)
    winners = [r for r in rows if r["group"] == "winner"]
    # P12 (highest pnl) is the best winner -> rank_index 0.
    winners_by_position = {r["position"]: r["rank_index"] for r in winners}
    assert winners_by_position["P12"] == 0
    assert winners_by_position["P8"] == 4


def test_rank_positions_loser_rank_index_counts_from_worst_n_ge_10() -> None:
    """/speckit-analyze finding G2: a loser's rank_index must be the reverse

    of its display order — the single worst position (P1) always gets
    rank_index 0 (brightest), regardless of display position.
    """
    pnls = {f"P{i}": float(i) for i in range(1, 13)}
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)
    losers = [r for r in rows if r["group"] == "loser"]
    losers_by_position = {r["position"]: r["rank_index"] for r in losers}
    assert losers_by_position["P1"] == 0  # worst overall -> brightest
    assert losers_by_position["P5"] == 4  # mildest of the bottom 5 -> palest


def test_rank_positions_loser_rank_index_counts_from_worst_n_lt_10() -> None:
    """Same reversal must hold when fewer than 5 losers are present."""
    pnls = {f"P{i}": float(i) for i in range(1, 7)}  # 6 positions -> 3 losers
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)
    losers = [r for r in rows if r["group"] == "loser"]
    losers_by_position = {r["position"]: r["rank_index"] for r in losers}
    assert losers_by_position["P1"] == 0  # worst of the 3 losers -> brightest
    assert losers_by_position["P3"] == 2  # mildest of the 3 losers -> palest


def test_rank_positions_single_loser_rank_index_is_zero() -> None:
    """A lone loser is simultaneously mildest and worst — brightest end wins."""
    pnls = {"Winner": 10.0, "Winner2": 5.0, "Loser": -20.0}
    entries = _entries_for(pnls)
    rows = _rank_positions(entries)
    losers = [r for r in rows if r["group"] == "loser"]
    assert losers[0]["rank_index"] == 0


# --- Gradient interpolation (FR-008, FR-013) ---------------------------------

_BRIGHT = "#1e8f3e"
_PALE = "#eaf7ee"


def test_gradient_color_index_zero_is_bright() -> None:
    assert _gradient_color(0, 5, _BRIGHT, _PALE) == _BRIGHT


def test_gradient_color_last_index_is_pale() -> None:
    assert _gradient_color(4, 5, _BRIGHT, _PALE) == _PALE


def test_gradient_color_intermediate_interpolates() -> None:
    color = _gradient_color(2, 5, _BRIGHT, _PALE)
    assert color not in (_BRIGHT, _PALE)


def test_gradient_color_single_row_group_is_bright() -> None:
    assert _gradient_color(0, 1, _BRIGHT, _PALE) == _BRIGHT


# --- Winners/losers table building (FR-005, FR-007, FR-008) -----------------


def test_build_winners_losers_table_columns_and_row_count() -> None:
    pnls = {f"P{i}": float(i) for i in range(1, 13)}
    entries = [
        {"position": name, "pnl": pnl, "book_cost": 100.0} for name, pnl in pnls.items()
    ]
    table = _build_winners_losers_table(entries)

    column_ids = {c["id"] for c in table.columns}
    assert column_ids == {"position", "pnl", "book_cost"}
    assert len(table.data) == 10


def test_build_winners_losers_table_style_conditional_covers_every_row() -> None:
    pnls = {f"P{i}": float(i) for i in range(1, 13)}
    entries = [
        {"position": name, "pnl": pnl, "book_cost": 100.0} for name, pnl in pnls.items()
    ]
    table = _build_winners_losers_table(entries)
    assert len(table.style_data_conditional) == 10
