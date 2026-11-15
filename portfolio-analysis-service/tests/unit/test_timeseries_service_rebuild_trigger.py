"""Integration test proving TimeSeriesService triggers a rebuild for a stale request (014).

Covers US1's core scenario directly against the reported defect: a request extending past
the last ingested date must return day-by-day varying market pricing, not one repeated
flat-filled value, and must never populate a date beyond the prior business day.
"""

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

_LAST_INGESTED = date(2026, 9, 23)  # Wednesday
_TODAY = date(2026, 11, 10)  # Tuesday -- well past _LAST_INGESTED


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


def _seed_stale_ladder(repo: LadderRepository, account_name: str) -> None:
    """Write a ladder for a single equity sub-account, last known at _LAST_INGESTED.

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


class TestStaleRequestReturnsVaryingMarketPricedValues:
    """A request extending past the last ingested date returns real, varying prices."""

    def test_stale_request_returns_varying_market_priced_values(
        self,
        ladder_repo: LadderRepository,
        service: TimeSeriesService,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """Each new business day's market_value reflects that day's own fetched price."""
        _seed_stale_ladder(ladder_repo, "HL-ISA")
        fake_market_data_service.configure_prices(
            "EQA.L",
            [
                PriceHistoryPoint(date=date(2026, 9, 24), close=51.0),
                PriceHistoryPoint(date=date(2026, 9, 25), close=52.0),
            ],
        )

        response = service.get_series(
            "HL-ISA", ["market_value"], date(2026, 9, 23), date(2026, 9, 25), _TODAY
        )

        by_date = {e.date: e.model_dump()["market_value"] for e in response.entries}
        assert by_date[date(2026, 9, 23)] == pytest.approx(500.0)
        assert by_date[date(2026, 9, 24)] == pytest.approx(51.0 * 10.0)
        assert by_date[date(2026, 9, 25)] == pytest.approx(52.0 * 10.0)
        # The defect being fixed: these must differ, not repeat the stale 500.0 figure.
        assert by_date[date(2026, 9, 24)] != by_date[date(2026, 9, 23)]
        assert by_date[date(2026, 9, 25)] != by_date[date(2026, 9, 24)]

    def test_rebuild_persists_so_the_ladder_meta_advances(
        self, ladder_repo: LadderRepository, service: TimeSeriesService
    ) -> None:
        """After the triggering request, AccountMeta.to_date reflects the rebuild."""
        _seed_stale_ladder(ladder_repo, "HL-ISA")

        service.get_series("HL-ISA", ["market_value"], date(2026, 9, 23), date(2026, 9, 25), _TODAY)

        meta = ladder_repo.read_meta("HL-ISA")
        assert meta.to_date >= date(2026, 9, 25)
        assert meta.rebuilt_at is not None


class TestRebuildNeverProjectsIntoTheFuture:
    """The rebuild is capped at the prior business day relative to today, never beyond."""

    def test_rebuild_target_never_exceeds_prior_business_day(
        self, ladder_repo: LadderRepository, service: TimeSeriesService
    ) -> None:
        """Even with a far-future-looking request, nothing is populated beyond T-1/T-0."""
        _seed_stale_ladder(ladder_repo, "HL-ISA")

        service.get_series("HL-ISA", ["market_value"], date(2026, 9, 23), date(2026, 11, 9), _TODAY)

        meta = ladder_repo.read_meta("HL-ISA")
        assert meta.to_date <= _TODAY
