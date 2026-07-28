"""Single source of truth for the five supported account performance measures.

Both the `/performance` endpoint's request validation and the `/performance/attributes`
metadata endpoint read from the same `ATTRIBUTE_DEFINITIONS` list, so the two can never
drift apart, mirroring `timeseries_attributes.py`'s role for the account time series API.
"""

from app.exceptions import NoAttributesRequestedError, UnsupportedAttributeError
from app.models.performance import PerformanceAttributeDefinition

ATTRIBUTE_DEFINITIONS: list[PerformanceAttributeDefinition] = [
    PerformanceAttributeDefinition(
        name="ITD",
        description=(
            "Inception to Date: the cumulative product of (1 + daily portfolio return) "
            "from the account's first recorded date through the given date, minus 1."
        ),
        source="position_ladder",
    ),
    PerformanceAttributeDefinition(
        name="ITD (Ann.)",
        description=(
            "ITD expressed as an annualized rate, scaled by the number of trading days "
            "elapsed since inception (260-trading-day year)."
        ),
        source="position_ladder",
    ),
    PerformanceAttributeDefinition(
        name="1Y",
        description=(
            "The cumulative product of (1 + daily portfolio return) over the trailing "
            "260 business days, minus 1. Not annualized."
        ),
        source="position_ladder",
    ),
    PerformanceAttributeDefinition(
        name="3Y",
        description=(
            "The cumulative product of (1 + daily portfolio return) over the trailing "
            "780 business days, annualized by raising to the power of 1/3."
        ),
        source="position_ladder",
    ),
    PerformanceAttributeDefinition(
        name="5Y",
        description=(
            "The cumulative product of (1 + daily portfolio return) over the trailing "
            "1300 business days, annualized by raising to the power of 1/5."
        ),
        source="position_ladder",
    ),
]

SUPPORTED_ATTRIBUTES: frozenset[str] = frozenset(a.name for a in ATTRIBUTE_DEFINITIONS)


def validate_attributes(attributes: list[str]) -> None:
    """Validate a requested performance-measure list against the supported set.

    Args:
        attributes: The requested measure names.

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
