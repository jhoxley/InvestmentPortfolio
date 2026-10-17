"""Unit tests for the shared value-formatting helper in
src/components/value_formatting.py (used by both the Positions page and
Overview's new position visualizations;
specs/019-overview-position-visuals/research.md #2).

Relocated verbatim from tests/unit/test_positions_chart_shaping.py
(behavior unchanged).
"""

from __future__ import annotations

from src.components.value_formatting import _format_attribute_value


def test_format_attribute_value_currency_for_monetary_attribute() -> None:
    assert _format_attribute_value("market_value", 1234.5) == "£1,234.50"


def test_format_attribute_value_plain_for_quantity() -> None:
    assert _format_attribute_value("quantity", 25.0) == "25.00"


def test_format_attribute_value_currency_fallback_for_unknown_attribute() -> None:
    assert _format_attribute_value("some_future_attribute", 10.0) == "£10.00"
