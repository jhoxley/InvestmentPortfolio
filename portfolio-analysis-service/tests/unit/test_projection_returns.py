"""Unit tests for the projection endpoint's return-name validator (022)."""

import pytest

from app.exceptions import UnsupportedAttributeError
from app.services.projection_returns import SUPPORTED_PROJECTION_RETURNS, validate_returns


def test_supported_returns_are_exactly_the_four_expected_names() -> None:
    """The supported set is fixed and excludes plain 'ITD' (spec FR-005)."""
    assert frozenset({"ITD (Ann.)", "1Y", "3Y", "5Y"}) == SUPPORTED_PROJECTION_RETURNS


def test_empty_list_does_not_raise() -> None:
    """Unlike performance_attributes.validate_attributes, an empty list is valid (FR-012)."""
    validate_returns([])


@pytest.mark.parametrize("name", ["ITD (Ann.)", "1Y", "3Y", "5Y"])
def test_each_supported_name_passes_individually(name: str) -> None:
    """Each of the four supported names is accepted on its own."""
    validate_returns([name])


def test_all_four_supported_names_pass_together() -> None:
    """All four supported names can be requested together in one call."""
    validate_returns(["ITD (Ann.)", "1Y", "3Y", "5Y"])


def test_plain_itd_is_rejected() -> None:
    """Plain 'ITD' is deliberately excluded from the projection endpoint's supported set."""
    with pytest.raises(UnsupportedAttributeError) as exc_info:
        validate_returns(["ITD"])
    assert exc_info.value.requested == ["ITD"]


@pytest.mark.parametrize("name", ["10Y", "itd_ann", "", "annual"])
def test_unknown_name_is_rejected(name: str) -> None:
    """An unrecognized return name is rejected."""
    with pytest.raises(UnsupportedAttributeError) as exc_info:
        validate_returns([name])
    assert exc_info.value.requested == [name]


def test_only_invalid_names_are_listed_in_the_exception() -> None:
    """A mixed request names only the invalid entries, not the valid ones alongside them."""
    with pytest.raises(UnsupportedAttributeError) as exc_info:
        validate_returns(["1Y", "bogus", "3Y"])
    assert exc_info.value.requested == ["bogus"]


def test_supported_set_in_exception_is_the_sorted_four_element_set() -> None:
    """The exception's supported list is the sorted four-element set."""
    with pytest.raises(UnsupportedAttributeError) as exc_info:
        validate_returns(["bogus"])
    assert exc_info.value.supported == sorted(SUPPORTED_PROJECTION_RETURNS)
