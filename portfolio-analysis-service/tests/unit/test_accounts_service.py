"""Unit tests for AccountsService account existence and date-range lookup."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.accounts_service import AccountsService


def _write_ladder(
    repo: LadderRepository, account_name: str, from_date: date, to_date: date
) -> None:
    """Write a minimal stored ladder for an account.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
        from_date: Earliest date to record in meta.
        to_date: Latest date to record in meta.
    """
    df = pd.DataFrame(
        {
            "date": [from_date],
            "sub_account": ["Cash"],
            "book_cost": [100.0],
            "quantity": [100.0],
            "total_income": [0.0],
            "price": [1.0],
            "market_value": [100.0],
            "portfolio_weight": [1.0],
        }
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=from_date,
        to_date=to_date,
        sub_accounts=["Cash"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


def _write_capital(
    repo: CapitalRepository, account_name: str, from_date: date, to_date: date
) -> None:
    """Write a minimal stored capital ledger for an account.

    Args:
        repo: CapitalRepository to write through.
        account_name: Target account name.
        from_date: Earliest date to record in meta.
        to_date: Latest date to record in meta.
    """
    df = pd.DataFrame(
        {"date": [from_date], "capital": [1000.0], "income": [0.0], "book_value": [900.0]}
    )
    meta = CapitalMeta(
        account_name=account_name,
        checksum="cafebabe",
        row_count=1,
        from_date=from_date,
        to_date=to_date,
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
def accounts_service(
    ladder_repo: LadderRepository, capital_repo: CapitalRepository
) -> AccountsService:
    """Return an AccountsService wired to the tmp_path-backed repositories.

    Returns:
        AccountsService ready for use in tests.
    """
    return AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)


class TestListKnownAccountsIsUnionOfBothRepositories:
    """Tests that list_known_accounts() unions both repositories' accounts."""

    def test_list_known_accounts_is_union_of_both_repositories(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        accounts_service: AccountsService,
    ) -> None:
        """An account known to only one repository still appears in the union."""
        _write_ladder(ladder_repo, "ladder-only", date(2024, 1, 2), date(2024, 1, 10))
        _write_capital(capital_repo, "capital-only", date(2024, 1, 2), date(2024, 1, 10))
        _write_ladder(ladder_repo, "both", date(2024, 1, 2), date(2024, 1, 10))
        _write_capital(capital_repo, "both", date(2024, 1, 2), date(2024, 1, 10))

        result = accounts_service.list_known_accounts()

        assert result == ["both", "capital-only", "ladder-only"]


class TestGetSummaryIncludesBothResourcesWhenBothIngested:
    """Tests that get_summary() reports both resources when both are ingested."""

    def test_get_summary_includes_both_resources_when_both_ingested(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        accounts_service: AccountsService,
    ) -> None:
        """Both capital_ledger and position_ladder are populated when both exist."""
        _write_ladder(ladder_repo, "dual", date(2024, 1, 2), date(2024, 6, 1))
        _write_capital(capital_repo, "dual", date(2024, 1, 3), date(2024, 5, 1))

        summary = accounts_service.get_summary("dual")

        assert summary.account_name == "dual"
        assert summary.position_ladder is not None
        assert summary.position_ladder.from_date == date(2024, 1, 2)
        assert summary.position_ladder.to_date == date(2024, 6, 1)
        assert summary.capital_ledger is not None
        assert summary.capital_ledger.from_date == date(2024, 1, 3)
        assert summary.capital_ledger.to_date == date(2024, 5, 1)


class TestGetSummaryHasNoneCapitalLedgerWhenOnlyLadderIngested:
    """Tests that get_summary() leaves capital_ledger None when absent."""

    def test_get_summary_has_none_capital_ledger_when_only_ladder_ingested(
        self, ladder_repo: LadderRepository, accounts_service: AccountsService
    ) -> None:
        """capital_ledger is None when no capital ledger has been ingested."""
        _write_ladder(ladder_repo, "ladder-only", date(2024, 1, 2), date(2024, 1, 10))

        summary = accounts_service.get_summary("ladder-only")

        assert summary.position_ladder is not None
        assert summary.capital_ledger is None


class TestGetSummaryHasNonePositionLadderWhenOnlyCapitalIngested:
    """Tests that get_summary() leaves position_ladder None when absent."""

    def test_get_summary_has_none_position_ladder_when_only_capital_ingested(
        self, capital_repo: CapitalRepository, accounts_service: AccountsService
    ) -> None:
        """position_ladder is None when no position ladder has been ingested."""
        _write_capital(capital_repo, "capital-only", date(2024, 1, 2), date(2024, 1, 10))

        summary = accounts_service.get_summary("capital-only")

        assert summary.capital_ledger is not None
        assert summary.position_ladder is None


class TestListSummariesCoversEveryKnownAccount:
    """Tests that list_summaries() returns one summary per known account."""

    def test_list_summaries_covers_every_known_account(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        accounts_service: AccountsService,
    ) -> None:
        """Every account with at least one ingested resource appears exactly once."""
        _write_ladder(ladder_repo, "a", date(2024, 1, 2), date(2024, 1, 10))
        _write_capital(capital_repo, "b", date(2024, 1, 2), date(2024, 1, 10))

        summaries = accounts_service.list_summaries()

        names = [s.account_name for s in summaries]
        assert names == ["a", "b"]
