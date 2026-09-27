"""Unit tests for DailyReturnSeriesLoader: shared account/date/daily-return acquisition."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.exceptions import (
    AccountNotFoundError,
    FutureEndDateError,
    InvalidDateRangeError,
    MissingRequiredSourceError,
)
from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.accounts_service import AccountsService
from app.services.daily_return_series_loader import DailyReturnSeriesLoader
from app.services.timeseries_date_resolver import TimeseriesDateResolver

TODAY = date(2024, 6, 14)  # Friday, well after all fixture dates below


def _write_ladder(repo: LadderRepository, account_name: str, rows: list[dict[str, Any]]) -> None:
    """Write a stored position ladder from explicit rows.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
        rows: Dicts with keys date, sub_account, weighted_position_return.
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


def _write_capital(repo: CapitalRepository, account_name: str) -> None:
    """Write a minimal stored capital ledger for an account.

    Args:
        repo: CapitalRepository to write through.
        account_name: Target account name.
    """
    df = pd.DataFrame(
        [{"date": date(2024, 1, 2), "capital": 100.0, "income": 0.0, "book_value": 100.0}]
    )
    meta = CapitalMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=date(2024, 1, 2),
        to_date=date(2024, 1, 2),
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
def loader(
    ladder_repo: LadderRepository, capital_repo: CapitalRepository
) -> DailyReturnSeriesLoader:
    """Return a loader wired to the tmp_path-backed repositories.

    Returns:
        DailyReturnSeriesLoader ready for use in tests.
    """
    return DailyReturnSeriesLoader(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        date_resolver=TimeseriesDateResolver(),
    )


def _two_day_ladder(ladder_repo: LadderRepository, account: str = "acct") -> None:
    """Write a ladder with two sub-accounts on 2024-01-02 and one on 2024-01-03.

    Args:
        ladder_repo: Repository to write to.
        account: Account name.
    """
    _write_ladder(
        ladder_repo,
        account,
        [
            {"date": date(2024, 1, 2), "sub_account": "A", "weighted_position_return": 0.011},
            {"date": date(2024, 1, 2), "sub_account": "B", "weighted_position_return": -0.0045},
            {"date": date(2024, 1, 3), "sub_account": "A", "weighted_position_return": 0.002},
        ],
    )


class TestLoadReturnsResolvedRangeAndSeries:
    """A known account yields its resolved range and the full daily-return series."""

    def test_returns_resolved_range_and_full_series(
        self, ladder_repo: LadderRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """The series starts at the ladder's first date and runs through the resolved end."""
        _two_day_ladder(ladder_repo)

        result = loader.load("acct", date(2024, 1, 3), date(2024, 1, 5), TODAY, attribute_label="x")

        assert result.resolved_start == date(2024, 1, 3)
        assert result.resolved_end == date(2024, 1, 5)
        # Full series from the ladder's first date, not just the requested window.
        assert list(result.daily_returns["date"]) == [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
        ]

    def test_daily_return_is_sum_of_weighted_position_returns(
        self, ladder_repo: LadderRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """Sub-accounts on the same date are summed."""
        _two_day_ladder(ladder_repo)

        result = loader.load("acct", date(2024, 1, 2), date(2024, 1, 3), TODAY, attribute_label="x")

        assert result.daily_returns["daily_return"].iloc[0] == pytest.approx(0.0065)
        assert result.daily_returns["daily_return"].iloc[1] == pytest.approx(0.002)

    def test_zero_fills_business_days_without_ladder_rows(
        self, ladder_repo: LadderRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """Business days after the last ladder row are 0.0, never forward-filled."""
        _two_day_ladder(ladder_repo)

        result = loader.load("acct", date(2024, 1, 2), date(2024, 1, 5), TODAY, attribute_label="x")

        assert result.daily_returns["daily_return"].iloc[2] == 0.0
        assert result.daily_returns["daily_return"].iloc[3] == 0.0

    def test_defaults_start_and_end_like_the_date_resolver(
        self, ladder_repo: LadderRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """No start/end: start is the ladder's first date, end is the business day before today."""
        _two_day_ladder(ladder_repo)

        result = loader.load("acct", None, None, TODAY, attribute_label="x")

        assert result.resolved_start == date(2024, 1, 2)
        assert result.resolved_end == date(2024, 6, 13)


class TestLoadErrors:
    """Error conditions map to the existing exception vocabulary."""

    def test_unknown_account_raises_account_not_found(
        self, loader: DailyReturnSeriesLoader
    ) -> None:
        """No ledger and no ladder at all."""
        with pytest.raises(AccountNotFoundError):
            loader.load("missing", None, None, TODAY, attribute_label="x")

    def test_capital_only_account_raises_missing_required_source(
        self, capital_repo: CapitalRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """A capital ledger without a ladder cannot produce daily returns."""
        _write_capital(capital_repo, "cap-only")

        with pytest.raises(MissingRequiredSourceError) as exc_info:
            loader.load("cap-only", None, None, TODAY, attribute_label="return-histogram")

        assert exc_info.value.attribute == "return-histogram"
        assert exc_info.value.source == "position_ladder"

    def test_start_before_ladder_raises_missing_required_source(
        self, ladder_repo: LadderRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """A start earlier than the ladder's first date is rejected."""
        _two_day_ladder(ladder_repo)

        with pytest.raises(MissingRequiredSourceError) as exc_info:
            loader.load("acct", date(2023, 12, 1), date(2024, 1, 3), TODAY, attribute_label="1Y")

        assert exc_info.value.attribute == "1Y"

    def test_future_end_raises_future_end_date_error(
        self, ladder_repo: LadderRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """An end after today is rejected by the shared date resolver."""
        _two_day_ladder(ladder_repo)

        with pytest.raises(FutureEndDateError):
            loader.load("acct", None, date(2024, 6, 15), TODAY, attribute_label="x")

    def test_start_after_end_raises_invalid_date_range(
        self, ladder_repo: LadderRepository, loader: DailyReturnSeriesLoader
    ) -> None:
        """A start after the end is rejected by the shared date resolver."""
        _two_day_ladder(ladder_repo)

        with pytest.raises(InvalidDateRangeError):
            loader.load("acct", date(2024, 1, 5), date(2024, 1, 3), TODAY, attribute_label="x")
