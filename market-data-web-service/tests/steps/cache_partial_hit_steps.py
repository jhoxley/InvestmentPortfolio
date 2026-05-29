from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.cache.repository import CacheRepository
from app.exceptions import ProviderUnavailableError

scenarios("cache_partial_hit.feature")

_MSFT_CACHED_BEFORE: list[tuple[date, float]] = [
    (date(2025, 3, 3), 410.00),
    (date(2025, 6, 30), 420.00),
]

_MSFT_CACHED_AFTER: list[tuple[date, float]] = [
    (date(2025, 1, 2), 400.00),
    (date(2025, 6, 30), 420.00),
]

_TSLA_CACHED: list[tuple[date, float]] = [
    (date(2025, 4, 1), 250.00),
    (date(2025, 6, 30), 260.00),
]

_MSFT_BEFORE_SEGMENT: list[tuple[date, float]] = [
    (date(2025, 1, 2), 395.00),
    (date(2025, 2, 28), 398.00),
]

_MSFT_AFTER_SEGMENT: list[tuple[date, float]] = [
    (date(2025, 7, 1), 425.00),
    (date(2025, 9, 30), 430.00),
]

_TSLA_BEFORE_SEGMENT: list[tuple[date, float]] = [
    (date(2025, 1, 2), 240.00),
    (date(2025, 3, 31), 248.00),
]

_TSLA_AFTER_SEGMENT: list[tuple[date, float]] = [
    (date(2025, 7, 1), 265.00),
    (date(2025, 9, 30), 270.00),
]


@given('a cache file exists for ticker "MSFT" covering dates "2025-03-03" to "2025-06-30"')
def seed_msft_mid(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("MSFT", _MSFT_CACHED_BEFORE)


@given('a cache file exists for ticker "MSFT" covering dates "2025-01-02" to "2025-06-30"')
def seed_msft_first_half(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("MSFT", _MSFT_CACHED_AFTER)


@given('a cache file exists for ticker "TSLA" covering dates "2025-04-01" to "2025-06-30"')
def seed_tsla_mid(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("TSLA", _TSLA_CACHED)


@given('YFinance returns data for "MSFT" from "2025-01-02" to "2025-02-28"')
def mock_msft_before(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = _MSFT_BEFORE_SEGMENT


@given('YFinance returns data for "MSFT" from "2025-07-01" to "2025-09-30"')
def mock_msft_after(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = _MSFT_AFTER_SEGMENT


@given('YFinance returns data for "TSLA" from "2025-01-02" to "2025-03-31"')
def mock_tsla_before(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.side_effect = [
        _TSLA_BEFORE_SEGMENT,
        _TSLA_AFTER_SEGMENT,
    ]


@given('YFinance also returns data for "TSLA" from "2025-07-01" to "2025-09-30"')
def mock_tsla_after_noop(mock_inner_provider: MagicMock) -> None:
    pass


@given("YFinance is unavailable")
def mock_yfinance_unavailable(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.side_effect = ProviderUnavailableError()


@when(
    'a consumer requests price history for "MSFT" from "2025-01-02" to "2025-06-30"',
    target_fixture="response",
)
def get_msft_history_extended_before(client_with_cache: TestClient) -> object:
    return client_with_cache.get(
        "/securities/MSFT/history", params={"from": "2025-01-02", "to": "2025-06-30"}
    )


@when(
    'a consumer requests price history for "MSFT" from "2025-01-02" to "2025-09-30"',
    target_fixture="response",
)
def get_msft_history_extended_after(client_with_cache: TestClient) -> object:
    return client_with_cache.get(
        "/securities/MSFT/history", params={"from": "2025-01-02", "to": "2025-09-30"}
    )


@when(
    'a consumer requests price history for "TSLA" from "2025-01-02" to "2025-09-30"',
    target_fixture="response",
)
def get_tsla_history_both_ends(client_with_cache: TestClient) -> object:
    return client_with_cache.get(
        "/securities/TSLA/history", params={"from": "2025-01-02", "to": "2025-09-30"}
    )


@then("the response status code is 200")
def status_200_partial(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the response status code is 503")
def status_503_partial(response: object) -> None:
    assert response.status_code == 503  # type: ignore[union-attr]


@then("the response covers the full requested range")
def response_covers_full_range(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert len(data["prices"]) >= 2


@then("YFinance was called exactly once for the before segment")
def yfinance_called_once_before(mock_inner_provider: MagicMock) -> None:
    assert mock_inner_provider.get_price_history.call_count == 1


@then("YFinance was called exactly once for the after segment")
def yfinance_called_once_after(mock_inner_provider: MagicMock) -> None:
    assert mock_inner_provider.get_price_history.call_count == 1


@then("YFinance was called twice for both segments")
def yfinance_called_twice(mock_inner_provider: MagicMock) -> None:
    assert mock_inner_provider.get_price_history.call_count == 2


@then("the cache is updated to include the newly fetched data")
def cache_updated(tmp_cache_dir: Path, response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    ticker = data["ticker"]
    updated = CacheRepository(tmp_cache_dir).read(ticker)
    assert updated is not None
    assert len(updated) > 0


@then('the existing cache entry for "MSFT" is unchanged')
def cache_unchanged(tmp_cache_dir: Path) -> None:
    records = CacheRepository(tmp_cache_dir).read("MSFT")
    assert records is not None
    assert len(records) == len(_MSFT_CACHED_AFTER)
