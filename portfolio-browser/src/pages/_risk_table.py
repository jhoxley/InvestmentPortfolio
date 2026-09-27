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


def build_rows(statistics: HistogramStatistics) -> list[dict[str, str]]:
    """Build statistic/value row dicts for the statistics DataTable.

    Args:
        statistics: The response's `statistics` object.

    Returns:
        One dict per row (`{"statistic": ..., "value": ...}`), in
        `_ROW_LABELS` order. A `None` field value renders as "N/A" rather
        than being omitted (spec FR-012).
    """
    values = statistics.model_dump()
    rows = []
    for field, label in _ROW_LABELS:
        value = values[field]
        rows.append({"statistic": label, "value": _NOT_AVAILABLE if value is None else str(value)})
    return rows
