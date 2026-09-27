"""Unit tests for HttpPortfolioAnalysisClient, stubbed via httpx.MockTransport.

No real portfolio-analysis-service instance is used — every request is
answered by a hand-built transport, mirroring the pattern already proven in
portfolio-analysis-service/app/clients/market_data_client.py.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from structlog.testing import capture_logs

from src.exceptions import PortfolioAnalysisServiceError
from src.services.portfolio_analysis_client import HttpPortfolioAnalysisClient

BASE_URL = "http://testserver"


def _client(transport: httpx.MockTransport) -> HttpPortfolioAnalysisClient:
    return HttpPortfolioAnalysisClient(base_url=BASE_URL, timeout_seconds=5.0, transport=transport)


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


# --- periodicity parameter (021) ------------------------------------------


def _timeseries_body(periodicity: str | None) -> dict:
    """Build a minimal timeseries payload, optionally echoing a periodicity."""
    body: dict = {
        "account_name": "HL-SIPP",
        "attributes": ["capital"],
        "from_date": "2016-04-20",
        "to_date": "2025-12-31",
        "entries": [{"date": "2016-04-20", "capital": 1.0}],
        "_links": {"self": "/v1/accounts/HL-SIPP/timeseries"},
    }
    if periodicity is not None:
        body["periodicity"] = periodicity
    return body


def _position_body(periodicity: str | None) -> dict:
    """Build a minimal position-timeseries payload, optionally echoing a periodicity."""
    body: dict = {
        "account_name": "HL-SIPP",
        "attributes": ["market_value"],
        "positions": ["Cash"],
        "from_date": "2016-04-20",
        "to_date": "2025-12-31",
        "entries": [{"date": "2016-04-20", "position": "Cash", "market_value": 1.0}],
        "_links": {"self": "/v1/accounts/HL-SIPP/position"},
    }
    if periodicity is not None:
        body["periodicity"] = periodicity
    return body


def test_get_timeseries_sends_periodicity_when_supplied() -> None:
    seen: dict[str, list[str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["periodicity"] = request.url.params.get_list("periodicity")
        return httpx.Response(200, json=_timeseries_body("annual"))

    response = _client(httpx.MockTransport(handler)).get_timeseries(
        account_name="HL-SIPP",
        attributes=["capital"],
        start=date(2016, 4, 20),
        end=date(2025, 12, 31),
        periodicity="annual",
    )

    assert seen["periodicity"] == ["annual"]
    assert response.periodicity == "annual"


def test_get_timeseries_omits_periodicity_when_not_supplied() -> None:
    """Backward compatibility: an unset interval must not appear in the query string."""
    seen: dict[str, list[str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["periodicity"] = request.url.params.get_list("periodicity")
        return httpx.Response(200, json=_timeseries_body("day"))

    _client(httpx.MockTransport(handler)).get_timeseries(
        account_name="HL-SIPP",
        attributes=["capital"],
        start=date(2016, 4, 20),
        end=date(2025, 12, 31),
    )

    assert seen["periodicity"] == []


def test_get_position_timeseries_sends_periodicity_when_supplied() -> None:
    seen: dict[str, list[str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["periodicity"] = request.url.params.get_list("periodicity")
        return httpx.Response(200, json=_position_body("quarter"))

    response = _client(httpx.MockTransport(handler)).get_position_timeseries(
        account_name="HL-SIPP",
        positions=["Cash"],
        attributes=["market_value"],
        start=date(2016, 4, 20),
        end=date(2025, 12, 31),
        periodicity="quarter",
    )

    assert seen["periodicity"] == ["quarter"]
    assert response.periodicity == "quarter"


def test_get_position_timeseries_omits_periodicity_when_not_supplied() -> None:
    seen: dict[str, list[str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["periodicity"] = request.url.params.get_list("periodicity")
        return httpx.Response(200, json=_position_body(None))

    _client(httpx.MockTransport(handler)).get_position_timeseries(
        account_name="HL-SIPP",
        positions=["Cash"],
        attributes=["market_value"],
        start=date(2016, 4, 20),
        end=date(2025, 12, 31),
    )

    assert seen["periodicity"] == []


def test_response_without_periodicity_still_parses() -> None:
    """A pre-008 service omits the field entirely; that must not be an error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_timeseries_body(None))

    response = _client(httpx.MockTransport(handler)).get_timeseries(
        account_name="HL-SIPP",
        attributes=["capital"],
        start=date(2016, 4, 20),
        end=date(2025, 12, 31),
        periodicity="annual",
    )

    assert response.periodicity is None


