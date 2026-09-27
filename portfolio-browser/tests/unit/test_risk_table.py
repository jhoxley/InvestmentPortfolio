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

    assert values_by_statistic["Count"] == "27"
    assert values_by_statistic["Mean"] == "4.1"
    assert values_by_statistic["Std Dev"] == "14.2"


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
