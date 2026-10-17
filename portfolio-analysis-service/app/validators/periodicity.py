"""Validation for the optional `periodicity` query parameter."""

from app.exceptions import UnsupportedPeriodicityError
from app.models.periodicity import SUPPORTED_PERIODICITY_VALUES, Periodicity


def resolve_periodicity(raw: str | None) -> Periodicity:
    """Resolve a raw query-string periodicity value into a Periodicity member.

    Matching is exact and case-sensitive, consistent with the account names and attribute
    names these endpoints already use — `Annual`, `yearly` and `daily` are all rejected
    rather than silently coerced, so a caller never receives a series at a periodicity
    they didn't ask for.

    Args:
        raw: The caller-supplied value, or None when the parameter was omitted.

    Returns:
        The matching Periodicity member; Periodicity.DAY when raw is None.

    Raises:
        UnsupportedPeriodicityError: If raw is neither None nor an exact supported value.
    """
    if raw is None:
        return Periodicity.DAY
    try:
        return Periodicity(raw)
    except ValueError as exc:
        raise UnsupportedPeriodicityError(
            requested=raw, supported=SUPPORTED_PERIODICITY_VALUES
        ) from exc
