"""HTTP client for calling market-data-web-service's price history endpoint."""

import time
from datetime import date
from typing import Protocol

import httpx
import structlog

from app.exceptions import MarketDataServiceError
from app.models.market_data import PriceHistoryPoint

logger = structlog.get_logger(__name__)


class MarketDataClient(Protocol):
    """Abstraction over the outbound market-data-service price history call."""

    def get_price_history(
        self, identifier: str, from_date: date, to_date: date, currency: str
    ) -> list[PriceHistoryPoint]:
        """Return the price history for an identifier over a date range in a given currency.

        Args:
            identifier: The ticker or ISIN to request prices for.
            from_date: Start of the requested date range (inclusive).
            to_date: End of the requested date range (inclusive).
            currency: The target currency (e.g. "GBP").

        Returns:
            List of PriceHistoryPoint covering the available dates in the range.
        """
        ...


class HttpMarketDataClient:
    """MarketDataClient implementation backed by an HTTP call to market-data-web-service."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Initialise the underlying httpx client.

        Args:
            base_url: Base URL of the market-data-web-service instance.
            timeout_seconds: Request timeout in seconds.
            transport: Optional custom transport (e.g. httpx.MockTransport for tests).
        """
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds, transport=transport)

    def get_price_history(
        self, identifier: str, from_date: date, to_date: date, currency: str
    ) -> list[PriceHistoryPoint]:
        """Request a GBP price history for an identifier from market-data-web-service.

        Args:
            identifier: The ticker or ISIN to request prices for.
            from_date: Start of the requested date range (inclusive).
            to_date: End of the requested date range (inclusive).
            currency: The target currency (e.g. "GBP").

        Returns:
            List of PriceHistoryPoint parsed from the response.

        Raises:
            MarketDataServiceError: On any non-2xx response, timeout, or connection error.
        """
        start = time.perf_counter()
        log = logger.bind(identifier=identifier, from_date=str(from_date), to_date=str(to_date))
        try:
            response = self._client.get(
                f"/securities/{identifier}/history",
                params={"from": str(from_date), "to": str(to_date), "currency": currency},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log.error("market_data_request_failed", duration_ms=duration_ms, detail=str(exc))
            raise MarketDataServiceError(sub_account=identifier, detail=str(exc)) from exc

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        payload = response.json()
        prices = [
            PriceHistoryPoint(date=point["date"], close=point["close"])
            for point in payload.get("prices", [])
        ]
        log.info(
            "market_data_request_succeeded",
            duration_ms=duration_ms,
            point_count=len(prices),
        )
        return prices
