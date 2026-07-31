"""Unit tests for HttpPortfolioAnalysisClient, stubbed via httpx.MockTransport.

No real portfolio-analysis-service instance is used — every request is
answered by a hand-built transport, mirroring the pattern already proven in
portfolio-analysis-service/app/clients/market_data_client.py.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from src.exceptions import PortfolioAnalysisServiceError
from src.services.portfolio_analysis_client import HttpPortfolioAnalysisClient

BASE_URL = "http://testserver"


def _client(transport: httpx.MockTransport) -> HttpPortfolioAnalysisClient:
    return HttpPortfolioAnalysisClient(
        base_url=BASE_URL, timeout_seconds=5.0, transport=transport
    )


def test_list_accounts_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/accounts"
        return httpx.Response(
            200,
            json={
                "accounts": [
                    {
                        "account_name": "HL-SIPP",
                        "capital_ledger": {
                            "from_date": "2016-04-20",
                            "to_date": "2026-06-01",
                        },
                        "position_ladder": {
                            "from_date": "2016-04-20",
                            "to_date": "2026-07-08",
                        },
                    },
                    {
                        "account_name": "capital-only-portfolio",
                        "capital_ledger": {
                            "from_date": "2020-01-02",
                            "to_date": "2020-06-01",
                        },
                        "position_ladder": None,
                    },
                ],
                "_links": {"self": "/v1/accounts"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    accounts = client.list_accounts()

    assert [a.account_name for a in accounts] == ["HL-SIPP", "capital-only-portfolio"]
    assert accounts[0].capital_ledger is not None
    assert accounts[0].capital_ledger.from_date == date(2016, 4, 20)
    assert accounts[1].position_ladder is None


def test_list_attributes_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/timeseries/attributes"
        return httpx.Response(
            200,
            json={
                "attributes": [
                    {
                        "name": "market_value",
                        "description": "The market value on that date.",
                        "source": "position_ladder",
                    },
                    {
                        "name": "capital",
                        "description": "The capital value on that date.",
                        "source": "capital_ledger",
                    },
                ],
                "_links": {"self": "/v1/timeseries/attributes"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    attributes = client.list_attributes()

    assert [a.name for a in attributes] == ["market_value", "capital"]
    assert attributes[0].description == "The market value on that date."


def test_get_timeseries_success_sends_repeated_attribute_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/accounts/HL-SIPP/timeseries"
        params = httpx.QueryParams(request.url.query)
        assert params.get_list("attribute") == ["capital", "market_value"]
        assert params.get("start") == "2024-01-02"
        assert params.get("end") == "2024-01-10"
        return httpx.Response(
            200,
            json={
                "account_name": "HL-SIPP",
                "attributes": ["capital", "market_value"],
                "from_date": "2024-01-02",
                "to_date": "2024-01-10",
                "entries": [
                    {"date": "2024-01-02", "capital": 236634.5, "market_value": 240120.11},
                ],
                "_links": {"self": "/v1/accounts/HL-SIPP/timeseries"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    response = client.get_timeseries(
        account_name="HL-SIPP",
        attributes=["capital", "market_value"],
        start=date(2024, 1, 2),
        end=date(2024, 1, 10),
    )

    assert response.account_name == "HL-SIPP"
    assert len(response.entries) == 1
    assert response.entries[0].model_dump()["market_value"] == 240120.11


@pytest.mark.parametrize("status_code", [404, 422])
def test_get_timeseries_raises_on_error_status(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "type": "about:blank",
                "title": "Error",
                "status": status_code,
                "detail": "boom",
                "instance": str(request.url),
            },
        )

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.get_timeseries(
            account_name="HL-SIPP",
            attributes=["market_value"],
            start=date(2024, 1, 2),
            end=date(2024, 1, 10),
        )


def test_get_timeseries_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.get_timeseries(
            account_name="HL-SIPP",
            attributes=["market_value"],
            start=date(2024, 1, 2),
            end=date(2024, 1, 10),
        )


def test_get_timeseries_raises_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.get_timeseries(
            account_name="HL-SIPP",
            attributes=["market_value"],
            start=date(2024, 1, 2),
            end=date(2024, 1, 10),
        )


def test_list_account_positions_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/accounts/HL-SIPP/positions"
        return httpx.Response(
            200,
            json={
                "account_name": "HL-SIPP",
                "positions": [
                    {"position": "Apple Inc", "from_date": "2020-03-02", "to_date": "2026-07-08"},
                    {"position": "Cash", "from_date": "2016-04-20", "to_date": "2026-07-08"},
                ],
                "_links": {"self": "/v1/accounts/HL-SIPP/positions"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    positions = client.list_account_positions(account_name="HL-SIPP")

    assert [p.position for p in positions] == ["Apple Inc", "Cash"]
    assert positions[0].from_date == date(2020, 3, 2)


def test_list_position_attributes_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/positions/attributes"
        return httpx.Response(
            200,
            json={
                "attributes": [
                    {
                        "name": "market_value",
                        "description": "The position's market value on that date.",
                        "source": "position_ladder",
                    },
                    {
                        "name": "quantity",
                        "description": "The position's quantity on that date.",
                        "source": "position_ladder",
                    },
                ],
                "_links": {"self": "/v1/positions/attributes"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    attributes = client.list_position_attributes()

    assert [a.name for a in attributes] == ["market_value", "quantity"]


def test_get_position_timeseries_sends_explicit_position_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/accounts/HL-SIPP/position"
        params = httpx.QueryParams(request.url.query)
        assert params.get_list("position") == ["Apple Inc", "Cash"]
        assert params.get_list("attribute") == ["market_value", "quantity"]
        assert params.get("start") == "2024-01-02"
        assert params.get("end") == "2024-01-10"
        return httpx.Response(
            200,
            json={
                "account_name": "HL-SIPP",
                "attributes": ["market_value", "quantity"],
                "positions": ["Apple Inc", "Cash"],
                "from_date": "2024-01-02",
                "to_date": "2024-01-10",
                "entries": [
                    {
                        "date": "2024-01-02",
                        "position": "Apple Inc",
                        "market_value": 5000.0,
                        "quantity": 25.0,
                    },
                ],
                "_links": {"self": "/v1/accounts/HL-SIPP/position"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    response = client.get_position_timeseries(
        account_name="HL-SIPP",
        positions=["Apple Inc", "Cash"],
        attributes=["market_value", "quantity"],
        start=date(2024, 1, 2),
        end=date(2024, 1, 10),
    )

    assert response.account_name == "HL-SIPP"
    assert len(response.entries) == 1
    assert response.entries[0].position == "Apple Inc"
    assert response.entries[0].model_dump()["market_value"] == 5000.0


@pytest.mark.parametrize("status_code", [404, 422])
def test_get_position_timeseries_raises_on_error_status(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "type": "about:blank",
                "title": "Error",
                "status": status_code,
                "detail": "boom",
                "instance": str(request.url),
            },
        )

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.get_position_timeseries(
            account_name="HL-SIPP",
            positions=["Apple Inc"],
            attributes=["market_value"],
            start=date(2024, 1, 2),
            end=date(2024, 1, 10),
        )


def test_list_account_positions_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.list_account_positions(account_name="HL-SIPP")


def test_list_performance_attributes_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/performance/attributes"
        return httpx.Response(
            200,
            json={
                "attributes": [
                    {
                        "name": "ITD",
                        "description": "Inception to Date return.",
                        "source": "position_ladder",
                    },
                    {
                        "name": "1Y",
                        "description": "Trailing 1-year return.",
                        "source": "position_ladder",
                    },
                ],
                "_links": {"self": "/v1/performance/attributes"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    attributes = client.list_performance_attributes()

    assert [a.name for a in attributes] == ["ITD", "1Y"]
    assert attributes[0].description == "Inception to Date return."


def test_get_performance_success_sends_repeated_attribute_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/accounts/HL-SIPP/performance"
        params = httpx.QueryParams(request.url.query)
        assert params.get_list("attribute") == ["ITD", "1Y"]
        assert params.get("start") == "2024-01-02"
        assert params.get("end") == "2024-01-10"
        return httpx.Response(
            200,
            json={
                "account_name": "HL-SIPP",
                "attributes": ["ITD", "1Y"],
                "from_date": "2024-01-02",
                "to_date": "2024-01-10",
                "entries": [
                    {"date": "2024-01-02", "ITD": 0.183, "1Y": 0.071},
                ],
                "_links": {"self": "/v1/accounts/HL-SIPP/performance"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    response = client.get_performance(
        account_name="HL-SIPP",
        attributes=["ITD", "1Y"],
        start=date(2024, 1, 2),
        end=date(2024, 1, 10),
    )

    assert response.account_name == "HL-SIPP"
    assert len(response.entries) == 1
    assert response.entries[0].model_dump()["ITD"] == 0.183


@pytest.mark.parametrize("status_code", [404, 422])
def test_get_performance_raises_on_error_status(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "type": "about:blank",
                "title": "Error",
                "status": status_code,
                "detail": "boom",
                "instance": str(request.url),
            },
        )

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.get_performance(
            account_name="HL-SIPP",
            attributes=["ITD"],
            start=date(2024, 1, 2),
            end=date(2024, 1, 10),
        )


def test_get_performance_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.get_performance(
            account_name="HL-SIPP",
            attributes=["ITD"],
            start=date(2024, 1, 2),
            end=date(2024, 1, 10),
        )
