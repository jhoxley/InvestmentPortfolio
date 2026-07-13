"""Single source of truth for the five supported time series attributes.

Both FR-004 (request validation) and FR-017 (metadata endpoint) read from the same
`ATTRIBUTE_DEFINITIONS` list, so the two can never drift apart (SC-004).
"""

from app.exceptions import NoAttributesRequestedError, UnsupportedAttributeError
from app.models.timeseries import AttributeDefinition

ATTRIBUTE_DEFINITIONS: list[AttributeDefinition] = [
    AttributeDefinition(
        name="capital",
        description="The capital value on that date.",
        source="capital_ledger",
    ),
    AttributeDefinition(
        name="income",
        description="The total income received up until that date.",
        source="capital_ledger",
    ),
    AttributeDefinition(
        name="book_cost",
        description="The book cost on that date (from the capital ledger's book_value field).",
        source="capital_ledger",
    ),
    AttributeDefinition(
        name="market_value",
        description=(
            "The sum of market_value across all sub-accounts in the position ladder for that date."
        ),
        source="position_ladder",
    ),
    AttributeDefinition(
        name="pnl",
        description="income + market_value - book_cost on that date.",
        source="capital_ledger,position_ladder",
    ),
]

SUPPORTED_ATTRIBUTES: frozenset[str] = frozenset(a.name for a in ATTRIBUTE_DEFINITIONS)

_REQUIRES_CAPITAL_LEDGER: frozenset[str] = frozenset({"capital", "income", "book_cost", "pnl"})
_REQUIRES_POSITION_LADDER: frozenset[str] = frozenset({"market_value", "pnl"})


def requires_capital_ledger(attribute: str) -> bool:
    """Return True if the given attribute requires the capital ledger.

    Args:
        attribute: A supported attribute name.

    Returns:
        True if the capital ledger is required to compute this attribute.
    """
    return attribute in _REQUIRES_CAPITAL_LEDGER


def requires_position_ladder(attribute: str) -> bool:
    """Return True if the given attribute requires the position ladder.

    Args:
        attribute: A supported attribute name.

    Returns:
        True if the position ladder is required to compute this attribute.
    """
    return attribute in _REQUIRES_POSITION_LADDER


def validate_attributes(attributes: list[str]) -> None:
    """Validate a requested attribute list against the supported set.

    Args:
        attributes: The requested attribute names.

    Raises:
        NoAttributesRequestedError: If attributes is empty.
        UnsupportedAttributeError: If any name is outside SUPPORTED_ATTRIBUTES; names
            every invalid entry, not just the first.
    """
    if not attributes:
        raise NoAttributesRequestedError()
    invalid = [a for a in attributes if a not in SUPPORTED_ATTRIBUTES]
    if invalid:
        raise UnsupportedAttributeError(requested=invalid, supported=sorted(SUPPORTED_ATTRIBUTES))
