"""Pure, side-effect-free helper for the Risk page's statistics table.

Kept out of risk.py so it stays importable from a plain unit test, mirroring
`_risk_chart.py`'s and `_performance_chart.py`'s own separation-of-concerns
rationale.
"""

from __future__ import annotations

from src.models.portfolio_analysis import HistogramStatistics

_NOT_AVAILABLE = "N/A"

# Declared in HistogramStatistics's own field order, excluding std_dev_bands
# (spec FR-010 explicitly excludes it from this table).
_ROW_LABELS: list[tuple[str, str]] = [
    ("count", "Count"),
    ("mean", "Mean"),
    ("median", "Median"),
    ("mode", "Mode"),
    ("minimum", "Minimum"),
    ("maximum", "Maximum"),
    ("std_dev", "Std Dev"),
    ("skewness", "Skewness"),
    ("kurtosis", "Kurtosis"),
]

# Fields whose raw value is basis points (027 FR-003/FR-004) -- every return-based
# statistic, including `mode` (a bucket center, same unit as mean/median/min/max even
# though spec.md's FR-003 names only the latter as its "at minimum" examples). Must use
# the exact same `/ 100` divisor `_risk_chart.py::build_figure` applies for its x-axis and
# mean reference line, so the table can never disagree with the chart (research.md #2).
_PERCENT_FIELDS = {"mean", "median", "mode", "minimum", "maximum", "std_dev"}


def _format_pct_bp(value_bp: float | int) -> str:
    """Format a basis-point return value as the percent string the chart itself uses."""
    return f"{value_bp / 100:.2f}%"


def build_rows(statistics: HistogramStatistics) -> list[dict[str, str]]:
    """Build statistic/value row dicts for the statistics DataTable.

    Args:
        statistics: The response's `statistics` object.

    Returns:
        One dict per row (`{"statistic": ..., "value": ...}`), in
        `_ROW_LABELS` order. A `None` field value renders as "N/A" rather
        than being omitted (spec FR-012). Return-based rows (`_PERCENT_FIELDS`)
        render as a percent string matching the chart's x-axis (spec FR-003);
        the rest (count, skewness, kurtosis) render as a plain string (FR-004).
    """
    values = statistics.model_dump()
    rows = []
    for field, label in _ROW_LABELS:
        value = values[field]
        if value is None:
            rendered = _NOT_AVAILABLE
        elif field in _PERCENT_FIELDS:
            rendered = _format_pct_bp(value)
        else:
            rendered = str(value)
        rows.append({"statistic": label, "value": rendered})
    return rows
