"""Unit tests for PerformanceService orchestration, validation, and error handling."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.exceptions import (
    AccountNotFoundError,
    MissingRequiredSourceError,
    NoAttributesRequestedError,
    UnsupportedAttributeError,
)
from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.accounts_service import AccountsService
from app.services.performance_service import PerformanceService
from app.services.timeseries_date_resolver import TimeseriesDateResolver

TODAY = date(2024, 6, 14)  # Friday, well after all fixture dates below


def _write_ladder(repo: LadderRepository, account_name: str, rows: list[dict]) -> None:
    """Write a stored position ladder for an account from explicit rows.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
        rows: List of dicts with keys date, sub_account, weighted_position_return.
    """
    df = pd.DataFrame(
        [
            {
                "date": r["date"],
                "sub_account": r["sub_account"],
                "book_cost": 0.0,
                "quantity": 1.0,
                "total_income": 0.0,
                "price": 1.0,
                "market_value": 0.0,
                "portfolio_weight": 1.0,
                "position_return": 0.0,
                "weighted_position_return": r["weighted_position_return"],
            }
            for r in rows
        ]
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="cafebabe",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=df["date"].max(),
        sub_accounts=sorted(df["sub_account"].unique().tolist()),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


def _write_capital(repo: CapitalRepository, account_name: str, rows: list[dict]) -> None:
    """Write a stored capital ledger for an account from explicit rows.

    Args:
        repo: CapitalRepository to write through.
        account_name: Target account name.
        rows: List of dicts with keys date, capital, income, book_value.
    """
    df = pd.DataFrame(rows)
    meta = CapitalMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=df["date"].max(),
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
def service(ladder_repo: LadderRepository, capital_repo: CapitalRepository) -> PerformanceService:
    """Return a PerformanceService wired to the tmp_path-backed repositories.

    Returns:
        PerformanceService ready for use in tests.
    """
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return PerformanceService(
        ladder_repo=ladder_repo,
        accounts_service=accounts_service,
        date_resolver=TimeseriesDateResolver(),
    )


class TestReturnsPopulatedResponseForKnownAccount:
    """A written ladder produces a response with one entry per business day."""

    def test_returns_populated_response_for_known_account(
        self, ladder_repo: LadderRepository, service: PerformanceService
    ) -> None:
        """get_performance() returns entries carrying the requested measure where computable."""
        _write_ladder(
            ladder_repo,
            "known",
            [
                {
                    "date": date(2024, 1, 2),
                    "sub_account": "Cash",
                    "weighted_position_return": 0.0,
                },
                {
                    "date": date(2024, 1, 3),
                    "sub_account": "Cash",
                    "weighted_position_return": 0.01,
                },
            ],
        )

        response = service.get_performance(
            "known", ["ITD"], date(2024, 1, 2), date(2024, 1, 3), TODAY
        )

        assert len(response.entries) == 2
        keys = set(response.entries[0].model_dump().keys())
        assert "ITD" in keys


class TestUnknownAccountRaisesAccountNotFoundError:
    """No resource of any kind ingested for the account raises AccountNotFoundError."""

    def test_unknown_account_raises_account_not_found_error(
        self, service: PerformanceService
    ) -> None:
        """An account with no ladder or capital ledger raises AccountNotFoundError."""
        with pytest.raises(AccountNotFoundError):
            service.get_performance("unknown", ["ITD"], None, date(2024, 1, 2), TODAY)


class TestKnownAccountWithoutLadderRaisesMissingRequiredSourceError:
    """A known account (e.g. via capital ledger) with no ladder raises MissingRequiredSourceError."""

    def test_known_account_without_ladder_raises_missing_required_source_error(
        self, capital_repo: CapitalRepository, service: PerformanceService
    ) -> None:
        """Requesting any performance measure on a capital-only account raises."""
        _write_capital(
            capital_repo,
            "capital-only",
            [{"date": date(2024, 1, 2), "capital": 1000.0, "income": 0.0, "book_value": 800.0}],
        )

        with pytest.raises(MissingRequiredSourceError) as exc_info:
            service.get_performance("capital-only", ["ITD"], None, date(2024, 1, 2), TODAY)
        assert exc_info.value.source == "position_ladder"


class TestDateResolutionMatchesTimeseriesDateResolverDefaults:
    """No explicit start/end defaults exactly as TimeseriesDateResolver.resolve() would."""

    def test_date_resolution_matches_timeseries_date_resolver_defaults(
        self, ladder_repo: LadderRepository, service: PerformanceService
    ) -> None:
        """Resolved dates equal calling TimeseriesDateResolver.resolve() directly."""
        _write_ladder(
            ladder_repo,
            "known",
            [
                {
                    "date": date(2024, 1, 2),
                    "sub_account": "Cash",
                    "weighted_position_return": 0.0,
                }
            ],
        )

        response = service.get_performance("known", ["ITD"], None, None, TODAY)

        expected_start, expected_end = TimeseriesDateResolver().resolve(
            raw_start=None,
            raw_end=None,
            today=TODAY,
            required_source_earliest_dates=[date(2024, 1, 2)],
        )
        assert response.from_date == expected_start
        assert response.to_date == expected_end


class TestEntryOmitsKeyForNotYetComputableMeasure:
    """A measure without enough history is omitted from the entry, not nulled."""

    def test_entry_omits_key_for_not_yet_computable_measure(
        self, ladder_repo: LadderRepository, service: PerformanceService
    ) -> None:
        """Requesting 5Y on an account with under 5 years of history omits the key early on."""
        rows = [
            {"date": d.date(), "sub_account": "Cash", "weighted_position_return": 0.0}
            for d in pd.bdate_range(start=date(2024, 1, 2), periods=10)
        ]
        _write_ladder(ladder_repo, "young", rows)

        response = service.get_performance(
            "young", ["5Y"], date(2024, 1, 2), rows[-1]["date"], TODAY
        )

        for entry in response.entries:
            assert "5Y" not in entry.model_dump()


class TestNoAttributesRaisesNoAttributesRequestedError:
    """Calling get_performance() with an empty attribute list raises NoAttributesRequestedError."""

    def test_no_attributes_raises_no_attributes_requested_error(
        self, ladder_repo: LadderRepository, service: PerformanceService
    ) -> None:
        """An empty attributes list raises before any account lookup is attempted."""
        _write_ladder(
            ladder_repo,
            "known",
            [
                {
                    "date": date(2024, 1, 2),
                    "sub_account": "Cash",
                    "weighted_position_return": 0.0,
                }
            ],
        )

        with pytest.raises(NoAttributesRequestedError):
            service.get_performance("known", [], None, date(2024, 1, 2), TODAY)


class TestUnsupportedAttributeRaisesUnsupportedAttributeError:
    """An unsupported measure name raises UnsupportedAttributeError."""

    def test_unsupported_attribute_raises_unsupported_attribute_error(
        self, ladder_repo: LadderRepository, service: PerformanceService
    ) -> None:
        """A bogus measure name is named in the raised exception's requested list."""
        _write_ladder(
            ladder_repo,
            "known",
            [
                {
                    "date": date(2024, 1, 2),
                    "sub_account": "Cash",
                    "weighted_position_return": 0.0,
                }
            ],
        )

        with pytest.raises(UnsupportedAttributeError) as exc_info:
            service.get_performance("known", ["bogus_measure"], None, date(2024, 1, 2), TODAY)
        assert "bogus_measure" in exc_info.value.requested
