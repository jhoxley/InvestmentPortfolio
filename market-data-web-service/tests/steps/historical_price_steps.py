import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("historical_price.feature")


@given("the API service is running locally", target_fixture="api_running_hist")
def api_running_hist() -> None:
    pass


@given('the ticker "MSFT" is valid')
def msft_valid() -> None:
    pass


@when(
    "a client sends a GET request to /securities/MSFT/history?from=2024-01-01&to=2024-03-31",
    target_fixture="response",
)
def get_msft_history_range(client: TestClient) -> object:
    return client.get("/securities/MSFT/history", params={"from": "2024-01-01", "to": "2024-03-31"})


@when(
    "a client sends a GET request to /securities/MSFT/history with no date parameters",
    target_fixture="response",
)
def get_msft_history_default(client: TestClient) -> object:
    return client.get("/securities/MSFT/history")


@when(
    "a client sends GET /securities/MSFT/history?from=2024-06-01&to=2024-01-01",
    target_fixture="response",
)
def get_msft_history_invalid_range(client: TestClient) -> object:
    return client.get("/securities/MSFT/history", params={"from": "2024-06-01", "to": "2024-01-01"})


@then("the response status code is 200")
def status_200(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then('the response body contains a list field "prices"')
def has_prices_list(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "prices" in data
    assert isinstance(data["prices"], list)


@then('each entry in "prices" contains a "date" in YYYY-MM-DD format and a numeric "close" field')
def prices_have_date_close(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    for entry in data["prices"]:
        assert "date" in entry
        assert len(entry["date"]) == 10
        assert entry["date"][4] == "-" and entry["date"][7] == "-"
        assert "close" in entry
        assert isinstance(entry["close"], (int, float))


@then("the entries are ordered chronologically ascending")
def prices_chronological(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    dates = [e["date"] for e in data["prices"]]
    assert dates == sorted(dates)


@then("the response contains at least one price entry")
def has_at_least_one_price(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert len(data.get("prices", [])) >= 1


@then("the response status code is 422")
def status_422(response: object) -> None:
    assert response.status_code == 422  # type: ignore[union-attr]


@then("the response body contains a field \"detail\" describing the validation error")
def has_detail_validation(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "detail" in data
    assert len(data["detail"]) > 0
