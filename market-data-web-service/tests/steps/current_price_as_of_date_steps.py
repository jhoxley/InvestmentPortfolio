import re
from datetime import date

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("current_price_as_of_date.feature")


@given("the API service is running locally", target_fixture="api_running_aod")
def api_running_aod() -> None:
    pass


@given('the ticker "AAPL" is a valid security listed on a supported exchange', target_fixture="aapl_valid_aod")
def aapl_valid_aod() -> None:
    pass


@given('the ticker "MSFT" is a valid security', target_fixture="msft_valid_aod")
def msft_valid_aod() -> None:
    pass


@when("a client sends a GET request to /securities/AAPL/price", target_fixture="response")
def get_aapl_price_aod(client: TestClient) -> object:
    return client.get("/securities/AAPL/price")


@when("a client sends a GET request to /securities/MSFT/price", target_fixture="price_response")
def get_msft_price(client: TestClient) -> object:
    return client.get("/securities/MSFT/price")


@when(
    "a client also sends a GET request to /securities/MSFT/history with no date parameters",
    target_fixture="history_response",
)
def get_msft_history_no_params(client: TestClient) -> object:
    return client.get("/securities/MSFT/history")


@then("the response status code is 200")
def status_200_aod(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then('the response body contains a field "as_of_date" in YYYY-MM-DD format')
def has_as_of_date(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "as_of_date" in data
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", data["as_of_date"]) is not None


@then('the "as_of_date" field is not a future date')
def as_of_date_not_future(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    as_of = date.fromisoformat(data["as_of_date"])
    assert as_of <= date.today()


@then('the "as_of_date" field is not a Saturday or Sunday')
def as_of_date_not_weekend(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    as_of = date.fromisoformat(data["as_of_date"])
    assert as_of.weekday() < 5


@then(
    'the "as_of_date" in the price response matches the "date" of the last entry in the history "prices" list'
)
def as_of_date_reconciles(price_response: object, history_response: object) -> None:
    price_data = price_response.json()  # type: ignore[union-attr]
    history_data = history_response.json()  # type: ignore[union-attr]
    last_date = history_data["prices"][-1]["date"]
    assert price_data["as_of_date"] == last_date
