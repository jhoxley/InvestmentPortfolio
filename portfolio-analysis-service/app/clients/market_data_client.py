"""HTTP client for calling market-data-web-service's price history endpoint."""

import time
from datetime import date
from typing import Protocol

import httpx
import structlog

from app.exceptions import (
    InstrumentNotFoundError,
    MarketDataServiceError,
    ObservedHistoryUnsupportedError,
)
from app.models.market_data import ObservedPriceHistory, PriceHistoryPoint

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


class ObservedPriceClient(Protocol):
    """Abstraction over the outbound market-data-service observed-only (fill=none) call.

    Kept separate from MarketDataClient (Interface Segregation): VaR calculation is the
    only caller that needs observed-only history, and this lets ladder pricing's fakes
    stay unaffected by this capability.
    """

    def get_observed_price_history(
        self, identifier: str, from_date: date, to_date: date, currency: str
    ) -> ObservedPriceHistory:
        """Return only real market observations for an identifier, never gap-filled.

        Args:
            identifier: The ticker or ISIN to request prices for.
            from_date: Start of the requested date range (inclusive).
            to_date: End of the requested date range (inclusive).
            currency: The target currency (e.g. "GBP").

        Returns:
            ObservedPriceHistory with only observed points plus the instrument's known
            observation window.

        Raises:
            ObservedHistoryUnsupportedError: If the service does not support fill=none
                (its response carries no observation-window fields at all).
            InstrumentNotFoundError: If the service has no price history at all for the
                identifier (404).
            MarketDataServiceError: On any other non-2xx response, timeout, or connection
                error.
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

    def get_observed_price_history(
        self, identifier: str, from_date: date, to_date: date, currency: str
    ) -> ObservedPriceHistory:
        """Request observed-only (fill=none) price history for an identifier.

        Args:
            identifier: The ticker or ISIN to request prices for.
            from_date: Start of the requested date range (inclusive).
            to_date: End of the requested date range (inclusive).
            currency: The target currency (e.g. "GBP").

        Returns:
            ObservedPriceHistory parsed from the response.

        Raises:
            ObservedHistoryUnsupportedError: If the response has no observation-window
                fields (first_observed_date/last_observed_date absent), meaning the
                service does not support fill=none.
            InstrumentNotFoundError: If the response is 404.
            MarketDataServiceError: On any other non-2xx response, timeout, or connection
                error.
        """
        start = time.perf_counter()
        log = logger.bind(identifier=identifier, from_date=str(from_date), to_date=str(to_date))
        try:
            response = self._client.get(
                f"/securities/{identifier}/history",
                params={
                    "from": str(from_date),
                    "to": str(to_date),
                    "currency": currency,
                    "fill": "none",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            if exc.response.status_code == 404:
                log.warning("observed_history_not_found", duration_ms=duration_ms)
                raise InstrumentNotFoundError(identifier=identifier) from exc
            log.error("market_data_request_failed", duration_ms=duration_ms, detail=str(exc))
            raise MarketDataServiceError(sub_account=identifier, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log.error("market_data_request_failed", duration_ms=duration_ms, detail=str(exc))
            raise MarketDataServiceError(sub_account=identifier, detail=str(exc)) from exc

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        payload = response.json()
        if "first_observed_date" not in payload or "last_observed_date" not in payload:
            log.error("observed_history_unsupported", duration_ms=duration_ms)
            raise ObservedHistoryUnsupportedError(identifier=identifier)

        points = [
            PriceHistoryPoint(date=point["date"], close=point["close"])
            for point in payload.get("prices", [])
        ]
        result = ObservedPriceHistory(
            points=points,
            first_observed_date=payload["first_observed_date"],
            last_observed_date=payload["last_observed_date"],
        )
        log.info(
            "observed_history_request_succeeded",
            duration_ms=duration_ms,
            point_count=len(points),
            first_observed_date=str(result.first_observed_date),
            last_observed_date=str(result.last_observed_date),
        )
        return result
