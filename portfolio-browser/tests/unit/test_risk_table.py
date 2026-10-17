"""Unit tests for the Risk page's pure statistics table builder (024)."""

from __future__ import annotations

from src.models.portfolio_analysis import HistogramStatistics
from src.pages._risk_table import build_rows

_EXPECTED_ORDER = [
    "count",
    "mean",
    "median",
    "mode",
    "minimum",
    "maximum",
    "std_dev",
    "skewness",
    "kurtosis",
]


def _statistics(**overrides: object) -> HistogramStatistics:
    defaults: dict[str, object] = {
        "count": 27,
        "mean": 4.1,
        "median": 3.0,
        "mode": 0,
        "minimum": -25,
        "maximum": 65,
        "std_dev": 14.2,
        "std_dev_bands": [],
        "skewness": 1.8,
        "kurtosis": 6.2,
    }
    defaults.update(overrides)
    return HistogramStatistics.model_validate(defaults)


def test_build_rows_returns_nine_rows_in_declared_order_no_std_dev_bands() -> None:
    rows = build_rows(_statistics())

    assert len(rows) == 9
    assert [row["statistic"] for row in rows] == [
        "Count",
        "Mean",
        "Median",
        "Mode",
        "Minimum",
        "Maximum",
        "Std Dev",
        "Skewness",
        "Kurtosis",
    ]
    assert all("std_dev_bands" not in row for row in rows)


def test_build_rows_renders_populated_values() -> None:
    rows = build_rows(_statistics())
    values_by_statistic = {row["statistic"]: row["value"] for row in rows}

    # 027 FR-003/FR-004: return-based rows (mean/median/mode/minimum/maximum/std_dev) are
    # basis points in the API response -- shown here as percent, matching the chart's x-axis
    # (value_bp / 100); count/skewness/kurtosis are not return values and stay unformatted.
    assert values_by_statistic["Count"] == "27"
    assert values_by_statistic["Mean"] == "0.04%"
    assert values_by_statistic["Std Dev"] == "0.14%"
    assert values_by_statistic["Skewness"] == "1.8"
    assert values_by_statistic["Kurtosis"] == "6.2"


def test_build_rows_formats_return_based_rows_as_percent_matching_the_chart() -> None:
    """027 FR-003: "is 8.08 mean for the 3Y HL-ISA really 0.0808%?" -- it must read "8.08%",
    using the exact same `value_bp / 100` conversion `_risk_chart.py` applies for its x-axis
    and mean reference line, not the raw basis-point number.
    """
    stats = _statistics(mean=808, median=-150, mode=0, minimum=-500, maximum=650, std_dev=107)
    rows = build_rows(stats)
    values_by_statistic = {row["statistic"]: row["value"] for row in rows}

    assert values_by_statistic["Mean"] == "8.08%"
    assert values_by_statistic["Median"] == "-1.50%"
    assert values_by_statistic["Mode"] == "0.00%"
    assert values_by_statistic["Minimum"] == "-5.00%"
    assert values_by_statistic["Maximum"] == "6.50%"
    assert values_by_statistic["Std Dev"] == "1.07%"


def test_build_rows_non_return_rows_have_no_percent_suffix() -> None:
    rows = build_rows(_statistics(count=27, skewness=1.8, kurtosis=6.2))
    values_by_statistic = {row["statistic"]: row["value"] for row in rows}

    assert values_by_statistic["Count"] == "27"
    assert "%" not in values_by_statistic["Count"]
    assert values_by_statistic["Skewness"] == "1.8"
    assert "%" not in values_by_statistic["Skewness"]
    assert values_by_statistic["Kurtosis"] == "6.2"
    assert "%" not in values_by_statistic["Kurtosis"]


def test_build_rows_renders_none_as_not_available() -> None:
    stats = _statistics(
        mean=None,
        median=None,
        mode=None,
        minimum=None,
        maximum=None,
        std_dev=None,
        skewness=None,
        kurtosis=None,
    )

    rows = build_rows(stats)
    values_by_statistic = {row["statistic"]: row["value"] for row in rows}

    assert values_by_statistic["Count"] == "27"
    not_applicable_labels = [
        "Mean",
        "Median",
        "Mode",
        "Minimum",
        "Maximum",
        "Std Dev",
        "Skewness",
        "Kurtosis",
    ]
    for label in not_applicable_labels:
        assert values_by_statistic[label] == "N/A"
