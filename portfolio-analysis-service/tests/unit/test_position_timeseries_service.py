"""Unit tests for PositionTimeSeriesService per-position expansion and validation."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.exceptions import (
    AccountNotFoundError,
    FutureEndDateError,
    InvalidDateRangeError,
    MissingRequiredSourceError,
    NoAttributesRequestedError,
    PositionLadderNotIngestedError,
    UnsupportedAttributeError,
)
from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.accounts_service import AccountsService
from app.services.position_timeseries_service import PositionTimeSeriesService
from app.services.positions_service import PositionsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver

TODAY = date(2024, 6, 14)  # Friday, well after all fixture dates below


def _write_ladder(
    repo: LadderRepository,
    account_name: str,
    rows: list[dict],
    to_date: date | None = None,
) -> None:
    """Write a stored position ladder for an account from explicit rows.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
        rows: List of dicts with keys date, sub_account, and optionally book_cost,
            quantity, total_income, price, market_value (defaulted if omitted).
        to_date: Explicit meta.to_date override, used to simulate a still-held position
            (its own last row equal to the ladder's to_date) independent of the
            DataFrame's actual max date; defaults to the DataFrame's own max date.
    """
    df = pd.DataFrame(
        [
            {
                "date": r["date"],
                "sub_account": r["sub_account"],
                "book_cost": r.get("book_cost", 0.0),
                "quantity": r.get("quantity", 1.0),
                "total_income": r.get("total_income", 0.0),
                "price": r.get("price", 1.0),
                "market_value": r.get("market_value", 0.0),
                "portfolio_weight": 1.0,
            }
            for r in rows
        ]
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="cafebabe",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=to_date if to_date is not None else df["date"].max(),
        sub_accounts=sorted(df["sub_account"].unique().tolist()),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


def _write_capital(repo: CapitalRepository, account_name: str) -> None:
    """Write a minimal stored capital ledger, to simulate a 'known' capital-only account.

    Args:
        repo: CapitalRepository to write through.
        account_name: Target account name.
    """
    df = pd.DataFrame(
        {"date": [date(2020, 1, 2)], "capital": [1000.0], "income": [0.0], "book_value": [900.0]}
    )
    meta = CapitalMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=date(2020, 1, 2),
        to_date=date(2020, 1, 2),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


@pytest.fixture()
def ladder_repo(tmp_path: Path) -> LadderRepository:
    """Return a tmp_path-backed LadderRepository.

    Returns:
        LadderRepository ready for use in tests.
    """
    return LadderRepository(data_dir=tmp_path)


@pytest.fixture()
def capital_repo(tmp_path: Path) -> CapitalRepository:
    """Return a tmp_path-backed CapitalRepository.

    Returns:
        CapitalRepository ready for use in tests.
    """
    return CapitalRepository(data_dir=tmp_path)


@pytest.fixture()
def service(
    ladder_repo: LadderRepository, capital_repo: CapitalRepository
) -> PositionTimeSeriesService:
    """Return a PositionTimeSeriesService wired to the tmp_path-backed repositories.

    Returns:
        PositionTimeSeriesService ready for use in tests.
    """
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return PositionTimeSeriesService(
        ladder_repo=ladder_repo,
        accounts_service=accounts_service,
        positions_service=PositionsService(),
        date_resolver=TimeseriesDateResolver(),
    )


class TestEffectivePositionsDefaultToAllIncludingCashWhenNoneRequested:
    """No position names supplied resolves to every recorded position, including Cash."""

    def test_effective_positions_default_to_all_including_cash_when_none_requested(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """Both positions appear when zero position names are requested."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {"date": date(2024, 1, 2), "sub_account": "Apple Inc", "market_value": 100.0},
                {"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 50.0},
            ],
        )

        response = service.get_series(
            "acct", [], ["market_value"], date(2024, 1, 2), date(2024, 1, 2), TODAY
        )

        assert response.positions == ["Apple Inc", "Cash"]
        assert len(response.entries) == 2


