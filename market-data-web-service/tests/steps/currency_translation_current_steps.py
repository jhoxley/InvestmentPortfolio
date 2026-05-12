from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("currency_translation_current.feature")

_AS_OF = date(2025, 1, 14)


@pytest.fixture()
def response_store() -> dict[str, object]:
    return {}


@given("AAPL is a USD security with current price 185.50")
def aapl_usd(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 185.50,
        "currency": "USD",
        "market_state": "closed",
        "as_of_date": _AS_OF,
    }


@given("BARC.L is a GBP security with current price 2.18")
def barcl_gbp(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 2.18,
        "currency": "GBP",
        "market_state": "closed",
        "as_of_date": _AS_OF,
    }


@given("the USDGBP FX rate is 0.7912")
def usdgbp_rate(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [(_AS_OF, 0.7912)]


@when(
    'a client requests the current price for "AAPL" with no currency parameter',
    target_fixture="response",
)
def get_aapl_no_currency(client_with_fx: TestClient) -> object:
    return client_with_fx.get("/securities/AAPL/price")


@when(
    'a client requests the current price for "AAPL" with currency "GBP"',
    target_fixture="response",
)
def get_aapl_gbp(client_with_fx: TestClient) -> object:
    return client_with_fx.get("/securities/AAPL/price?currency=GBP")


@when(
    'a client requests the current price for "BARC.L" with currency "GBP"',
    target_fixture="response",
)
def get_barcl_gbp(client_with_fx: TestClient) -> object:
    return client_with_fx.get("/securities/BARC.L/price?currency=GBP")


@when(
    'a client requests the current price for "AAPL" with currency "INVALID"',
    target_fixture="response",
)
def get_aapl_invalid_currency(client_with_fx: TestClient) -> object:
    return client_with_fx.get("/securities/AAPL/price?currency=INVALID")


@then("the response status code is 200")
def status_200(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the response status code is 422")
def status_422(response: object) -> None:
    assert response.status_code == 422  # type: ignore[union-attr]


@then('the response currency is "USD"')
def currency_usd(response: object) -> None:
    assert response.json()["currency"] == "USD"  # type: ignore[union-attr]


@then('the response currency is "GBP"')
def currency_gbp(response: object) -> None:
    assert response.json()["currency"] == "GBP"  # type: ignore[union-attr]


@then("the response price is 185.50")
def price_185(response: object) -> None:
    assert response.json()["price"] == pytest.approx(185.50, rel=1e-4)  # type: ignore[union-attr]


@then("the response price is 2.18")
def price_218(response: object) -> None:
    assert response.json()["price"] == pytest.approx(2.18, rel=1e-4)  # type: ignore[union-attr]


@then("the response price is approximately 146.72")
def price_approx_14672(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data["price"] == pytest.approx(185.50 * 0.7912, rel=1e-3)


@then("the response fx_rate is null")
def fx_rate_null(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data.get("fx_rate") is None


@then("the response fx_rate is 0.7912")
def fx_rate_07912(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data["fx_rate"] == pytest.approx(0.7912, rel=1e-4)


@then('the response error code is "INVALID_CURRENCY"')
def error_code_invalid_currency(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data.get("code") == "INVALID_CURRENCY"