def test_ignored_periodicity_is_logged_as_a_warning() -> None:
    """A service that ignores the parameter must be diagnosable, not silent."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_timeseries_body(None))

    with capture_logs() as entries:
        _client(httpx.MockTransport(handler)).get_timeseries(
            account_name="HL-SIPP",
            attributes=["capital"],
            start=date(2016, 4, 20),
            end=date(2025, 12, 31),
            periodicity="annual",
        )

    warnings = [e for e in entries if e["log_level"] == "warning"]
    assert [e["event"] for e in warnings] == ["periodicity_not_applied"]
    assert warnings[0]["requested_periodicity"] == "annual"
    assert warnings[0]["echoed_periodicity"] is None


def test_mismatched_periodicity_echo_is_logged_as_a_warning() -> None:
    """An echo that differs from the request is just as wrong as a missing one."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_timeseries_body("day"))

    with capture_logs() as entries:
        _client(httpx.MockTransport(handler)).get_timeseries(
            account_name="HL-SIPP",
            attributes=["capital"],
            start=date(2016, 4, 20),
            end=date(2025, 12, 31),
            periodicity="annual",
        )

    warnings = [e for e in entries if e["log_level"] == "warning"]
    assert [e["event"] for e in warnings] == ["periodicity_not_applied"]
    assert warnings[0]["echoed_periodicity"] == "day"


def test_matching_periodicity_echo_logs_no_warning() -> None:
    """The happy path must stay quiet, or the warning is noise."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_timeseries_body("annual"))

    with capture_logs() as entries:
        _client(httpx.MockTransport(handler)).get_timeseries(
            account_name="HL-SIPP",
            attributes=["capital"],
            start=date(2016, 4, 20),
            end=date(2025, 12, 31),
            periodicity="annual",
        )

    assert [e for e in entries if e["log_level"] == "warning"] == []


def test_no_warning_when_no_periodicity_was_requested() -> None:
    """Callers that never ask for an interval must not be warned at."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_timeseries_body(None))

    with capture_logs() as entries:
        _client(httpx.MockTransport(handler)).get_timeseries(
            account_name="HL-SIPP",
            attributes=["capital"],
            start=date(2016, 4, 20),
            end=date(2025, 12, 31),
        )

    assert [e for e in entries if e["log_level"] == "warning"] == []


# --- get_projection (022) ---------------------------------------------------


def _projection_body(periodicity: str | None) -> dict:
    body: dict = {
        "account_name": "HL-SIPP",
        "attributes": ["market_value"],
        "positions": ["Historical", "3Y", "5Y"],
        "from_date": "2016-04-20",
        "to_date": "2036-09-22",
        "entries": [
            {"date": "2026-09-22", "position": "Historical", "market_value": 48120.75},
            {"date": "2036-09-22", "position": "3Y", "market_value": 71204.90},
            {"date": "2036-09-22", "position": "5Y", "market_value": 78310.20},
        ],
        "_links": {"self": "/v1/accounts/HL-SIPP/projection"},
    }
    if periodicity is not None:
        body["periodicity"] = periodicity
    return body


def test_get_projection_sends_projection_date_and_repeated_return_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/accounts/HL-SIPP/projection"
        params = httpx.QueryParams(request.url.query)
        assert params.get_list("return") == ["3y", "5y"]
        assert params.get("projection_date") == "2036-09-22"
        assert "start" not in params
        assert "periodicity" not in params
        return httpx.Response(200, json=_projection_body(None))

    client = _client(httpx.MockTransport(handler))
    response = client.get_projection(
        account_name="HL-SIPP",
        projection_date=date(2036, 9, 22),
        returns=["3y", "5y"],
    )

    assert response.account_name == "HL-SIPP"
    assert response.positions == ["Historical", "3Y", "5Y"]
    assert {e.position for e in response.entries} == {"Historical", "3Y", "5Y"}


