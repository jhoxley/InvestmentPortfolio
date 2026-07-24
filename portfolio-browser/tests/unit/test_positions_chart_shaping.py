"""Unit tests for the pure chart/table-shaping helpers in src/pages/_positions_chart.py.

No Dash app / browser required — these are plain functions taking/returning
dicts, plotly.graph_objects.Figure objects, and dash_table.DataTable objects.
"""

from __future__ import annotations

import colorsys
from datetime import date

from src.models.portfolio_analysis import PositionTimeSeriesEntry
from src.pages._positions_chart import (
    _build_comparison_rows,
    _build_comparison_table,
    _build_figure,
    _color_for_position,
    _generate_palette,
)

# --- Color assignment (FR-015, /speckit-clarify Q1 & Q3) ---------------------


def test_color_for_position_is_stable_across_repeated_calls() -> None:
    first = _color_for_position("Apple Inc")
    second = _color_for_position("Apple Inc")
    assert first == second


def test_color_for_position_varies_across_distinct_names() -> None:
    names = ["Apple Inc", "Berkshire Hathaway Class B (BRK.B)", "Cash", "Sold Corp", "Zeta Ltd"]
    colors = {_color_for_position(name) for name in names}
    assert len(colors) > 1


def test_generate_palette_has_50_distinct_colors() -> None:
    palette = _generate_palette(50)
    assert len(palette) == 50
    assert len(set(palette)) == 50


def test_generate_palette_colors_have_minimum_hue_separation() -> None:
    palette = _generate_palette(50)
    hues = []
    for hex_color in palette:
        r = int(hex_color[1:3], 16) / 255
        g = int(hex_color[3:5], 16) / 255
        b = int(hex_color[5:7], 16) / 255
        h, _l, _s = colorsys.rgb_to_hls(r, g, b)
        hues.append(h * 360)
    hues.sort()
    gaps = [hues[i + 1] - hues[i] for i in range(len(hues) - 1)]
    gaps.append(360 - hues[-1] + hues[0])  # wrap-around gap
    assert min(gaps) >= 5.0


# --- Figure building (FR-007, FR-008, FR-015, FR-016a) -----------------------

_ENTRIES = [
    {"date": date(2024, 1, 2), "position": "Apple Inc", "market_value": 5000.0, "quantity": 25.0},
    {"date": date(2024, 1, 3), "position": "Apple Inc", "market_value": 5100.0, "quantity": 25.0},
    {"date": date(2024, 1, 2), "position": "Cash", "market_value": 2000.0, "quantity": 2000.0},
    {"date": date(2024, 1, 3), "position": "Cash", "market_value": 2000.0, "quantity": 2000.0},
]


def test_build_figure_line_mode_one_trace_per_position_single_attribute() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"], stacked=False)

    assert len(fig.data) == 2
    names = {trace.name for trace in fig.data}
    assert names == {"Apple Inc", "Cash"}
    for trace in fig.data:
        assert trace.mode == "lines+markers"


def test_build_figure_trace_color_matches_color_for_position() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"], stacked=False)

    for trace in fig.data:
        assert trace.line.color == _color_for_position(trace.name)


def test_build_figure_single_position_multiple_attributes_uses_dual_label() -> None:
    """Regression test for the /speckit-analyze U1 fix: FR-016a must trigger

    whenever more than one attribute is selected, even with only one
    position selected (same color, otherwise indistinguishable lines).
    """
    single_position_entries = [e for e in _ENTRIES if e["position"] == "Apple Inc"]
    fig = _build_figure(single_position_entries, ["market_value", "quantity"], stacked=False)

    assert len(fig.data) == 2
    names = {trace.name for trace in fig.data}
    assert names == {"Apple Inc — market_value", "Apple Inc — quantity"}
    # Same position -> same color for both traces, per FR-015 (color encodes
    # position only) — the dual label is what disambiguates them instead.
    colors = {trace.line.color for trace in fig.data}
    assert len(colors) == 1


def test_build_figure_multiple_positions_single_attribute_uses_plain_label() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"], stacked=False)

    names = {trace.name for trace in fig.data}
    assert names == {"Apple Inc", "Cash"}


def test_build_figure_stacked_mode_uses_shared_stackgroup() -> None:
    single_attribute_entries = _ENTRIES
    fig = _build_figure(single_attribute_entries, ["market_value"], stacked=True)

    assert len(fig.data) == 2
    for trace in fig.data:
        assert trace.stackgroup == "positions"
        assert trace.mode == "lines"


def test_build_figure_hover_uses_attribute_aware_formatting() -> None:
    fig = _build_figure(_ENTRIES, ["quantity"], stacked=False)

    for trace in fig.data:
        assert "£" not in trace.hovertemplate


# --- Comparison table derivation (FR-017-FR-019, FR-025) ---------------------

