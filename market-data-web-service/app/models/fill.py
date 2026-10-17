from enum import StrEnum


class FillMode(StrEnum):
    """Series shaping mode for a price history request.

    ALL  — gap-fill every Mon-Fri business day in the requested range (the default,
           and the only behaviour before feature 009).
    NONE — return only dates carrying a real market observation; manufacture nothing.
    """

    ALL = "all"
    NONE = "none"
