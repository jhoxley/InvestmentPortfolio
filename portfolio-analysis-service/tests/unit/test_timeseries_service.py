"""Unit tests for TimeSeriesService join, aggregation, and pnl computation."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.exceptions import MissingRequiredSourceError
from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.accounts_service import AccountsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.services.timeseries_service import TimeSeriesService

TODAY = date(2024, 6, 14)  # Friday, well after all fixture dates below


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


def _write_ladder(repo: LadderRepository, account_name: str, rows: list[dict]) -> None:
    """Write a stored position ladder for an account from explicit rows.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
        rows: List of dicts with keys date, sub_account, market_value (other columns filled
            with placeholder values).
    """
    df = pd.DataFrame(
        [
            {
                "date": r["date"],
                "sub_account": r["sub_account"],
                "book_cost": r.get("market_value", 0.0),
                "quantity": 1.0,
                "total_income": 0.0,
                "price": 1.0,
                "market_value": r["market_value"],
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
        to_date=df["date"].max(),
        sub_accounts=sorted(df["sub_account"].unique().tolist()),
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
def service(ladder_repo: LadderRepository, capital_repo: CapitalRepository) -> TimeSeriesService:
    """Return a TimeSeriesService wired to the tmp_path-backed repositories.

    Returns:
        TimeSeriesService ready for use in tests.
    """
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return TimeSeriesService(
        ladder_repo=ladder_repo,
        capital_repo=capital_repo,
        accounts_service=accounts_service,
        date_resolver=TimeseriesDateResolver(),
    )


class TestJoinsCapitalAndMarketValueByDate:
    """Requesting attributes from both sources joins them correctly by date."""

    def test_joins_capital_and_market_value_by_date(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        service: TimeSeriesService,
    ) -> None:
        """Each entry carries both the capital value and the summed market value for that date."""
        _write_capital(
            capital_repo,
            "dual",
            [
                {"date": date(2024, 1, 2), "capital": 1000.0, "income": 0.0, "book_value": 800.0},
                {"date": date(2024, 1, 3), "capital": 1100.0, "income": 10.0, "book_value": 850.0},
            ],
        )
        _write_ladder(
            ladder_repo,
            "dual",
            [
                {"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 200.0},
                {"date": date(2024, 1, 2), "sub_account": "Equity A", "market_value": 600.0},
                {"date": date(2024, 1, 3), "sub_account": "Cash", "market_value": 200.0},
                {"date": date(2024, 1, 3), "sub_account": "Equity A", "market_value": 650.0},
            ],
        )

        response = service.get_series(
            "dual", ["capital", "market_value"], None, date(2024, 1, 3), TODAY
        )

        by_date = {e.date: e for e in response.entries}
        assert by_date[date(2024, 1, 2)].model_dump()["capital"] == 1000.0
        assert by_date[date(2024, 1, 2)].model_dump()["market_value"] == 800.0
        assert by_date[date(2024, 1, 3)].model_dump()["market_value"] == 850.0


class TestPnlEqualsIncomePlusMarketValueMinusBookCost:
    """pnl is computed correctly from the three underlying components."""

    def test_pnl_equals_income_plus_market_value_minus_book_cost(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        service: TimeSeriesService,
    ) -> None:
        """Pnl = income + market_value - book_cost for each entry."""
        _write_capital(
            capital_repo,
            "dual",
            [{"date": date(2024, 1, 2), "capital": 1000.0, "income": 50.0, "book_value": 800.0}],
        )
        _write_ladder(
            ladder_repo,
            "dual",
            [{"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 900.0}],
        )

        response = service.get_series("dual", ["pnl"], None, date(2024, 1, 2), TODAY)

        entry = response.entries[0].model_dump()
        assert entry["pnl"] == pytest.approx(50.0 + 900.0 - 800.0)


class TestForwardFillsPastCapitalLedgersOwnLatestDate:
    """The capital-derived attributes forward-fill past the capital ledger's own latest date."""

    def test_forward_fills_past_capital_ledgers_own_latest_date(
        self, capital_repo: CapitalRepository, service: TimeSeriesService
    ) -> None:
        """Requesting an end date beyond the capital ledger's to_date carries the last value."""
        _write_capital(
            capital_repo,
            "capital-only",
            [{"date": date(2024, 1, 2), "capital": 1000.0, "income": 0.0, "book_value": 800.0}],
        )

        response = service.get_series(
            "capital-only", ["capital"], date(2024, 1, 2), date(2024, 1, 5), TODAY
        )

        by_date = {e.date: e.model_dump()["capital"] for e in response.entries}
        assert by_date[date(2024, 1, 5)] == 1000.0


