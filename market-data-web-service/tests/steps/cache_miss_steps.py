from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.cache.repository import CacheRepository

scenarios("cache_miss.feature")

_GOOG_RECORDS: list[tuple[date, float]] = [
    (date(2025, 1, 2), 175.00),
    (date(2025, 1, 3), 176.50),
    (date(2025, 3, 31), 180.00),
]


@given('no cache file exists for ticker "GOOG"')
def no_goog_cache(tmp_cache_dir: Path) -> None:
    path = tmp_cache_dir / "GOOG.csv"
    assert not path.exists()


@given('YFinance returns data for "GOOG" from "2025-01-02" to "2025-03-31"')
def mock_goog_data(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = _GOOG_RECORDS


@when(
    'a consumer requests price history for "GOOG" from "2025-01-02" to "2025-03-31"',
    target_fixture="response",
)
def get_goog_history(client_with_cache: TestClient) -> object:
    return client_with_cache.get(
        "/securities/GOOG/history", params={"from": "2025-01-02", "to": "2025-03-31"}
    )


@then("the response status code is 200")
def status_200_miss(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the full date range is fetched from YFinance")
def full_range_fetched(mock_inner_provider: MagicMock) -> None:
    assert mock_inner_provider.get_price_history.call_count == 1
    call_args = mock_inner_provider.get_price_history.call_args
    assert call_args[0][1] == date(2025, 1, 2)
    assert call_args[0][2] == date(2025, 3, 31)


@then('a cache file is created for "GOOG"')
def cache_file_created(tmp_cache_dir: Path) -> None:
    records = CacheRepository(tmp_cache_dir).read("GOOG")
    assert records is not None
    assert len(records) == len(_GOOG_RECORDS)


@then("the response contains the correct price data")
def correct_price_data(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    prices = data["prices"]
    assert len(prices) == len(_GOOG_RECORDS)
    for actual, (expected_date, expected_close) in zip(prices, _GOOG_RECORDS, strict=True):
        assert actual["date"] == expected_date.isoformat()
        assert abs(actual["close"] - expected_close) < 0.001
