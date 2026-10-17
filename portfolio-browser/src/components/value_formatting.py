"""Shared attribute-value formatting (Positions page + Overview page).

Extracted from `src/pages/_positions_chart.py` (018) so the Overview
page's new position visualizations (019) can reuse the same
currency-vs-plain-numeric formatting logic rather than duplicating the
monetary-attribute-name list a second time
(specs/019-overview-position-visuals/research.md #2).
"""

from __future__ import annotations

# `quantity` is a share count, not a currency value; every other currently
# known position attribute (market_value, income, book_cost, pnl,
# close_price) is monetary. Currency is the fallback for any attribute not
# in this set, matching _overview_chart.py's ATTRIBUTE_COLORS/
# DEFAULT_ATTRIBUTE_COLOR fixed-mapping-with-default shape.
_PLAIN_NUMERIC_ATTRIBUTES = frozenset({"quantity"})


def _format_attribute_value(attribute_name: str, value: float) -> str:
    """Format a numeric attribute value for display.

    Args:
        attribute_name: The wire-format attribute name (e.g. "market_value").
        value: The raw numeric value to format.

    Returns:
        `"£1,234.50"`-style for monetary attributes; `"25.00"`-style (no
        currency symbol) for `quantity`.
    """
    if attribute_name in _PLAIN_NUMERIC_ATTRIBUTES:
        return f"{value:,.2f}"
    return f"£{value:,.2f}"