class TestForwardFillsPastLaddersOwnLatestDate:
    """market_value forward-fills past the position ladder's own latest date."""

    def test_forward_fills_past_ladders_own_latest_date(
        self, ladder_repo: LadderRepository, service: TimeSeriesService
    ) -> None:
        """Requesting an end date beyond the ladder's to_date carries the last summed value."""
        _write_ladder(
            ladder_repo,
            "ladder-only",
            [{"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 500.0}],
        )

        response = service.get_series(
            "ladder-only", ["market_value"], date(2024, 1, 2), date(2024, 1, 5), TODAY
        )

        by_date = {e.date: e.model_dump()["market_value"] for e in response.entries}
        assert by_date[date(2024, 1, 5)] == 500.0


class TestMarketValueRequestedOnLadderOnlyAccountSucceeds:
    """market_value alone does not require a capital ledger to exist."""

    def test_market_value_requested_on_ladder_only_account_succeeds(
        self, ladder_repo: LadderRepository, service: TimeSeriesService
    ) -> None:
        """A ladder-only account can serve market_value without error."""
        _write_ladder(
            ladder_repo,
            "ladder-only",
            [{"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 500.0}],
        )

        response = service.get_series(
            "ladder-only", ["market_value"], date(2024, 1, 2), date(2024, 1, 2), TODAY
        )

        assert len(response.entries) == 1


class TestCapitalRequestedOnLadderOnlyAccountRaises:
    """capital requires the capital ledger, absent on a ladder-only account."""

    def test_capital_requested_on_ladder_only_account_raises_missing_required_source_error(
        self, ladder_repo: LadderRepository, service: TimeSeriesService
    ) -> None:
        """Requesting capital on a ladder-only account raises MissingRequiredSourceError."""
        _write_ladder(
            ladder_repo,
            "ladder-only",
            [{"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 500.0}],
        )

        with pytest.raises(MissingRequiredSourceError):
            service.get_series("ladder-only", ["capital"], None, date(2024, 1, 2), TODAY)


class TestPnlRequestedWithOnlyOneSourceRaises:
    """pnl requires both sources; a single-source account raises."""

    def test_pnl_requested_with_only_one_source_raises_missing_required_source_error(
        self, capital_repo: CapitalRepository, service: TimeSeriesService
    ) -> None:
        """Requesting pnl on a capital-only account raises MissingRequiredSourceError."""
        _write_capital(
            capital_repo,
            "capital-only",
            [{"date": date(2024, 1, 2), "capital": 1000.0, "income": 0.0, "book_value": 800.0}],
        )

        with pytest.raises(MissingRequiredSourceError):
            service.get_series("capital-only", ["pnl"], None, date(2024, 1, 2), TODAY)


class TestStartBeforeRequiredSourcesEarliestDateRaises:
    """An explicit start earlier than a required source's earliest date raises."""

    def test_start_before_required_sources_earliest_date_raises_missing_required_source_error(
        self, capital_repo: CapitalRepository, service: TimeSeriesService
    ) -> None:
        """A start before the capital ledger's own from_date raises MissingRequiredSourceError."""
        _write_capital(
            capital_repo,
            "capital-only",
            [{"date": date(2024, 1, 10), "capital": 1000.0, "income": 0.0, "book_value": 800.0}],
        )

        with pytest.raises(MissingRequiredSourceError):
            service.get_series(
                "capital-only", ["capital"], date(2024, 1, 2), date(2024, 1, 10), TODAY
            )


class TestResponseEntriesContainOnlyRequestedAttributeKeys:
    """Entries never carry keys for attributes that weren't requested."""

    def test_response_entries_contain_only_requested_attribute_keys(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        service: TimeSeriesService,
    ) -> None:
        """Only 'capital' (plus date) appears when only 'capital' was requested."""
        _write_capital(
            capital_repo,
            "dual",
            [{"date": date(2024, 1, 2), "capital": 1000.0, "income": 0.0, "book_value": 800.0}],
        )
        _write_ladder(
            ladder_repo,
            "dual",
            [{"date": date(2024, 1, 2), "sub_account": "Cash", "market_value": 900.0}],
        )

        response = service.get_series(
            "dual", ["capital"], date(2024, 1, 2), date(2024, 1, 2), TODAY
        )

        keys = set(response.entries[0].model_dump().keys())
        assert keys == {"date", "capital"}
