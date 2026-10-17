from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("observed_only_history.feature")


def _prev_bday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _entry_for(response: httpx.Response, target: date) -> dict[str, Any] | None:
    for entry in response.json()["prices"]:
        if entry["date"] == target.isoformat():
            return entry
    return None


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


@given("the data source has no price before 2025-01-06")
def mock_no_price_before(mock_inner_provider: MagicMock) -> None:
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


@given("the data source has a price for T-2 at 100.00 but no observations for T-1 or today")
def mock_t2_stale(mock_inner_provider: MagicMock) -> None:
    t2 = _prev_bday(_prev_bday(date.today()))
    mock_inner_provider.get_price_history.return_value = [(t2, 100.0)]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 100.0,
        "as_of_date": t2,
        "market_state": "CLOSED",
    }


@given("the data source has observations on only 2 of the 5 business days in the range")
def mock_sparse_observations(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 3), 101.0),
        (date(2025, 1, 7), 103.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 103.0,
        "as_of_date": date(2025, 1, 7),
        "market_state": "CLOSED",
    }


# ── When steps ─────────────────────────────────────────────────────────────────

@when(
    "a consumer requests observed-only price history from 2025-01-02 to 2025-01-06",
    target_fixture="response",
)
def get_observed_jan02_jan06(client_with_gap_fill: TestClient) -> httpx.Response:
    return client_with_gap_fill.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-02", "to": "2025-01-06", "fill": "none"},
    )


@when(
    "a consumer requests observed-only price history from 2025-01-02 to 2025-01-07",
    target_fixture="response",
)
def get_observed_jan02_jan07(client_with_gap_fill: TestClient) -> httpx.Response:
    return client_with_gap_fill.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-02", "to": "2025-01-07", "fill": "none"},
    )


@when(
    "a consumer requests observed-only price history from 2025-01-02 to 2025-01-08",
    target_fixture="response",
)
def get_observed_jan02_jan08(client_with_gap_fill: TestClient) -> httpx.Response:
    return client_with_gap_fill.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-02", "to": "2025-01-08", "fill": "none"},
    )


@when("a consumer requests observed-only price history ending today", target_fixture="response")
def get_observed_ending_today(client_with_gap_fill: TestClient) -> httpx.Response:
    today = date.today()
    start = today - timedelta(days=10)
    return client_with_gap_fill.get(
        "/securities/AAPL/history",
        params={"from": start.isoformat(), "to": today.isoformat(), "fill": "none"},
    )


@when(
    "a consumer requests price history from 2025-01-02 to 2025-01-06 with no fill parameter",
    target_fixture="response",
)
def get_default_jan02_jan06(client_with_gap_fill: TestClient) -> httpx.Response:
    return client_with_gap_fill.get(
        "/securities/AAPL/history", params={"from": "2025-01-02", "to": "2025-01-06"}
    )


@when(
    "a consumer requests the same range once with fill all and once with no fill parameter",
    target_fixture="response_pair",
)
def get_fill_all_and_default(
    client_with_gap_fill: TestClient,
) -> tuple[httpx.Response, httpx.Response]:
    params = {"from": "2025-01-02", "to": "2025-01-06"}
    explicit = client_with_gap_fill.get(
        "/securities/AAPL/history", params={**params, "fill": "all"}
    )
    default = client_with_gap_fill.get("/securities/AAPL/history", params=params)
    return explicit, default


@when('a consumer requests price history with fill "forward"', target_fixture="response")
def get_invalid_fill(client_with_gap_fill: TestClient) -> httpx.Response:
    return client_with_gap_fill.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-02", "to": "2025-01-06", "fill": "forward"},
    )


@when(
    "a consumer requests the current price with and without fill none",
    target_fixture="current_price_pair",
)
def get_current_price_pair(
    client_with_gap_fill: TestClient,
) -> tuple[httpx.Response, httpx.Response]:
    with_fill = client_with_gap_fill.get("/securities/AAPL/price", params={"fill": "none"})
    without = client_with_gap_fill.get("/securities/AAPL/price")
    return with_fill, without


@when(
    "a consumer requests FX history with and without fill none",
    target_fixture="fx_history_pair",
)
def get_fx_history_pair(
    client_with_gap_fill: TestClient, mock_fx_provider: MagicMock
) -> tuple[httpx.Response, httpx.Response]:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 0.79),
        (date(2025, 1, 6), 0.80),
    ]
    params = {"from": "2025-01-02", "to": "2025-01-06"}
    with_fill = client_with_gap_fill.get("/fx/GBPUSD/history", params={**params, "fill": "none"})
    without = client_with_gap_fill.get("/fx/GBPUSD/history", params=params)
    return with_fill, without


