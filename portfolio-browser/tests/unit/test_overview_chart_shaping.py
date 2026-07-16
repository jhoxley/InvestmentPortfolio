"""Unit tests for the pure date/chart-shaping helpers in src/pages/overview.py.

No Dash app / browser required — these are plain functions taking/returning
dates, dicts, and plotly.graph_objects.Figure objects.
"""

from __future__ import annotations

from datetime import date

from src.models.portfolio_analysis import AccountResourceRange, AccountSummary
from src.pages._overview_chart import (
    ATTRIBUTE_COLORS,
    DEFAULT_ATTRIBUTE_COLOR,
    _build_figure,
    _color_for,
    _earliest_from_date,
    _last_business_day,
)


def test_last_business_day_from_monday_is_previous_friday() -> None:
    # 2024-01-08 is a Monday; 2024-01-05 is the preceding Friday.
    assert _last_business_day(date(2024, 1, 8)) == date(2024, 1, 5)


def test_last_business_day_from_tuesday_is_monday() -> None:
    assert _last_business_day(date(2024, 1, 9)) == date(2024, 1, 8)


def test_last_business_day_from_saturday_is_friday() -> None:
    assert _last_business_day(date(2024, 1, 6)) == date(2024, 1, 5)


def test_last_business_day_from_sunday_is_friday() -> None:
    assert _last_business_day(date(2024, 1, 7)) == date(2024, 1, 5)


def test_earliest_from_date_uses_min_of_both_ranges() -> None:
    account = AccountSummary(
        account_name="HL-SIPP",
        capital_ledger=AccountResourceRange(
            from_date=date(2016, 4, 20), to_date=date(2026, 6, 1)
        ),
        position_ladder=AccountResourceRange(
            from_date=date(2015, 1, 1), to_date=date(2026, 7, 8)
        ),
    )
    assert _earliest_from_date(account) == date(2015, 1, 1)


def test_earliest_from_date_with_only_capital_ledger() -> None:
    account = AccountSummary(
        account_name="capital-only-portfolio",
        capital_ledger=AccountResourceRange(
            from_date=date(2020, 1, 2), to_date=date(2020, 6, 1)
        ),
        position_ladder=None,
    )
    assert _earliest_from_date(account) == date(2020, 1, 2)


def test_earliest_from_date_with_only_position_ladder() -> None:
    account = AccountSummary(
        account_name="ladder-only-portfolio",
        capital_ledger=None,
        position_ladder=AccountResourceRange(
            from_date=date(2019, 3, 4), to_date=date(2020, 6, 1)
        ),
    )
    assert _earliest_from_date(account) == date(2019, 3, 4)


def test_color_for_known_attribute_is_stable() -> None:
    first = _color_for("market_value")
    second = _color_for("market_value")
    assert first == second == ATTRIBUTE_COLORS["market_value"]


def test_color_for_unknown_attribute_falls_back_to_default() -> None:
    assert _color_for("some_future_attribute") == DEFAULT_ATTRIBUTE_COLOR


_ENTRIES = [
    {"date": date(2024, 1, 2), "market_value": 240120.11, "capital": 236634.5},
    {"date": date(2024, 1, 3), "market_value": 241000.0, "capital": 236634.5},
]


def test_build_figure_one_toggled_metric_produces_one_trace() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"])

    assert len(fig.data) == 1
    trace = fig.data[0]
    assert trace.name == "market_value"
    assert list(trace.x) == [date(2024, 1, 2), date(2024, 1, 3)]
    assert list(trace.y) == [240120.11, 241000.0]
    assert trace.line.color == ATTRIBUTE_COLORS["market_value"]


def test_build_figure_multiple_toggled_metrics_produce_distinct_colors() -> None:
    fig = _build_figure(_ENTRIES, ["market_value", "capital"])

    assert len(fig.data) == 2
    colors = {trace.name: trace.line.color for trace in fig.data}
    assert colors["market_value"] != colors["capital"]


def test_build_figure_legend_positioned_below_plot() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"])

    assert fig.layout.legend.orientation == "h"
    assert fig.layout.legend.y < 0


def test_build_figure_yaxis_is_gbp_formatted() -> None:
    fig = _build_figure(_ENTRIES, ["market_value"])

    assert fig.layout.yaxis.tickprefix == "£"
