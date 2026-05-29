import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.exceptions import ProviderUnavailableError

scenarios("error_handling.feature")


@given("the API service is running locally", target_fixture="api_running_err")
def api_running_err() -> None:
    pass


@given("the upstream data provider is unreachable")
def provider_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_unavailable(self: object, ticker: str) -> None:
        raise ProviderUnavailableError()

    from app.providers.yfinance_provider import YFinanceProvider
    monkeypatch.setattr(YFinanceProvider, "get_current_price", raise_unavailable)


@when("a client sends a GET request to /securities/INVALIDXYZ99/price", target_fixture="response")
def get_invalid_ticker_price(client: TestClient) -> object:
    return client.get("/securities/INVALIDXYZ99/price")


@when("a client sends a GET request to /securities/%24/price", target_fixture="response")
def get_malformed_ticker_price(client: TestClient) -> object:
    return client.get("/securities/%24/price")


@when("a client sends a GET request to any valid ticker price endpoint", target_fixture="response")
def get_price_provider_down(client: TestClient) -> object:
    return client.get("/securities/AAPL/price")


@then("the response status code is 404")
def status_404(response: object) -> None:
    assert response.status_code == 404  # type: ignore[union-attr]


@then("the response status code is 422")
def status_422(response: object) -> None:
    assert response.status_code == 422  # type: ignore[union-attr]


@then("the response status code is 503")
def status_503(response: object) -> None:
    assert response.status_code == 503  # type: ignore[union-attr]


@then('the response body contains a field "detail" with a descriptive error message')
def has_detail_404(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "detail" in data
    assert len(data["detail"]) > 0


@then('the response body contains a field "detail"')
def has_detail_field(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "detail" in data


@then(
    "the response body contains a field \"detail\""
    " indicating the upstream dependency is unavailable"
)
def has_detail_503(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "detail" in data
    assert len(data["detail"]) > 0