_COMPARISON_ENTRIES = [
    {"date": date(2024, 1, 2), "position": "Apple Inc", "market_value": 5000.0},
    {"date": date(2024, 1, 10), "position": "Apple Inc", "market_value": 5500.0},
    {"date": date(2024, 1, 2), "position": "Cash", "market_value": 2000.0},
    {"date": date(2024, 1, 10), "position": "Cash", "market_value": 1900.0},
    {"date": date(2024, 1, 2), "position": "Flat Corp", "market_value": 1000.0},
    {"date": date(2024, 1, 10), "position": "Flat Corp", "market_value": 1000.0},
]


def test_comparison_rows_one_row_per_position_with_data() -> None:
    rows = _build_comparison_rows(
        _COMPARISON_ENTRIES, ["market_value"], date(2024, 1, 2), date(2024, 1, 10)
    )
    assert {row["position"] for row in rows} == {"Apple Inc", "Cash", "Flat Corp"}


def test_comparison_rows_shading_up_down_flat() -> None:
    rows = {
        row["position"]: row
        for row in _build_comparison_rows(
            _COMPARISON_ENTRIES, ["market_value"], date(2024, 1, 2), date(2024, 1, 10)
        )
    }
    assert rows["Apple Inc"]["_market_value_shading"] == "up"
    assert rows["Cash"]["_market_value_shading"] == "down"
    assert rows["Flat Corp"]["_market_value_shading"] == "flat"


def test_comparison_rows_formats_values_and_prev_column() -> None:
    rows = {
        row["position"]: row
        for row in _build_comparison_rows(
            _COMPARISON_ENTRIES, ["market_value"], date(2024, 1, 2), date(2024, 1, 10)
        )
    }
    assert rows["Apple Inc"]["market_value"] == "£5,500.00"
    assert rows["Apple Inc"]["market_value_prev"] == "£5,000.00"


def test_comparison_rows_excludes_position_with_no_entries() -> None:
    entries = [*_COMPARISON_ENTRIES]  # "Sold Corp" is never present in entries
    rows = _build_comparison_rows(entries, ["market_value"], date(2024, 1, 2), date(2024, 1, 10))
    assert "Sold Corp" not in {row["position"] for row in rows}


def test_build_comparison_table_returns_data_table_with_style_conditional() -> None:
    table = _build_comparison_table(
        _COMPARISON_ENTRIES, ["market_value"], date(2024, 1, 2), date(2024, 1, 10)
    )
    column_ids = {c["id"] for c in table.columns}
    assert column_ids == {"position", "market_value", "market_value_prev"}
    assert len(table.data) == 3
    assert len(table.style_data_conditional) >= 2


def test_comparison_rows_match_dates_from_real_model_dump() -> None:
    """Regression test: positions.py must pass `entries` built via
    `PositionTimeSeriesEntry.model_dump()` (python mode), not
    `model_dump(mode="json")` — the latter serializes `date` to an ISO
    *string*, which silently never equals the `datetime.date`
    `from_date`/`to_date` this function compares against, making every
    value read as absent (reported bug: table always showed "-").
    """
    from_date = date(2024, 1, 2)
    to_date = date(2024, 1, 10)
    entries = [
        PositionTimeSeriesEntry.model_validate(
            {"date": from_date, "position": "Apple Inc", "market_value": 5000.0}
        ).model_dump(),
        PositionTimeSeriesEntry.model_validate(
            {"date": to_date, "position": "Apple Inc", "market_value": 5500.0}
        ).model_dump(),
    ]

    rows = _build_comparison_rows(entries, ["market_value"], from_date, to_date)

    assert rows[0]["market_value"] == "£5,500.00"
    assert rows[0]["market_value_prev"] == "£5,000.00"
    assert rows[0]["_market_value_shading"] == "up"


def test_comparison_rows_do_not_match_json_mode_dump_dates() -> None:
    """Documents the exact failure mode the bug produced, so a future

    accidental reintroduction of `model_dump(mode="json")` in the caller is
    caught here rather than only visible as "-" in a running app.
    """
    from_date = date(2024, 1, 2)
    to_date = date(2024, 1, 10)
    entries = [
        PositionTimeSeriesEntry.model_validate(
            {"date": from_date, "position": "Apple Inc", "market_value": 5000.0}
        ).model_dump(mode="json"),
        PositionTimeSeriesEntry.model_validate(
            {"date": to_date, "position": "Apple Inc", "market_value": 5500.0}
        ).model_dump(mode="json"),
    ]

    rows = _build_comparison_rows(entries, ["market_value"], from_date, to_date)

    # This is the bug's exact symptom — asserted here so the fix (caller
    # using plain `model_dump()`) doesn't silently regress.
    assert rows[0]["market_value"] == "—"
    assert rows[0]["market_value_prev"] == "—"
