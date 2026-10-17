from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("observed_only_fx.feature")

_RATE_JAN02 = 0.7900
_RATE_JAN06 = 0.8100


@given("a USD security has observations on 2025-01-02 and 2025-01-06 only")
def usd_security_sparse(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 100.0),
        (date(2025, 1, 6), 200.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 200.0,
        "as_of_date": date(2025, 1, 6),
        "market_state": "CLOSED",
    }


@given("the FX rate differs between 2025-01-02 and 2025-01-06")
def fx_differs(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), _RATE_JAN02),
        (date(2025, 1, 6), _RATE_JAN06),
    ]


@given("the FX source has no rate for 2025-01-06")
def fx_missing_jan06(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), _RATE_JAN02),
        (date(2025, 1, 3), _RATE_JAN02),
    ]


@given("the FX source has rates for every business day from 2025-01-02 to 2025-01-08")
def fx_all_days(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 0.79),
        (date(2025, 1, 3), 0.795),
        (date(2025, 1, 6), 0.80),
        (date(2025, 1, 7), 0.805),
        (date(2025, 1, 8), 0.81),
    ]


@when(
    "a consumer requests observed-only history in GBP from 2025-01-02 to 2025-01-06",
    target_fixture="response",
)
def req_gbp_to_jan06(client_with_fx: TestClient) -> httpx.Response:
    return client_with_fx.get(
        "/securities/AAPL/history",
        params={
            "from": "2025-01-02",
            "to": "2025-01-06",
            "currency": "GBP",
            "fill": "none",
        },
    )


@when(
    "a consumer requests observed-only history in GBP from 2025-01-02 to 2025-01-08",
    target_fixture="response",
)
def req_gbp_to_jan08(client_with_fx: TestClient) -> httpx.Response:
    return client_with_fx.get(
        "/securities/AAPL/history",
        params={
            "from": "2025-01-02",
            "to": "2025-01-08",
            "currency": "GBP",
            "fill": "none",
        },
    )


@then("the response status code is 200")
def status_200(response: httpx.Response) -> None:
    assert response.status_code == 200, response.text


@then('the response currency is "GBP"')
def currency_gbp(response: httpx.Response) -> None:
    assert response.json()["currency"] == "GBP"


@then("the response contains exactly 2 price entries")
def exactly_two(response: httpx.Response) -> None:
    assert len(response.json()["prices"]) == 2, response.json()["prices"]


@then("each entry's price reflects the FX rate for its own date")
def rates_per_own_date(response: httpx.Response) -> None:
    by_date = {e["date"]: e for e in response.json()["prices"]}
    jan02, jan06 = by_date["2025-01-02"], by_date["2025-01-06"]
    assert jan02["fx_rate"] == pytest.approx(_RATE_JAN02)
    assert jan06["fx_rate"] == pytest.approx(_RATE_JAN06)
    assert jan02["close"] == pytest.approx(100.0 * _RATE_JAN02)
    assert jan06["close"] == pytest.approx(200.0 * _RATE_JAN06)


@then("the entry for 2025-01-06 is present with a carried forward FX rate")
def jan06_carried_rate(response: httpx.Response) -> None:
    by_date = {e["date"]: e for e in response.json()["prices"]}
    assert "2025-01-06" in by_date, list(by_date)
    entry = by_date["2025-01-06"]
    assert entry["fx_rate"] == pytest.approx(_RATE_JAN02)
    assert entry["close"] == pytest.approx(200.0 * _RATE_JAN02)


@then("the returned dates are 2025-01-02 and 2025-01-06")
def dates_are_two(response: httpx.Response) -> None:
    assert [e["date"] for e in response.json()["prices"]] == ["2025-01-02", "2025-01-06"]
