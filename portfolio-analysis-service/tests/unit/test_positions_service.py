"""Unit tests for PositionsService position enumeration and effective-set resolution."""

from datetime import date

import pandas as pd
import pytest

from app.services.positions_service import PositionsService


def _ladder_df() -> pd.DataFrame:
    """Return a small synthetic ladder DataFrame with three sub_accounts.

    Returns:
        DataFrame with columns [date, sub_account], one row per (date, sub_account).
    """
    return pd.DataFrame(
        {
            "date": [
                date(2020, 1, 2),
                date(2020, 1, 3),
                date(2020, 1, 2),
                date(2020, 1, 10),
                date(2018, 6, 1),
                date(2018, 6, 5),
            ],
            "sub_account": [
                "Apple Inc",
                "Apple Inc",
                "Cash",
                "Cash",
                "Sold Corp",
                "Sold Corp",
            ],
        }
    )


@pytest.fixture()
def positions_service() -> PositionsService:
    """Return a fresh PositionsService instance.

    Returns:
        PositionsService with no constructor dependencies.
    """
    return PositionsService()


class TestListPositionsReturnsFirstAndLastDatePerSubAccount:
    """Tests that list_positions() computes accurate per-position date ranges."""

    def test_list_positions_returns_first_and_last_date_per_sub_account(
        self, positions_service: PositionsService
    ) -> None:
        """Each sub_account's min/max date is reported, sorted by position name."""
        summaries = positions_service.list_positions(_ladder_df())

        by_name = {s.position: s for s in summaries}
        assert list(by_name) == ["Apple Inc", "Cash", "Sold Corp"]
        assert by_name["Apple Inc"].from_date == date(2020, 1, 2)
        assert by_name["Apple Inc"].to_date == date(2020, 1, 3)
        assert by_name["Cash"].from_date == date(2020, 1, 2)
        assert by_name["Cash"].to_date == date(2020, 1, 10)
        assert by_name["Sold Corp"].from_date == date(2018, 6, 1)
        assert by_name["Sold Corp"].to_date == date(2018, 6, 5)


class TestResolveEffectivePositionsDefaultsToAllWhenNoneRequested:
    """Tests that an empty requested list defaults to every recorded sub_account."""

    def test_resolve_effective_positions_defaults_to_all_when_none_requested(
        self, positions_service: PositionsService
    ) -> None:
        """Zero requested positions resolves to all distinct sub_accounts, sorted."""
        result = positions_service.resolve_effective_positions(_ladder_df(), [])

        assert result == ["Apple Inc", "Cash", "Sold Corp"]


class TestResolveEffectivePositionsIntersectsAndSilentlyDropsUnmatched:
    """Tests that unmatched requested positions are silently dropped, not an error."""

    def test_resolve_effective_positions_intersects_and_silently_drops_unmatched(
        self, positions_service: PositionsService
    ) -> None:
        """Only the recognised requested position is returned; no exception raised."""
        result = positions_service.resolve_effective_positions(
            _ladder_df(), ["Apple Inc", "Nonexistent Corp"]
        )

        assert result == ["Apple Inc"]


class TestResolveEffectivePositionsDuplicateRequestedValuesTreatedOnce:
    """Tests that duplicate requested values collapse to a single position."""

    def test_resolve_effective_positions_duplicate_requested_values_treated_once(
        self, positions_service: PositionsService
    ) -> None:
        """Requesting the same position twice yields it exactly once."""
        result = positions_service.resolve_effective_positions(_ladder_df(), ["Cash", "Cash"])

        assert result == ["Cash"]


class TestResolveEffectivePositionsEmptyWhenAllRequestedUnmatched:
    """Tests that an all-unmatched request set returns an empty list, not an error."""

    def test_resolve_effective_positions_empty_when_all_requested_unmatched(
        self, positions_service: PositionsService
    ) -> None:
        """Every requested value failing to match returns an empty list."""
        result = positions_service.resolve_effective_positions(
            _ladder_df(), ["Nonexistent Corp", "Also Missing"]
        )

        assert result == []
