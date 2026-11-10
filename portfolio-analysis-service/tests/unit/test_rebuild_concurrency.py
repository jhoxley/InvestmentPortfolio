"""US2/FR-005: concurrent requests for the same stale gap produce exactly one rebuild (014)."""

import threading
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.clients.market_data_client import MarketDataClient
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


class _SlowFirstCallClient:
    """Wraps a real MarketDataClient, holding its first call open until released.

    Lets a test force two concurrent requests to genuinely race for the same rebuild
    lock: the first caller blocks inside the pricing call (simulating real network
    latency) while a second caller attempts to start a rebuild for the same gap.
    """

    def __init__(self, inner: MarketDataClient, release: threading.Event) -> None:
        """Initialise with the wrapped client and the event that releases the first call.

        Args:
            inner: The real (fake-backed) MarketDataClient to delegate to.
            release: Event the test sets once the second thread has attempted to start.
        """
        self._inner = inner
        self._release = release
        self.call_count = 0
        self._lock = threading.Lock()
        self._first_call_in_flight = threading.Event()

    def get_price_history(
        self, identifier: str, from_date: date, to_date: date, currency: str
    ) -> list[PriceHistoryPoint]:
        """Delegate to the inner client, blocking the first call until released.

        Returns:
            The inner client's price history.
        """
        with self._lock:
            self.call_count += 1
            is_first = self.call_count == 1
        if is_first:
            self._first_call_in_flight.set()
            self._release.wait(timeout=5)
        return self._inner.get_price_history(identifier, from_date, to_date, currency)

    def wait_for_first_call(self) -> None:
        """Block until the first call has started (used by the test to sequence threads)."""
        self._first_call_in_flight.wait(timeout=5)


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


class TestConcurrentRequestsProduceOneRebuild:
    """Two threads requesting the same stale gap trigger exactly one rebuild."""

    def test_concurrent_requests_produce_one_rebuild(
        self,
        ladder_repo: LadderRepository,
        capital_repo: CapitalRepository,
        fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
        fake_market_data_service: FakeMarketDataService,
    ) -> None:
        """Only one thread's call reaches the market-data client; both get the same result."""
        _seed_ladder(ladder_repo, "HL-ISA")
        fake_identifier_mapping_repository.set_entry("Equity A", ticker="EQA.L")
        # Full coverage through _TODAY so the happy path succeeds on the first attempt --
        # this test is about concurrency serialisation, not partial-pricing fallback
        # (covered separately by test_ladder_rebuild_service.py).
        full_coverage = [
            PriceHistoryPoint(date=d.date(), close=50.0 + i)
            for i, d in enumerate(pd.bdate_range(start=date(2026, 9, 24), end=_TODAY))
        ]
        fake_market_data_service.configure_prices("EQA.L", full_coverage)

        release = threading.Event()
        slow_client = _SlowFirstCallClient(fake_market_data_service.client(), release)
        rebuild_lock_registry = RebuildLockRegistry()

        def _build_service() -> TimeSeriesService:
            accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
            mapping_repo = fake_identifier_mapping_repository
            return TimeSeriesService(
                ladder_repo=ladder_repo,
                capital_repo=capital_repo,
                accounts_service=accounts_service,
                date_resolver=TimeseriesDateResolver(),
                ladder_rebuild_service=LadderRebuildService(
                    repository=ladder_repo,
                    mapping_repo=mapping_repo,
                    market_data_client=slow_client,  # type: ignore[arg-type]
                    enrichment_service=PricingEnrichmentService(
                        mapping_repo=mapping_repo,
                        market_data_client=slow_client,  # type: ignore[arg-type]
                    ),
                    returns_service=ReturnsEnrichmentService(),
                ),
                capital_rebuild_service=CapitalRebuildService(capital_repo),
                rebuild_lock_registry=rebuild_lock_registry,
            )

        results: dict[str, object] = {}

        def _request(key: str) -> None:
            service = _build_service()
            response = service.get_series(
                "HL-ISA", ["market_value"], date(2026, 9, 23), date(2026, 9, 25), _TODAY
            )
            results[key] = response

        t1 = threading.Thread(target=_request, args=("first",))
        t1.start()
        slow_client.wait_for_first_call()

        t2 = threading.Thread(target=_request, args=("second",))
        t2.start()
        time.sleep(0.1)  # give t2 a chance to block on the same lock
        release.set()

        t1.join(timeout=5)
        t2.join(timeout=5)

        assert slow_client.call_count == 1, (
            f"Expected exactly one rebuild's worth of market-data calls, got "
            f"{slow_client.call_count}"
        )
        first_entries = [e.model_dump() for e in results["first"].entries]  # type: ignore[attr-defined]
        second_entries = [e.model_dump() for e in results["second"].entries]  # type: ignore[attr-defined]
        assert first_entries == second_entries
