"""Unit tests for src/pages/_var_backtest_panel.py's pure build_panel() (026, US2; 027 US5)."""

from __future__ import annotations

from dash import dash_table, html

from src.pages._var_backtest_panel import STYLE_CELL, STYLE_HEADER, build_panel


def _level(confidence_bp: int = 9500, observation_count: int = 250, **overrides: object) -> dict:
    base = {
        "confidence_bp": confidence_bp,
        "observation_count": observation_count,
        "exception_count": 6,
        "expected_exceptions": 12.5,
        "exception_rate": 0.024,
        "kupiec_lr": 1.2,
        "kupiec_p_value": 0.27,
        "christoffersen_independence_lr": 0.3,
        "christoffersen_independence_p_value": 0.58,
        "conditional_coverage_lr": 1.5,
        "conditional_coverage_p_value": 0.47,
        "zone": "green",
        "exception_dates": [],
        "mean_var_gbp": 100.0,
        "var_stability": 0.02,
        "rolling_exceptions": None,
    }
    base.update(overrides)
    return base


def _backtest_by_basis_quality(level: dict) -> dict:
    return {
        "hypothetical": {"ok": {"levels": [level]}, "degraded": {"levels": [level]}},
        "ladder": {"ok": {"levels": [level]}, "degraded": {"levels": [level]}},
    }


def _backtest_by_basis_quality_multi(levels: list[dict]) -> dict:
    return {
        "hypothetical": {"ok": {"levels": levels}, "degraded": {"levels": levels}},
        "ladder": {"ok": {"levels": levels}, "degraded": {"levels": levels}},
    }


def _text(component: object) -> str:
    if isinstance(component, str):
        return component
    data = getattr(component, "data", None)
    if data is not None:
        # dash_table.DataTable: its cell values live in `.data` (row dicts), not `.children`.
        return "".join(str(v) for row in data for v in row.values())
    children = getattr(component, "children", None)
    if children is None:
        return ""
    if not isinstance(children, list):
        children = [children]
    return "".join(_text(c) for c in children)


def _find_data_tables(component: object) -> list:
    """Depth-first collect every `dash_table.DataTable` in the component tree."""
    found = []
    if isinstance(component, dash_table.DataTable):
        found.append(component)
    children = getattr(component, "children", None)
    if children is not None:
        if not isinstance(children, list):
            children = [children]
        for child in children:
            found.extend(_find_data_tables(child))
    return found


def test_selects_hypothetical_degraded_by_default() -> None:
    hyp_level = _level(exception_count=6)
    ladder_level = _level(exception_count=99)
    data = {
        "hypothetical": {"ok": {"levels": [hyp_level]}, "degraded": {"levels": [hyp_level]}},
        "ladder": {"ok": {"levels": [ladder_level]}, "degraded": {"levels": [ladder_level]}},
    }
    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    text = _text(panel)
    assert "6" in text
    assert "99" not in text


def test_hide_degraded_selects_the_ok_result() -> None:
    ok_level = _level(exception_count=3)
    degraded_level = _level(exception_count=7)
    data = {
        "hypothetical": {
            "ok": {"levels": [ok_level]},
            "degraded": {"levels": [degraded_level]},
        },
        "ladder": {"ok": {"levels": [ok_level]}, "degraded": {"levels": [degraded_level]}},
    }
    panel_shown = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    panel_hidden = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=True
    )
    assert "7" in _text(panel_shown)
    assert "3" in _text(panel_hidden)


def test_pnl_basis_selects_the_matching_result() -> None:
    hyp_level = _level(exception_count=1)
    ladder_level = _level(exception_count=9)
    data = _backtest_by_basis_quality(hyp_level)
    data["ladder"] = {"ok": {"levels": [ladder_level]}, "degraded": {"levels": [ladder_level]}}

    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="ladder", hide_degraded=False
    )
    assert "9" in _text(panel)


def test_renders_exception_count_expected_pvalues_zone_mean_var_stability() -> None:
    data = _backtest_by_basis_quality(_level())
    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    text = _text(panel)
    for expected in ("6", "12.5", "0.27", "0.47", "Pass", "100", "0.02"):
        assert expected in text


def test_insufficient_observations_shows_not_enough_observations_message() -> None:
    level = _level(
        observation_count=1,
        kupiec_lr=None,
        kupiec_p_value=None,
        christoffersen_independence_lr=None,
        christoffersen_independence_p_value=None,
        conditional_coverage_lr=None,
        conditional_coverage_p_value=None,
        var_stability=None,
        zone=None,
    )
    data = _backtest_by_basis_quality(level)
    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    text = _text(panel)
    assert "not enough observations" in text.lower()


