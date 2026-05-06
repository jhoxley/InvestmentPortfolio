from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("current_price.feature")


@pytest.fixture()
def response_store() -> dict[str, object]:
    return {}


@given("the API service is running locally")
def api_running() -> None:
    pass


@given('the ticker "AAPL" is a valid security listed on a supported exchange')
def aapl_valid() -> None:
    pass


@given('the ticker "BARC.L" is a valid security on the London Stock Exchange')
def barcl_valid() -> None:
    pass


@when("a client sends a GET request to /securities/AAPL/price", target_fixture="response")
def get_aapl_price(client: TestClient) -> object:
    return client.get("/securities/AAPL/price")


@when("a client sends a GET request to /securities/BARC.L/price", target_fixture="response")
def get_barcl_price(client: TestClient) -> object:
    return client.get("/securities/BARC.L/price")


@when('a client requests the price for valid ticker "AAPL"', target_fixture="response")
def request_aapl_price(client: TestClient) -> object:
    return client.get("/securities/AAPL/price")


@then("the response status code is 200")
def status_200(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then('the response body contains a numeric field "price"')
def has_price_field(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "price" in data
    assert isinstance(data["price"], (int, float))


@then('the response body contains a field "currency" with a valid ISO 4217 currency code')
def has_currency_field(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "currency" in data
    assert len(data["currency"]) >= 3


@then('the response body contains a field "ticker" matching the requested identifier "AAPL"')
def ticker_matches_aapl(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data.get("ticker") == "AAPL"


@then('the response body contains a field "timestamp" in ISO 8601 format')
def has_iso_timestamp(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "timestamp" in data
    datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))


@then('the field "currency" in the response body is "GBp" or "GBP"')
def currency_is_gbp(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data.get("currency") in ("GBp", "GBP")


@then('the returned "price" field is a positive numeric value')
def price_is_positive(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert isinstance(data.get("price"), (int, float))
    assert data["price"] > 0
