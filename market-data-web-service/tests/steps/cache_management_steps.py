from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.cache.repository import CacheRepository

scenarios("cache_management.feature")

_SAMPLE_RECORDS: list[tuple[date, float]] = [
    (date(2025, 1, 2), 100.0),
    (date(2025, 1, 3), 101.0),
]


@given('a cache file exists for ticker "AAPL"')
def seed_aapl(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("AAPL", _SAMPLE_RECORDS)


@given('no cache file exists for ticker "XYZ"')
def no_xyz_cache(tmp_cache_dir: Path) -> None:
    path = tmp_cache_dir / "XYZ.csv"
    assert not path.exists()


@given('cache files exist for tickers "AAPL", "MSFT", and "TSLA"')
def seed_multiple(tmp_cache_dir: Path) -> None:
    repo = CacheRepository(tmp_cache_dir)
    for ticker in ("AAPL", "MSFT", "TSLA"):
        repo.write(ticker, _SAMPLE_RECORDS)


@given("no cache files exist")
def no_cache_files(tmp_cache_dir: Path) -> None:
    assert len(list(tmp_cache_dir.glob("*.csv"))) == 0


@when("an operator calls DELETE /cache/AAPL", target_fixture="response")
def delete_aapl(client_with_cache: TestClient) -> object:
    return client_with_cache.delete("/cache/AAPL")


@when("an operator calls DELETE /cache/XYZ", target_fixture="response")
def delete_xyz(client_with_cache: TestClient) -> object:
    return client_with_cache.delete("/cache/XYZ")


@when("an operator calls DELETE /cache", target_fixture="response")
def delete_all(client_with_cache: TestClient) -> object:
    return client_with_cache.delete("/cache")


@then("the response status code is 200")
def status_200_mgmt(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the response confirms the entry was deleted")
def confirms_deleted(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data["ticker"] == "AAPL"
    assert data["deleted"] is True


@then("the response indicates no cache was found")
def indicates_not_found(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data["ticker"] == "XYZ"
    assert data["deleted"] is False


@then('the cache file for "AAPL" is removed')
def aapl_cache_removed(tmp_cache_dir: Path) -> None:
    assert CacheRepository(tmp_cache_dir).read("AAPL") is None


@then("the response confirms 3 entries were deleted")
def confirms_three_deleted(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data["deleted_count"] == 3


@then("all cache files are removed")
def all_cache_removed(tmp_cache_dir: Path) -> None:
    assert len(list(tmp_cache_dir.glob("*.csv"))) == 0


@then("the response confirms 0 entries were deleted")
def confirms_zero_deleted(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data["deleted_count"] == 0
