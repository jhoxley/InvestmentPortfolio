"""Return-name validation for the projection endpoint.

A fixed subset of `performance_attributes.py`'s own supported measure names — reused verbatim
(specs/009-projection-endpoint/research.md #2) rather than a second, parallel naming scheme.
"""

from app.exceptions import UnsupportedAttributeError

SUPPORTED_PROJECTION_RETURNS: frozenset[str] = frozenset({"ITD (Ann.)", "1Y", "3Y", "5Y"})
"""Every return the projection endpoint accepts. Deliberately excludes plain 'ITD' (spec
FR-005) — an inception-to-date return that isn't annualized has no well-defined daily rate to
project forward with."""


def validate_returns(returns: list[str]) -> None:
    """Validate a requested return-name list against the supported set.

    Unlike `performance_attributes.validate_attributes`, an empty list is valid here — the
    projection endpoint's own FR-012 requires that requesting zero returns still succeeds,
    returning the historical series alone.

    Args:
        returns: The requested return names.

    Raises:
        UnsupportedAttributeError: If any name is outside SUPPORTED_PROJECTION_RETURNS; names
            every invalid entry, not just the first.
    """
    invalid = [r for r in returns if r not in SUPPORTED_PROJECTION_RETURNS]
    if invalid:
        raise UnsupportedAttributeError(
            requested=invalid, supported=sorted(SUPPORTED_PROJECTION_RETURNS)
        )
