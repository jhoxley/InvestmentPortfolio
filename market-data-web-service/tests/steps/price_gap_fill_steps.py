from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("price_gap_fill.feature")


def _prev_bday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


# ── Given steps ────────────────────────────────────────────────────────────────

@given("the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00")
def mock_mid_series_gap(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 100.0),
        (date(2025, 1, 6), 102.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 102.0,
        "as_of_date": date(2025, 1, 6),
        "market_state": "CLOSED",
    }


@given("the data source has prices for 2025-01-02 at 100.00 and 2025-01-07 at 105.00")
def mock_multi_gap(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 100.0),
        (date(2025, 1, 7), 105.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 105.0,
        "as_of_date": date(2025, 1, 7),
        "market_state": "CLOSED",
    }


@given("the data source has prices for 2025-01-02 at 100.00 and 2025-01-03 at 98.00")
def mock_end_of_range_gap(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 100.0),
        (date(2025, 1, 3), 98.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 98.0,
        "as_of_date": date(2025, 1, 3),
        "market_state": "CLOSED",
    }


@given("the data source has no price before 2025-01-06")
def mock_back_fill(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 6), 100.0),
        (date(2025, 1, 7), 102.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 100.0,
        "as_of_date": date(2025, 1, 6),
        "market_state": "CLOSED",
    }


@given("today is a business day")
def today_is_business_day() -> None:
    if date.today().weekday() >= 5:
        pytest.skip("Test requires today to be a business day (Mon-Fri)")


@given("the data source has a price for yesterday at 100.00 but no price for today")
def mock_t1_stale(mock_inner_provider: MagicMock) -> None:
    t1 = _prev_bday(date.today())
    mock_inner_provider.get_price_history.return_value = [(t1, 100.0)]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 100.0,
        "as_of_date": t1,
        "market_state": "CLOSED",
    }


@given("the data source has a price for T-2 at 100.00 but no observations for T-1 or today")
def mock_t2_stale(mock_inner_provider: MagicMock) -> None:
    t1 = _prev_bday(date.today())
    t2 = _prev_bday(t1)
    mock_inner_provider.get_price_history.return_value = [(t2, 100.0)]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 100.0,
        "as_of_date": t2,
        "market_state": "CLOSED",
    }


# ── When steps ─────────────────────────────────────────────────────────────────

@when(
    "a client requests price history from 2025-01-02 to 2025-01-06",
    target_fixture="response",
)
def get_history_jan02_jan06(client_with_gap_fill: TestClient) -> object:
    return client_with_gap_fill.get(
        "/securities/AAPL/history", params={"from": "2025-01-02", "to": "2025-01-06"}
    )


@when(
    "a client requests price history from 2025-01-02 to 2025-01-07",
    target_fixture="response",
)
def get_history_jan02_jan07(client_with_gap_fill: TestClient) -> object:
    return client_with_gap_fill.get(
        "/securities/AAPL/history", params={"from": "2025-01-02", "to": "2025-01-07"}
    )


@when(
    "a client requests price history ending today",
    target_fixture="response",
)
def get_history_ending_today(client_with_gap_fill: TestClient) -> object:
    today = date.today()
    from_d = today - timedelta(days=10)
    return client_with_gap_fill.get(
        "/securities/AAPL/history",
        params={"from": str(from_d), "to": str(today)},
    )


# ── Then steps ─────────────────────────────────────────────────────────────────

@then("the response contains 3 price entries")
def assert_3_entries(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]
    assert len(response.json()["prices"]) == 3  # type: ignore[union-attr]


@then("the response contains 4 price entries")
def assert_4_entries(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]
    assert len(response.json()["prices"]) == 4  # type: ignore[union-attr]


@then("the entry for 2025-01-03 has close price 100.00")
def assert_jan03_100(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices["2025-01-03"] == pytest.approx(100.0)


@then("the entry for 2025-01-06 has close price 102.00")
def assert_jan06_102(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices["2025-01-06"] == pytest.approx(102.0)


@then("the entries for 2025-01-03 and 2025-01-06 both have close price 100.00")
def assert_jan03_jan06_100(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices["2025-01-03"] == pytest.approx(100.0)
    assert prices["2025-01-06"] == pytest.approx(100.0)


@then("the entries for 2025-01-06 and 2025-01-07 both have close price 98.00")
def assert_jan06_jan07_98(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices["2025-01-06"] == pytest.approx(98.0)
    assert prices["2025-01-07"] == pytest.approx(98.0)


@then("the entries for 2025-01-02 and 2025-01-03 both have close price 100.00")
def assert_jan02_jan03_100(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices["2025-01-02"] == pytest.approx(100.0)
    assert prices["2025-01-03"] == pytest.approx(100.0)


@then("the response contains an entry for today")
def assert_has_today(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]
    dates = {p["date"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert str(date.today()) in dates


@then("the entry for today has close price 100.00")
def assert_today_100(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    assert prices[str(date.today())] == pytest.approx(100.0)


@then("the response contains entries for T-1 and today")
def assert_has_t1_and_today(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]
    dates = {p["date"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    t1 = _prev_bday(date.today())
    assert str(date.today()) in dates
    assert str(t1) in dates


@then("both T-1 and today entries have close price 100.00")
def assert_t1_and_today_100(response: object) -> None:
    prices = {p["date"]: p["close"] for p in response.json()["prices"]}  # type: ignore[union-attr]
    t1 = _prev_bday(date.today())
    assert prices[str(t1)] == pytest.approx(100.0)
    assert prices[str(date.today())] == pytest.approx(100.0)
