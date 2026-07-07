"""Shared pytest fixtures for the portfolio analysis service test suite."""

import io
from collections.abc import Generator
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.ladder import _get_identifier_mapping_repository, _get_market_data_client
from app.clients.market_data_client import HttpMarketDataClient
from app.config import DataSettings, Settings, get_settings
from app.main import app
from app.models.market_data import IdentifierMappingEntry, PriceHistoryPoint


def _make_settings(data_dir: Path) -> Settings:
    """Create a Settings instance pointing at the given data directory.

    Args:
        data_dir: Temporary directory to use as the data store.

    Returns:
        Settings instance with data.directory overridden.
    """
    return Settings(data=DataSettings(directory=data_dir))


@pytest.fixture()
def app_client(
    tmp_path: Path,
    fake_market_data_service: "FakeMarketDataService",
    fake_identifier_mapping_repository: "FakeIdentifierMappingRepository",
) -> Generator[TestClient, None, None]:
    """Provide a TestClient backed by a temporary data directory.

    Overrides get_settings so that the app writes to tmp_path rather than the real
    data/ directory, and overrides the market-data client / identifier mapping
    repository dependencies with the shared fakes so that ingestion (which now always
    enriches with pricing) works out of the box without per-test market-data setup.
    Tests that need specific pricing behaviour can still configure the same fake
    instances directly via the `fake_market_data_service` / `fake_identifier_mapping_repository`
    fixtures (fixture caching guarantees it's the same instance).

    Args:
        tmp_path: pytest-provided temporary directory.
        fake_market_data_service: Shared fake market-data-service.
        fake_identifier_mapping_repository: Shared fake identifier mapping repository.

    Yields:
        Configured FastAPI TestClient.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    settings = _make_settings(data_dir)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[_get_market_data_client] = lambda: fake_market_data_service.client()
    app.dependency_overrides[_get_identifier_mapping_repository] = lambda: (
        fake_identifier_mapping_repository
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_ledger_df() -> pd.DataFrame:
    """Return a minimal valid sub-account ledger DataFrame.

    Contains two sub-accounts ('Cash' and 'Equity A') over two dates,
    both well before T-2, so the expansion range is non-empty.

    Returns:
        DataFrame with columns: date, sub_account, book_cost, quantity, total_income.
    """
    today = date.today()
    d1 = today - timedelta(days=30)
    d2 = today - timedelta(days=20)
    return pd.DataFrame(
        {
            "date": [d1, d1, d2, d2],
            "sub_account": ["Cash", "Equity A", "Cash", "Equity A"],
            "book_cost": [1000.0, 500.0, 1000.0, 500.0],
            "quantity": [1000.0, 10.0, 1000.0, 10.0],
            "total_income": [0.0, 5.0, 0.0, 10.0],
        }
    )


@pytest.fixture()
def sample_ledger_bytes(sample_ledger_df: pd.DataFrame) -> bytes:
    """Serialise the sample ledger DataFrame to XLSX bytes.

    Args:
        sample_ledger_df: The sample ledger fixture.

    Returns:
        XLSX file contents as bytes.
    """
    buf = io.BytesIO()
    sample_ledger_df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@pytest.fixture()
def sample_ledger_file(sample_ledger_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap XLSX bytes as a multipart file dict for TestClient POSTs.

    Args:
        sample_ledger_bytes: Raw XLSX file bytes.

    Returns:
        Dict suitable for use as the 'files' argument to TestClient.post().
    """
    return {
        "file": (
            "ledger.xlsx",
            sample_ledger_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


class FakeMarketDataService:
    """Shared httpx.MockTransport-backed fake standing in for market-data-web-service.

    By default, returns a flat 100.0 GBP close for every business day (Mon-Fri) in the
    requested range for any identifier. Tests can call `configure_prices()` to return an
    explicit (possibly gapped) price list for a specific identifier, or `configure_error()`
    to simulate an upstream failure.
    """

    def __init__(self) -> None:
        """Initialise with no configured overrides and an empty request log."""
        self.requests: list[httpx.Request] = []
        self._prices: dict[str, list[PriceHistoryPoint]] = {}
        self._errors: dict[str, int] = {}
        self.transport = httpx.MockTransport(self._handle)

    def configure_prices(self, identifier: str, prices: list[PriceHistoryPoint]) -> None:
        """Set an explicit price list to return for a given identifier.

        Args:
            identifier: The ticker or ISIN to configure.
            prices: The exact list of PriceHistoryPoint to return for this identifier,
                regardless of the requested date range (used to simulate gaps).
        """
        self._prices[identifier] = prices

    def configure_error(self, identifier: str, status_code: int = 502) -> None:
        """Configure a given identifier to return an HTTP error response.

        Args:
            identifier: The ticker or ISIN to configure.
            status_code: The HTTP status code to return.
        """
        self._errors[identifier] = status_code

    def calls_for(self, identifier: str) -> list[httpx.Request]:
        """Return every request received for a given identifier.

        Args:
            identifier: The ticker or ISIN to filter requests by.

        Returns:
            List of matching httpx.Request objects, in call order.
        """
        return [r for r in self.requests if r.url.path == f"/securities/{identifier}/history"]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        """Respond to a price-history request, recording it first.

        Args:
            request: The outbound httpx.Request being intercepted.

        Returns:
            A simulated httpx.Response per the configured overrides or the default.
        """
        self.requests.append(request)
        identifier = request.url.path.split("/")[2]
        if identifier in self._errors:
            return httpx.Response(self._errors[identifier], json={"detail": "simulated error"})

        params = request.url.params
        currency = params.get("currency", "GBP")
        if identifier in self._prices:
            prices = self._prices[identifier]
        else:
            from_date = date.fromisoformat(params["from"])
            to_date = date.fromisoformat(params["to"])
            prices = []
            current = from_date
            while current <= to_date:
                if current.weekday() < 5:
                    prices.append(PriceHistoryPoint(date=current, close=100.0))
                current += timedelta(days=1)

        return httpx.Response(
            200,
            json={
                "ticker": identifier,
                "currency": currency,
                "prices": [{"date": p.date.isoformat(), "close": p.close} for p in prices],
            },
        )

    def client(self, timeout_seconds: float = 5.0) -> HttpMarketDataClient:
        """Build an HttpMarketDataClient wired to this fake's mock transport.

        Args:
            timeout_seconds: Timeout to configure on the client.

        Returns:
            An HttpMarketDataClient that routes requests through this fake.
        """
        return HttpMarketDataClient(
            base_url="http://fake-market-data",
            timeout_seconds=timeout_seconds,
            transport=self.transport,
        )


class FakeIdentifierMappingRepository:
    """Shared fake identifier mapping repository for tests.

    Auto-resolves any sub-account name to itself as a ticker by default (so ordinary
    ingestion tests don't need a real mapping file); use `set_entry()`/`set_missing()`
    to override behaviour for specific sub-accounts.
    """

    def __init__(self) -> None:
        """Initialise with no configured overrides."""
        self._overrides: dict[str, IdentifierMappingEntry | None] = {}

    def set_entry(
        self, sub_account: str, *, ticker: str | None = None, isin: str | None = None
    ) -> None:
        """Configure an explicit mapping entry for a sub-account.

        Args:
            sub_account: The sub-account name to configure.
            ticker: The ticker to return, if any.
            isin: The ISIN to return, if any.
        """
        self._overrides[sub_account] = IdentifierMappingEntry(
            name=sub_account, ticker=ticker, isin=isin
        )

    def set_missing(self, sub_account: str) -> None:
        """Configure a sub-account to have no mapping entry at all.

        Args:
            sub_account: The sub-account name to configure as missing.
        """
        self._overrides[sub_account] = None

    def lookup(self, sub_account: str) -> IdentifierMappingEntry | None:
        """Return the configured or default mapping entry for a sub-account.

        Args:
            sub_account: The sub-account name to look up.

        Returns:
            The overridden entry if configured, otherwise a default entry that maps the
            sub-account name to itself as a ticker.
        """
        if sub_account in self._overrides:
            return self._overrides[sub_account]
        return IdentifierMappingEntry(name=sub_account, ticker=sub_account)


@pytest.fixture()
def fake_market_data_service() -> FakeMarketDataService:
    """Provide a shared httpx.MockTransport-backed fake market-data-service.

    Returns:
        A fresh FakeMarketDataService instance for the test.
    """
    return FakeMarketDataService()


@pytest.fixture()
def fake_identifier_mapping_repository() -> FakeIdentifierMappingRepository:
    """Provide a shared fake identifier mapping repository.

    Returns:
        A fresh FakeIdentifierMappingRepository instance for the test.
    """
    return FakeIdentifierMappingRepository()
