"""Unit tests for HttpMarketDataClient.get_observed_price_history()."""

from datetime import date

import httpx
import pytest

from app.clients.market_data_client import HttpMarketDataClient
from app.exceptions import (
    InstrumentNotFoundError,
    MarketDataServiceError,
    ObservedHistoryUnsupportedError,
)


def _client(handler: httpx.MockTransport) -> HttpMarketDataClient:
    return HttpMarketDataClient(
        base_url="http://market-data.test",
        timeout_seconds=5.0,
        transport=handler,
    )


class TestGetObservedPriceHistory:
    """get_observed_price_history() sends fill=none and parses the observed-history fields."""

    def test_sends_fill_none_and_currency(self) -> None:
        """The request carries fill=none and the response is parsed into ObservedPriceHistory."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "ticker": "EQA.L",
                    "currency": "GBP",
                    "prices": [{"date": "2026-03-02", "close": 100.0}],
                    "first_observed_date": "2020-01-02",
                    "last_observed_date": "2026-09-22",
                },
            )

        result = _client(httpx.MockTransport(handler)).get_observed_price_history(
            "EQA.L", date(2026, 3, 1), date(2026, 3, 2), "GBP"
        )

        assert len(captured) == 1
        params = captured[0].url.params
        assert params["fill"] == "none"
        assert params["currency"] == "GBP"
        assert params["from"] == "2026-03-01"
        assert params["to"] == "2026-03-02"
        assert len(result.points) == 1
        assert result.points[0].close == 100.0
        assert result.first_observed_date == date(2020, 1, 2)
        assert result.last_observed_date == date(2026, 9, 22)

    def test_empty_prices_with_observed_dates_is_valid(self) -> None:
        """An empty points list alongside known observation dates is not an error."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "ticker": "EQA.L",
                    "currency": "GBP",
                    "prices": [],
                    "first_observed_date": "2020-01-02",
                    "last_observed_date": "2026-09-22",
                },
            )

        result = _client(httpx.MockTransport(handler)).get_observed_price_history(
            "EQA.L", date(2026, 3, 1), date(2026, 3, 2), "GBP"
        )
        assert result.points == []

    def test_missing_observed_date_fields_is_unsupported(self) -> None:
        """A response with no observation-window keys at all means the service predates feature 009."""

        def handler(_request: httpx.Request) -> httpx.Response:
            # Old market-data-service: no observation-window fields at all.
            return httpx.Response(
                200,
                json={
                    "ticker": "EQA.L",
                    "currency": "GBP",
                    "prices": [{"date": "2026-03-02", "close": 100.0}],
                },
            )

        with pytest.raises(ObservedHistoryUnsupportedError):
            _client(httpx.MockTransport(handler)).get_observed_price_history(
                "EQA.L", date(2026, 3, 1), date(2026, 3, 2), "GBP"
            )

    def test_null_observed_dates_are_not_unsupported(self) -> None:
        """Null observation dates, with the keys present, are a valid 'nothing known yet' response."""

        # A supporting service may legitimately report null observation dates
        # for an identifier it knows nothing about yet -- the KEY is present.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "ticker": "EQA.L",
                    "currency": "GBP",
                    "prices": [],
                    "first_observed_date": None,
                    "last_observed_date": None,
                },
            )

        result = _client(httpx.MockTransport(handler)).get_observed_price_history(
            "EQA.L", date(2026, 3, 1), date(2026, 3, 2), "GBP"
        )
        assert result.first_observed_date is None
        assert result.points == []

    def test_404_raises_instrument_not_found(self) -> None:
        """A 404 response raises InstrumentNotFoundError."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "not found"})

        with pytest.raises(InstrumentNotFoundError):
            _client(httpx.MockTransport(handler)).get_observed_price_history(
                "UNKNOWN", date(2026, 3, 1), date(2026, 3, 2), "GBP"
            )

    def test_500_raises_market_data_service_error(self) -> None:
        """A 500 response raises MarketDataServiceError."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "boom"})

        with pytest.raises(MarketDataServiceError):
            _client(httpx.MockTransport(handler)).get_observed_price_history(
                "EQA.L", date(2026, 3, 1), date(2026, 3, 2), "GBP"
            )

    def test_timeout_raises_market_data_service_error(self) -> None:
        """A read timeout raises MarketDataServiceError."""

        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        with pytest.raises(MarketDataServiceError):
            _client(httpx.MockTransport(handler)).get_observed_price_history(
                "EQA.L", date(2026, 3, 1), date(2026, 3, 2), "GBP"
            )

    def test_connection_error_raises_market_data_service_error(self) -> None:
        """A connection error raises MarketDataServiceError."""

        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        with pytest.raises(MarketDataServiceError):
            _client(httpx.MockTransport(handler)).get_observed_price_history(
                "EQA.L", date(2026, 3, 1), date(2026, 3, 2), "GBP"
            )