class TestUnrecognisedPositionSilentlyDroppedNoError:
    """A mix of recognised and unrecognised position names never raises."""

    def test_unrecognised_position_silently_dropped_no_error(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """Only the recognised position appears in the response."""
        _write_ladder(
            ladder_repo,
            "acct",
            [{"date": date(2024, 1, 2), "sub_account": "Apple Inc", "market_value": 100.0}],
        )

        response = service.get_series(
            "acct",
            ["Apple Inc", "Nonexistent Corp"],
            ["market_value"],
            date(2024, 1, 2),
            date(2024, 1, 2),
            TODAY,
        )

        assert response.positions == ["Apple Inc"]
        assert len(response.entries) == 1


class TestAllRequestedPositionsUnmatchedReturnsZeroEntriesNotError:
    """Every requested position failing to match returns an empty, successful response."""

    def test_all_requested_positions_unmatched_returns_zero_entries_not_error(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """No exception is raised; entries and positions are both empty."""
        _write_ladder(
            ladder_repo,
            "acct",
            [{"date": date(2024, 1, 2), "sub_account": "Apple Inc", "market_value": 100.0}],
        )

        response = service.get_series(
            "acct",
            ["Nonexistent Corp"],
            ["market_value"],
            date(2024, 1, 2),
            date(2024, 1, 2),
            TODAY,
        )

        assert response.entries == []
        assert response.positions == []


class TestEntriesContainOnlyRequestedAttributeKeys:
    """Entries never carry keys for attributes that weren't requested."""

    def test_entries_contain_only_requested_attribute_keys(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """Only 'date', 'position', and 'market_value' appear."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {
                    "date": date(2024, 1, 2),
                    "sub_account": "Apple Inc",
                    "market_value": 100.0,
                    "quantity": 5.0,
                }
            ],
        )

        response = service.get_series(
            "acct", [], ["market_value"], date(2024, 1, 2), date(2024, 1, 2), TODAY
        )

        keys = set(response.entries[0].model_dump().keys())
        assert keys == {"date", "position", "market_value"}


class TestEachDirectAttributeSourcedFromItsOwnColumn:
    """Each direct-mapping attribute reads from its own distinct ladder column."""

    def test_market_value_book_cost_income_close_price_quantity_each_sourced_from_their_own_column(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """No column is accidentally cross-wired to the wrong attribute."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {
                    "date": date(2024, 1, 2),
                    "sub_account": "Apple Inc",
                    "market_value": 111.0,
                    "book_cost": 222.0,
                    "total_income": 333.0,
                    "price": 444.0,
                    "quantity": 555.0,
                }
            ],
        )

        response = service.get_series(
            "acct",
            [],
            ["market_value", "book_cost", "income", "close_price", "quantity"],
            date(2024, 1, 2),
            date(2024, 1, 2),
            TODAY,
        )

        entry = response.entries[0].model_dump()
        assert entry["market_value"] == 111.0
        assert entry["book_cost"] == 222.0
        assert entry["income"] == 333.0
        assert entry["close_price"] == 444.0
        assert entry["quantity"] == 555.0


