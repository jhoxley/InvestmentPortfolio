"""Periodicity vocabulary shared by the time series request, aggregation, and responses."""

from enum import StrEnum


class Periodicity(StrEnum):
    """A calendar aggregation interval for a time series request.

    String-based so that the bare wire value (`"day"`, `"month"`, ...) is what appears in
    a serialised response body and what a raw query-string value is matched against.
    """

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    ANNUAL = "annual"


SUPPORTED_PERIODICITY_VALUES: tuple[str, ...] = tuple(p.value for p in Periodicity)
"""Every accepted wire value, in request order — the single source for the OpenAPI enum,
the rejection message, and the tests."""

PERIOD_ALIAS: dict[Periodicity, str] = {
    Periodicity.WEEK: "W",
    Periodicity.MONTH: "M",
    Periodicity.QUARTER: "Q",
    Periodicity.ANNUAL: "Y",
}
"""pandas period aliases per periodicity. `DAY` is deliberately absent: "no aggregation" is
a lookup miss rather than a special-cased string. These aliases align to the real calendar
(weeks from Monday, quarters from Jan/Apr/Jul/Oct, years from 01-Jan)."""
