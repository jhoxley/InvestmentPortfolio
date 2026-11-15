"""US2: a rebuild triggered by one request is not repeated by a subsequent one (014)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.models.market_data import PriceHistoryPoint
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.accounts_service import AccountsService
from app.services.pricing_enrichment_service import PricingEnrichmentService
from app.services.rebuild.capital_rebuild_service import CapitalRebuildService
from app.services.rebuild.ladder_rebuild_service import LadderRebuildService
from app.services.rebuild.rebuild_lock_registry import RebuildLockRegistry
from app.services.returns_enrichment_service import ReturnsEnrichmentService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.services.timeseries_service import TimeSeriesService
from tests.conftest import FakeIdentifierMappingRepository, FakeMarketDataService

_LAST_INGESTED = date(2026, 9, 23)
_TODAY = date(2026, 11, 10)


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


def _seed_ladder(repo: LadderRepository, account_name: str) -> None:
    """Write a minimal stale ladder for a single equity sub-account.

    Args:
        repo: LadderRepository to write through.
        account_name: Target account name.
    """
    df = pd.DataFrame(
        {
            "date": [_LAST_INGESTED],
            "sub_account": ["Equity A"],
            "book_cost": [500.0],
            "quantity": [10.0],
            "total_income": [0.0],
            "price": [50.0],
            "market_value": [500.0],
            "portfolio_weight": [1.0],
            "position_return": [0.0],
            "weighted_position_return": [0.0],
            "provenance": ["ingested"],
        }
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=_LAST_INGESTED,
        to_date=_LAST_INGESTED,
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


@pytest.fixture()
def service(
    ladder_repo: LadderRepository,
    capital_repo: CapitalRepository,
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
    fake_market_data_service: FakeMarketDataService,
) -> TimeSeriesService:
    """Return a TimeSeriesService wired to the tmp_path-backed repositories and fakes.

    Returns:
        TimeSeriesService ready for use in tests.
    """
    fake_identifier_mapping_repository.set_entry("Equity A", ticker="EQA.L")
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    mapping_repo = fake_identifier_mapping_repository
    market_data_client = fake_market_data_service.client()
    return TimeSeriesService(
        ladder_repo=ladder_repo,
        capital_repo=capital_repo,
        accounts_service=accounts_service,
        date_resolver=TimeseriesDateResolver(),
        ladder_rebuild_service=LadderRebuildService(
            repository=ladder_repo,
            mapping_repo=mapping_repo,
            market_data_client=market_data_client,
            enrichment_service=PricingEnrichmentService(
                mapping_repo=mapping_repo, market_data_client=market_data_client
            ),
            returns_service=ReturnsEnrichmentService(),
        ),
        capital_rebuild_service=CapitalRebuildService(capital_repo),
        rebuild_lock_registry=RebuildLockRegistry(),
    )


class TestSecondRequestDoesNotRepeatTheRebuild:
    """A second call for an already-rebuilt range makes no new market-data calls."""

    def test_second_request_makes_no_new_market_data_calls(
        self,
        ladder_repo: LadderRepository,
        service: TimeSeriesService,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """The fake market-data client is called on the first request only."""
        _seed_ladder(ladder_repo, "HL-ISA")
        fake_market_data_service.configure_prices(
            "EQA.L",
            [
                PriceHistoryPoint(date=date(2026, 9, 24), close=51.0),
                PriceHistoryPoint(date=date(2026, 9, 25), close=52.0),
            ],
        )

        first = service.get_series(
            "HL-ISA", ["market_value"], date(2026, 9, 23), date(2026, 9, 25), _TODAY
        )
        calls_after_first = len(fake_market_data_service.calls_for("EQA.L"))
        assert calls_after_first > 0

        second = service.get_series(
            "HL-ISA", ["market_value"], date(2026, 9, 23), date(2026, 9, 25), _TODAY
        )
        calls_after_second = len(fake_market_data_service.calls_for("EQA.L"))

        assert calls_after_second == calls_after_first, (
            "Second request must not trigger any new market-data calls"
        )
        assert [e.model_dump() for e in first.entries] == [e.model_dump() for e in second.entries]
