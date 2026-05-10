from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.cache.repository import CacheRepository

scenarios("cache_full_hit.feature")

_AAPL_RECORDS_Q1: list[tuple[date, float]] = [
    (date(2025, 1, 2), 185.50),
    (date(2025, 1, 3), 186.20),
    (date(2025, 1, 6), 188.00),
    (date(2025, 3, 31), 192.10),
]

_AAPL_RECORDS_FULL_YEAR: list[tuple[date, float]] = [
    (date(2025, 1, 2), 185.50),
    (date(2025, 1, 3), 186.20),
    (date(2025, 3, 3), 189.00),
    (date(2025, 6, 30), 195.00),
    (date(2025, 12, 31), 210.00),
]


@given('a cache file exists for ticker "AAPL" covering dates "2025-01-02" to "2025-03-31"')
def seed_aapl_q1(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("AAPL", _AAPL_RECORDS_Q1)


@given('a cache file exists for ticker "AAPL" covering dates "2025-01-02" to "2025-12-31"')
def seed_aapl_full_year(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("AAPL", _AAPL_RECORDS_FULL_YEAR)


@when(
    'a consumer requests price history for "AAPL" from "2025-01-02" to "2025-03-31"',
    target_fixture="response",
)
def get_aapl_history_q1(client_with_cache: TestClient) -> object:
    return client_with_cache.get(
        "/securities/AAPL/history", params={"from": "2025-01-02", "to": "2025-03-31"}
    )


@when(
    'a consumer requests price history for "AAPL" from "2025-03-03" to "2025-06-30"',
    target_fixture="response",
)
def get_aapl_history_subrange(client_with_cache: TestClient) -> object:
    return client_with_cache.get(
        "/securities/AAPL/history", params={"from": "2025-03-03", "to": "2025-06-30"}
    )


@then("the response status code is 200")
def status_200_cache(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the response prices list contains the cached entries")
def prices_match_cache(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    prices = data["prices"]
    assert len(prices) == len(_AAPL_RECORDS_Q1)
    for actual, (expected_date, expected_close) in zip(prices, _AAPL_RECORDS_Q1, strict=True):
        assert actual["date"] == expected_date.isoformat()
        assert abs(actual["close"] - expected_close) < 0.001


@then("the response prices list contains only entries within the requested range")
def prices_within_subrange(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    prices = data["prices"]
    assert len(prices) > 0
    for entry in prices:
        d = date.fromisoformat(entry["date"])
        assert date(2025, 3, 3) <= d <= date(2025, 6, 30)


@then("no external call to YFinance is made")
def no_yfinance_call(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.assert_not_called()