def test_get_projection_sends_start_when_supplied() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = httpx.QueryParams(request.url.query)
        assert params.get("start") == "2024-01-02"
        return httpx.Response(200, json=_projection_body(None))

    client = _client(httpx.MockTransport(handler))
    client.get_projection(
        account_name="HL-SIPP",
        projection_date=date(2036, 9, 22),
        returns=["3y"],
        start=date(2024, 1, 2),
    )


def test_get_projection_omits_start_when_not_supplied() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = httpx.QueryParams(request.url.query)
        assert "start" not in params
        return httpx.Response(200, json=_projection_body(None))

    client = _client(httpx.MockTransport(handler))
    client.get_projection(
        account_name="HL-SIPP",
        projection_date=date(2036, 9, 22),
        returns=["3y"],
        start=None,
    )


def test_get_projection_sends_no_return_params_when_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = httpx.QueryParams(request.url.query)
        assert params.get_list("return") == []
        return httpx.Response(
            200,
            json={
                **_projection_body(None),
                "positions": ["Historical"],
                "entries": [
                    {"date": "2026-09-22", "position": "Historical", "market_value": 48120.75}
                ],
            },
        )

    client = _client(httpx.MockTransport(handler))
    response = client.get_projection(
        account_name="HL-SIPP",
        projection_date=date(2036, 9, 22),
        returns=[],
    )
    assert response.positions == ["Historical"]


def test_get_projection_sends_periodicity_when_supplied() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = httpx.QueryParams(request.url.query)
        assert params.get("periodicity") == "month"
        return httpx.Response(200, json=_projection_body("month"))

    client = _client(httpx.MockTransport(handler))
    response = client.get_projection(
        account_name="HL-SIPP",
        projection_date=date(2036, 9, 22),
        returns=["3y", "5y"],
        periodicity="month",
    )
    assert response.periodicity == "month"


@pytest.mark.parametrize("status_code", [404, 422])
def test_get_projection_raises_on_error_status(status_code: int) -> None:
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
        client.get_projection(
            account_name="HL-SIPP",
            projection_date=date(2036, 9, 22),
            returns=["3y"],
        )


def test_get_projection_ignored_periodicity_is_logged_as_a_warning() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_projection_body(None))

    with capture_logs() as entries:
        _client(httpx.MockTransport(handler)).get_projection(
            account_name="HL-SIPP",
            projection_date=date(2036, 9, 22),
            returns=["3y"],
            periodicity="month",
        )

    warnings = [e for e in entries if e["log_level"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["event"] == "periodicity_not_applied"


# --- return histogram (024) -------------------------------------------------


def test_get_return_histogram_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/accounts/HL-SIPP/risk/return-histogram"
        params = httpx.QueryParams(request.url.query)
        assert params.get("start") == "2024-01-02"
        assert params.get("end") == "2024-12-31"
        return httpx.Response(
            200,
            json={
                "account_name": "HL-SIPP",
                "from_date": "2024-01-02",
                "to_date": "2024-12-31",
                "histogram": [[-25, 1], [0, 12], [65, 1]],
                "statistics": {
                    "count": 14,
                    "mean": 4.1,
                    "median": 3.0,
                    "mode": 0,
                    "minimum": -25,
                    "maximum": 65,
                    "std_dev": 14.2,
                    "std_dev_bands": [],
                    "skewness": 1.8,
                    "kurtosis": 6.2,
                },
                "_links": {"self": "/v1/accounts/HL-SIPP/risk/return-histogram"},
            },
        )

    client = _client(httpx.MockTransport(handler))
    response = client.get_return_histogram(
        account_name="HL-SIPP",
        start=date(2024, 1, 2),
        end=date(2024, 12, 31),
    )

    assert response.account_name == "HL-SIPP"
    assert response.histogram == [(-25, 1), (0, 12), (65, 1)]
    assert response.statistics.count == 14
    assert response.statistics.mean == 4.1


@pytest.mark.parametrize("status_code", [404, 422])
def test_get_return_histogram_raises_on_error_status(status_code: int) -> None:
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
        client.get_return_histogram(
            account_name="HL-SIPP",
            start=date(2024, 1, 2),
            end=date(2024, 12, 31),
        )


def test_get_return_histogram_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(PortfolioAnalysisServiceError):
        client.get_return_histogram(
            account_name="HL-SIPP",
            start=date(2024, 1, 2),
            end=date(2024, 12, 31),
        )