# ── Then steps ─────────────────────────────────────────────────────────────────

@then("the response status code is 200")
def status_200(response: httpx.Response) -> None:
    assert response.status_code == 200, response.text


@then("the response status code is 422")
def status_422(response: httpx.Response) -> None:
    assert response.status_code == 422, response.text


@then("the response contains exactly 2 price entries")
def exactly_two_entries(response: httpx.Response) -> None:
    assert len(response.json()["prices"]) == 2, response.json()["prices"]


@then("the response contains exactly 3 price entries")
def exactly_three_entries(response: httpx.Response) -> None:
    assert len(response.json()["prices"]) == 3, response.json()["prices"]


@then("the response contains an entry for 2025-01-02 with close price 100.00")
def entry_jan02_100(response: httpx.Response) -> None:
    entry = _entry_for(response, date(2025, 1, 2))
    assert entry is not None
    assert entry["close"] == pytest.approx(100.0)


@then("the response contains an entry for 2025-01-06 with close price 102.00")
def entry_jan06_102(response: httpx.Response) -> None:
    entry = _entry_for(response, date(2025, 1, 6))
    assert entry is not None
    assert entry["close"] == pytest.approx(102.0)


@then("the response contains an entry for 2025-01-03 with close price 100.00")
def entry_jan03_100(response: httpx.Response) -> None:
    entry = _entry_for(response, date(2025, 1, 3))
    assert entry is not None
    assert entry["close"] == pytest.approx(100.0)


@then("the response contains no entry for 2025-01-03")
def no_entry_jan03(response: httpx.Response) -> None:
    assert _entry_for(response, date(2025, 1, 3)) is None


@then("the response contains no entry for 2025-01-02")
def no_entry_jan02(response: httpx.Response) -> None:
    assert _entry_for(response, date(2025, 1, 2)) is None


@then("the earliest entry in the response is 2025-01-06")
def earliest_is_jan06(response: httpx.Response) -> None:
    prices = response.json()["prices"]
    assert prices
    assert prices[0]["date"] == "2025-01-06"


@then("the response contains no entry for today")
def no_entry_today(response: httpx.Response) -> None:
    assert _entry_for(response, date.today()) is None


@then("the response contains no entry for the previous business day")
def no_entry_prev_bday(response: httpx.Response) -> None:
    assert _entry_for(response, _prev_bday(date.today())) is None


@then("the latest entry in the response is T-2")
def latest_is_t2(response: httpx.Response) -> None:
    t2 = _prev_bday(_prev_bday(date.today()))
    prices = response.json()["prices"]
    assert prices
    assert prices[-1]["date"] == t2.isoformat()


@then("both responses contain an identical list of price entries")
def identical_price_lists(response_pair: tuple[httpx.Response, httpx.Response]) -> None:
    explicit, default = response_pair
    assert explicit.status_code == 200, explicit.text
    assert default.status_code == 200, default.text
    assert explicit.json()["prices"] == default.json()["prices"]


@then('the error identifies "fill" as the invalid parameter')
def error_names_fill(response: httpx.Response) -> None:
    body = response.json()
    locations = [part for item in body["detail"] for part in item["loc"]]
    assert "fill" in locations, body


@then("the data source was never called")
def data_source_never_called(mock_inner_provider: MagicMock) -> None:
    assert mock_inner_provider.get_price_history.call_count == 0
    assert mock_inner_provider.get_current_price.call_count == 0


@then("every returned date is present in the data source observations")
def every_date_is_observed(response: httpx.Response, mock_inner_provider: MagicMock) -> None:
    observed = {d.isoformat() for d, _ in mock_inner_provider.get_price_history.return_value}
    returned = {entry["date"] for entry in response.json()["prices"]}
    assert returned <= observed, f"returned {returned - observed} which are not observations"


@then("both current price responses are identical apart from their timestamps")
def current_price_identical(current_price_pair: tuple[httpx.Response, httpx.Response]) -> None:
    with_fill, without = current_price_pair
    assert with_fill.status_code == without.status_code == 200
    a = {k: v for k, v in with_fill.json().items() if k != "timestamp"}
    b = {k: v for k, v in without.json().items() if k != "timestamp"}
    assert a == b


@then("both FX history responses are identical")
def fx_history_identical(fx_history_pair: tuple[httpx.Response, httpx.Response]) -> None:
    with_fill, without = fx_history_pair
    assert with_fill.status_code == without.status_code == 200
    assert with_fill.json() == without.json()
