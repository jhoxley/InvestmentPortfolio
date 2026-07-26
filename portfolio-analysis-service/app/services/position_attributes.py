"""Single source of truth for the eight supported position time series attributes.

Both FR-008 (request validation) and FR-017 (metadata endpoint) read from the same
`ATTRIBUTE_DEFINITIONS` list, so the two can never drift apart (SC-005). Unlike
`app/services/timeseries_attributes.py`'s account-level set, every attribute here is
sourced from the position ladder alone — there is no capital-ledger split.
"""

from app.exceptions import NoAttributesRequestedError, UnsupportedAttributeError
from app.models.timeseries import AttributeDefinition

ATTRIBUTE_DEFINITIONS: list[AttributeDefinition] = [
    AttributeDefinition(
        name="market_value",
        description="The position's market value on that date.",
        source="position_ladder",
    ),
    AttributeDefinition(
        name="income",
        description="The position's total income received up until that date.",
        source="position_ladder",
    ),
    AttributeDefinition(
        name="book_cost",
        description="The position's book cost on that date.",
        source="position_ladder",
    ),
    AttributeDefinition(
        name="pnl",
        description="income + market_value - book_cost on that date, for this position.",
        source="position_ladder",
    ),
    AttributeDefinition(
        name="close_price",
        description="The position's close price on that date.",
        source="position_ladder",
    ),
    AttributeDefinition(
        name="quantity",
        description="The position's held quantity on that date.",
        source="position_ladder",
    ),
    AttributeDefinition(
        name="position_return",
        description=(
            "The position's daily return: price change plus per-share income, relative to "
            "the previous day's price. Zero on the position's first recorded ladder date."
        ),
        source="position_ladder",
    ),
    AttributeDefinition(
        name="weighted_position_return",
        description=(
            "position_return scaled by the position's start-of-day (previous ladder date's) "
            "portfolio weight, for account- or theme-level contribution analysis."
        ),
        source="position_ladder",
    ),
]

SUPPORTED_ATTRIBUTES: frozenset[str] = frozenset(a.name for a in ATTRIBUTE_DEFINITIONS)

COLUMN_FOR_ATTRIBUTE: dict[str, str] = {
    "market_value": "market_value",
    "income": "total_income",
    "book_cost": "book_cost",
    "close_price": "price",
    "quantity": "quantity",
    "position_return": "position_return",
    "weighted_position_return": "weighted_position_return",
}


def validate_attributes(attributes: list[str]) -> None:
    """Validate a requested attribute list against the supported set.

    Args:
        attributes: The requested attribute names.

    Raises:
        NoAttributesRequestedError: If attributes is empty.
        UnsupportedAttributeError: If any name is outside SUPPORTED_ATTRIBUTES (including
            `capital`, which is valid on the account-level endpoint but not here); names
            every invalid entry, not just the first.
    """
    if not attributes:
        raise NoAttributesRequestedError()
    invalid = [a for a in attributes if a not in SUPPORTED_ATTRIBUTES]
    if invalid:
        raise UnsupportedAttributeError(requested=invalid, supported=sorted(SUPPORTED_ATTRIBUTES))
