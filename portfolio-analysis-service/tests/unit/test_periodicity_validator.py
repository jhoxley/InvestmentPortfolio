"""Unit tests for the periodicity query-parameter validator."""

import pytest

from app.exceptions import UnsupportedPeriodicityError
from app.models.periodicity import SUPPORTED_PERIODICITY_VALUES, Periodicity
from app.validators.periodicity import resolve_periodicity


class TestDefaultsToDay:
    """An absent periodicity must resolve to the day default (FR-002)."""

    def test_none_resolves_to_day(self) -> None:
        """Omitting the parameter yields Periodicity.DAY."""
        assert resolve_periodicity(None) is Periodicity.DAY


class TestAcceptsEverySupportedToken:
    """Each of the five documented tokens must resolve to its matching member (FR-001)."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("day", Periodicity.DAY),
            ("week", Periodicity.WEEK),
            ("month", Periodicity.MONTH),
            ("quarter", Periodicity.QUARTER),
            ("annual", Periodicity.ANNUAL),
        ],
    )
    def test_supported_token_resolves(self, raw: str, expected: Periodicity) -> None:
        """A valid lowercase token resolves to its enum member.

        Args:
            raw: The raw query-string value.
            expected: The member it must resolve to.
        """
        assert resolve_periodicity(raw) is expected

    def test_supported_values_tuple_matches_enum(self) -> None:
        """The declared supported set is exactly the enum's values, in request order."""
        assert SUPPORTED_PERIODICITY_VALUES == ("day", "week", "month", "quarter", "annual")
        assert set(SUPPORTED_PERIODICITY_VALUES) == {p.value for p in Periodicity}


class TestRejectsUnsupportedValues:
    """Matching is case-sensitive and admits no synonyms (spec Assumptions, FR-014)."""

    @pytest.mark.parametrize(
        "raw",
        [
            "Annual",
            "ANNUAL",
            "yearly",
            "annually",
            "daily",
            "Q",
            "fortnight",
            "",
            " day ",
        ],
    )
    def test_unsupported_value_raises(self, raw: str) -> None:
        """An unrecognised value is rejected rather than silently defaulted.

        Args:
            raw: The raw query-string value that must be rejected.
        """
        with pytest.raises(UnsupportedPeriodicityError):
            resolve_periodicity(raw)


class TestErrorCarriesDiagnosticContext:
    """The raised error must name the rejected value and the full supported set (SC-007)."""

    def test_error_attributes_and_message(self) -> None:
        """requested/supported are populated and the message names all five values."""
        with pytest.raises(UnsupportedPeriodicityError) as exc_info:
            resolve_periodicity("fortnight")

        exc = exc_info.value
        assert exc.requested == "fortnight"
        assert exc.supported == SUPPORTED_PERIODICITY_VALUES
        message = str(exc)
        assert "fortnight" in message
        for value in SUPPORTED_PERIODICITY_VALUES:
            assert value in message, f"Supported value '{value}' missing from error message"