def test_renders_as_data_tables_matching_the_histogram_tables_style() -> None:
    """027 FR-010/SC-005: the panel must present its figures via the same
    `dash_table.DataTable` component type and the same `style_cell`/`style_header`
    dictionaries risk.py's own `risk-statistics-table` uses, not stacked H6/P prose.
    """
    panel = build_panel(
        _backtest_by_basis_quality(_level()),
        selected_confidence_bp=[9500],
        pnl_basis="hypothetical",
        hide_degraded=False,
    )
    tables = _find_data_tables(panel)
    assert len(tables) == 1
    table = tables[0]
    assert table.style_cell == STYLE_CELL
    assert table.style_header == STYLE_HEADER
    assert {col["id"] for col in table.columns} == {"statistic", "level_9500"}


def test_combined_table_has_one_column_per_selected_confidence_level() -> None:
    """028 FR-003: up to three per-level tables become one table with one value column
    per selected confidence level, not one table per level.
    """
    levels = [_level(confidence_bp=9500), _level(confidence_bp=9750), _level(confidence_bp=9900)]
    data = _backtest_by_basis_quality_multi(levels)

    panel = build_panel(
        data,
        selected_confidence_bp=[9500, 9750, 9900],
        pnl_basis="hypothetical",
        hide_degraded=False,
    )

    tables = _find_data_tables(panel)
    assert len(tables) == 1
    table = tables[0]
    assert {col["id"] for col in table.columns} == {
        "statistic",
        "level_9500",
        "level_9750",
        "level_9900",
    }
    assert len(table.data) == 6  # one row per statistic, unchanged from the prior per-level table


def test_combined_table_column_names_are_formatted_confidence_labels() -> None:
    levels = [_level(confidence_bp=9500), _level(confidence_bp=9750)]
    data = _backtest_by_basis_quality_multi(levels)

    panel = build_panel(
        data, selected_confidence_bp=[9500, 9750], pnl_basis="hypothetical", hide_degraded=False
    )

    table = _find_data_tables(panel)[0]
    names_by_id = {col["id"]: col["name"] for col in table.columns}
    assert names_by_id["level_9500"] == "95%"
    assert names_by_id["level_9750"] == "97.5%"


def test_deselecting_a_confidence_level_removes_its_column_only() -> None:
    """028 FR-004: removing a column must not change the remaining columns' values."""
    levels = [
        _level(confidence_bp=9500, exception_count=3),
        _level(confidence_bp=9750, exception_count=5),
        _level(confidence_bp=9900, exception_count=7),
    ]
    data = _backtest_by_basis_quality_multi(levels)

    panel_all = build_panel(
        data,
        selected_confidence_bp=[9500, 9750, 9900],
        pnl_basis="hypothetical",
        hide_degraded=False,
    )
    panel_without_9750 = build_panel(
        data, selected_confidence_bp=[9500, 9900], pnl_basis="hypothetical", hide_degraded=False
    )

    table_all = _find_data_tables(panel_all)[0]
    table_without = _find_data_tables(panel_without_9750)[0]

    assert {col["id"] for col in table_without.columns} == {"statistic", "level_9500", "level_9900"}

    exceptions_row_all = next(r for r in table_all.data if r["statistic"] == "Exceptions")
    exceptions_row_without = next(r for r in table_without.data if r["statistic"] == "Exceptions")
    assert exceptions_row_all["level_9500"] == exceptions_row_without["level_9500"]
    assert exceptions_row_all["level_9900"] == exceptions_row_without["level_9900"]


def test_single_selected_level_still_renders_one_column_table() -> None:
    panel = build_panel(
        _backtest_by_basis_quality(_level()),
        selected_confidence_bp=[9500],
        pnl_basis="hypothetical",
        hide_degraded=False,
    )
    tables = _find_data_tables(panel)
    assert len(tables) == 1
    assert {col["id"] for col in tables[0].columns} == {"statistic", "level_9500"}


def test_returns_a_div() -> None:
    panel = build_panel(
        _backtest_by_basis_quality(_level()),
        selected_confidence_bp=[9500],
        pnl_basis="hypothetical",
        hide_degraded=False,
    )
    assert isinstance(panel, html.Div)
