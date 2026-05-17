from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("gap_fill_fx_conversion.feature")


@given(
    "the provider returns security prices for 2025-01-02, 2025-01-03, and 2025-01-06 all at 100.00"
)
def mock_security_prices_complete(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 100.0),
        (date(2025, 1, 3), 100.0),
        (date(2025, 1, 6), 100.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 100.0,
        "as_of_date": date(2025, 1, 6),
        "market_state": "CLOSED",
    }


@given("the FX provider returns rates for USDGBP on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only")
def mock_fx_usdgbp_gap(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 1.25),
        (date(2025, 1, 6), 1.27),
    ]


@when(
    "a client requests AAPL history from 2025-01-02 to 2025-01-06 with currency GBP",
    target_fixture="response",
)
def get_history_with_fx_conversion(client_with_gap_fill: TestClient) -> object:
    return client_with_gap_fill.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-02", "to": "2025-01-06", "currency": "GBP"},
    )


@then("the conversion response contains 3 price entries")
def assert_conversion_3_entries(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]
    assert len(response.json()["prices"]) == 3  # type: ignore[union-attr]


@then("the entry for 2025-01-03 has a non-zero close")
def assert_jan03_nonzero(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices["2025-01-03"] > 0


@then("the entry for 2025-01-03 close price equals 125.00")
def assert_jan03_125(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices["2025-01-03"] == pytest.approx(125.0)