class TestPnlEqualsIncomePlusMarketValueMinusBookCostPerPosition:
    """pnl is computed correctly per position from its own three components."""

    def test_pnl_equals_income_plus_market_value_minus_book_cost_per_position(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """Pnl = income + market_value - book_cost for the position's own values."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {
                    "date": date(2024, 1, 2),
                    "sub_account": "Apple Inc",
                    "market_value": 900.0,
                    "book_cost": 800.0,
                    "total_income": 50.0,
                }
            ],
        )

        response = service.get_series(
            "acct", [], ["pnl"], date(2024, 1, 2), date(2024, 1, 2), TODAY
        )

        entry = response.entries[0].model_dump()
        assert entry["pnl"] == pytest.approx(50.0 + 900.0 - 800.0)


class TestStillHeldPositionForwardFilledThroughResolvedEnd:
    """A position whose last row equals the ladder's own to_date is forward-filled."""

    def test_still_held_position_forward_filled_through_resolved_end(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """Entries continue through resolved_end carrying the last known value."""
        _write_ladder(
            ladder_repo,
            "acct",
            [{"date": date(2024, 1, 8), "sub_account": "Apple Inc", "market_value": 5000.0}],
            to_date=date(2024, 1, 8),
        )

        response = service.get_series(
            "acct", [], ["market_value"], date(2024, 1, 8), date(2024, 1, 10), TODAY
        )

        by_date = {e.date: e.model_dump()["market_value"] for e in response.entries}
        assert by_date[date(2024, 1, 9)] == 5000.0
        assert by_date[date(2024, 1, 10)] == 5000.0


class TestDivestedPositionNotForwardFilledPastItsOwnLastRow:
    """A position whose last row precedes the ladder's own to_date is never filled past it."""

    def test_divested_position_not_forward_filled_past_its_own_last_row(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """No entries appear after the position's own recorded closure date."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {
                    "date": date(2024, 1, 5),
                    "sub_account": "Sold Corp",
                    "market_value": 300.0,
                    "quantity": 0.0,
                }
            ],
            to_date=date(2024, 1, 10),
        )

        response = service.get_series("acct", [], ["market_value"], None, date(2024, 1, 10), TODAY)

        dates = {e.date for e in response.entries}
        assert date(2024, 1, 5) in dates
        assert date(2024, 1, 8) not in dates
        assert date(2024, 1, 10) not in dates


class TestPositionBoughtAfterResolvedStartHasNoEntriesBeforeItsFirstRow:
    """A position with no recorded activity before its own first row has no earlier entries."""

    def test_position_bought_after_resolved_start_has_no_entries_before_its_first_row(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """Entries only start from the position's own recorded first date."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 10.0},
                {"date": date(2024, 1, 8), "sub_account": "Apple Inc", "market_value": 500.0},
            ],
            to_date=date(2024, 1, 8),
        )

        response = service.get_series(
            "acct",
            ["Apple Inc"],
            ["market_value"],
            date(2024, 1, 2),
            date(2024, 1, 8),
            TODAY,
        )

        dates = {e.date for e in response.entries}
        assert date(2024, 1, 2) not in dates
        assert date(2024, 1, 8) in dates


class TestPositionWithNoOverlapWithResolvedRangeProducesZeroEntriesNotAnError:
    """A position whose active window doesn't overlap the resolved range is skipped, not an error."""

    def test_position_with_no_overlap_with_resolved_range_produces_zero_entries_not_an_error(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """No exception; the position simply contributes zero entries."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 10.0},
                {
                    "date": date(2024, 1, 3),
                    "sub_account": "Sold Corp",
                    "market_value": 20.0,
                    "quantity": 0.0,
                },
            ],
            to_date=date(2024, 1, 10),
        )

        response = service.get_series(
            "acct",
            ["Sold Corp"],
            ["market_value"],
            date(2024, 1, 5),
            date(2024, 1, 10),
            TODAY,
        )

        assert response.entries == []
        assert response.positions == []


class TestResponsePositionsFieldExcludesAPositionSkippedForZeroOverlap:
    """The positions field only lists positions actually represented in entries."""

    def test_response_positions_field_excludes_a_position_skipped_for_zero_overlap(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """Sold Corp (zero overlap) is absent from positions; Cash (has data) is present."""
        _write_ladder(
            ladder_repo,
            "acct",
            [
                {"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 10.0},
                {"date": date(2024, 1, 10), "sub_account": "Cash", "market_value": 10.0},
                {
                    "date": date(2024, 1, 3),
                    "sub_account": "Sold Corp",
                    "market_value": 20.0,
                    "quantity": 0.0,
                },
            ],
            to_date=date(2024, 1, 10),
        )

        response = service.get_series(
            "acct",
            ["Cash", "Sold Corp"],
            ["market_value"],
            date(2024, 1, 5),
            date(2024, 1, 10),
            TODAY,
        )

        assert "Sold Corp" not in response.positions
        assert "Cash" in response.positions


class TestStartBeforeLaddersOwnEarliestDateRaisesMissingRequiredSourceError:
    """An explicit start earlier than the ladder's own earliest date raises."""

    def test_start_before_ladders_own_earliest_date_raises_missing_required_source_error(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """A start before the ladder's own from_date raises MissingRequiredSourceError."""
        _write_ladder(
            ladder_repo,
            "acct",
            [{"date": date(2024, 1, 10), "sub_account": "Cash", "market_value": 10.0}],
        )

        with pytest.raises(MissingRequiredSourceError):
            service.get_series(
                "acct", [], ["market_value"], date(2024, 1, 2), date(2024, 1, 10), TODAY
            )


class TestKnownAccountWithoutLadderRaisesPositionLadderNotIngestedError:
    """A capital-only account is known but cannot serve this endpoint at all."""

    def test_known_account_without_ladder_raises_position_ladder_not_ingested_error(
        self, capital_repo: CapitalRepository, service: PositionTimeSeriesService
    ) -> None:
        """PositionLadderNotIngestedError is raised, not AccountNotFoundError."""
        _write_capital(capital_repo, "capital-only")

        with pytest.raises(PositionLadderNotIngestedError):
            service.get_series("capital-only", [], ["market_value"], None, date(2020, 1, 2), TODAY)


class TestUnknownAccountRaisesAccountNotFoundError:
    """An account with no ingested resource of any kind is rejected as unknown."""

    def test_unknown_account_raises_account_not_found_error(
        self, service: PositionTimeSeriesService
    ) -> None:
        """AccountNotFoundError is raised for a wholly unknown account."""
        with pytest.raises(AccountNotFoundError):
            service.get_series("unknown", [], ["market_value"], None, date(2024, 1, 2), TODAY)


class TestCapitalAttributeRejectedAsUnsupported:
    """The 'capital' attribute is not valid on this endpoint."""

    def test_capital_attribute_rejected_as_unsupported(
        self, service: PositionTimeSeriesService
    ) -> None:
        """UnsupportedAttributeError is raised for 'capital'."""
        with pytest.raises(UnsupportedAttributeError):
            service.get_series("acct", [], ["capital"], None, date(2024, 1, 2), TODAY)


class TestNoAttributesRaisesNoAttributesRequestedError:
    """Zero requested attributes is rejected."""

    def test_no_attributes_raises_no_attributes_requested_error(
        self, service: PositionTimeSeriesService
    ) -> None:
        """NoAttributesRequestedError is raised when attributes is empty."""
        with pytest.raises(NoAttributesRequestedError):
            service.get_series("acct", [], [], None, date(2024, 1, 2), TODAY)


class TestResolvedStartAfterResolvedEndRaisesInvalidDateRangeError:
    """A start after end is rejected."""

    def test_resolved_start_after_resolved_end_raises_invalid_date_range_error(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """InvalidDateRangeError is raised when start is after end."""
        _write_ladder(
            ladder_repo,
            "acct",
            [{"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 10.0}],
        )

        with pytest.raises(InvalidDateRangeError):
            service.get_series(
                "acct", [], ["market_value"], date(2024, 2, 1), date(2024, 1, 1), TODAY
            )


class TestFutureEndDateRaisesFutureEndDateError:
    """An end date later than today is rejected."""

    def test_future_end_date_raises_future_end_date_error(
        self, ladder_repo: LadderRepository, service: PositionTimeSeriesService
    ) -> None:
        """FutureEndDateError is raised when end is later than today."""
        _write_ladder(
            ladder_repo,
            "acct",
            [{"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 10.0}],
        )

        with pytest.raises(FutureEndDateError):
            service.get_series(
                "acct", [], ["market_value"], None, TODAY + timedelta(days=30), TODAY
            )
