from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("fx_history.feature")


@given("the USDGBP FX cache has no data")
def fx_cache_empty() -> None:
    pass  # tmp_cache_dir starts empty for each test


@given("the provider has USDGBP rates 0.7884 on 2025-01-02 and 0.7902 on 2025-01-03")
def fx_provider_usdgbp_rates(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 0.7884),
        (date(2025, 1, 3), 0.7902),
    ]


@given("the USDGBP FX cache has rates 0.7884 on 2025-01-02 and 0.7902 on 2025-01-03")
def seed_usdgbp_cache(tmp_cache_dir: Path) -> None:
    from app.cache.repository import CacheRepository

    repo = CacheRepository(tmp_cache_dir)
    repo.write("USDGBP", [(date(2025, 1, 2), 0.7884), (date(2025, 1, 3), 0.7902)])


@when(
    'a client requests FX history for "USDGBP" from 2025-01-02 to 2025-01-03',
    target_fixture="response",
)
def get_fx_usdgbp(client_with_fx: TestClient) -> object:
    return client_with_fx.get(
        "/fx/USDGBP/history",
        params={"from": "2025-01-02", "to": "2025-01-03"},
    )


@when(
    'a client requests FX history for "USDZZ" from 2025-01-02 to 2025-01-03',
    target_fixture="response",
)
def get_fx_usdzz(client_with_fx: TestClient) -> object:
    return client_with_fx.get(
        "/fx/USDZZ/history",
        params={"from": "2025-01-02", "to": "2025-01-03"},
    )


@when(
    'a client requests FX history for "USDGBP" from 2025-03-31 to 2025-01-02',
    target_fixture="response",
)
def get_fx_reversed_dates(client_with_fx: TestClient) -> object:
    return client_with_fx.get(
        "/fx/USDGBP/history",
        params={"from": "2025-03-31", "to": "2025-01-02"},
    )


@then("the FX response status code is 200")
def fx_status_200(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the FX response status code is 422")
def fx_status_422(response: object) -> None:
    assert response.status_code == 422  # type: ignore[union-attr]


@then('the FX response pair is "USDGBP"')
def fx_pair_usdgbp(response: object) -> None:
    assert response.json()["pair"] == "USDGBP"  # type: ignore[union-attr]


@then('the FX response base_currency is "USD"')
def fx_base_usd(response: object) -> None:
    assert response.json()["base_currency"] == "USD"  # type: ignore[union-attr]


@then('the FX response quote_currency is "GBP"')
def fx_quote_gbp(response: object) -> None:
    assert response.json()["quote_currency"] == "GBP"  # type: ignore[union-attr]


@then("the FX rates list has 2 entries")
def fx_rates_two_entries(response: object) -> None:
    assert len(response.json()["rates"]) == 2  # type: ignore[union-attr]


@then("the FX rate on 2025-01-02 is 0.7884")
def fx_rate_jan02(response: object) -> None:
    rates = response.json()["rates"]  # type: ignore[union-attr]
    entry = next(r for r in rates if r["date"] == "2025-01-02")
    assert entry["rate"] == pytest.approx(0.7884, rel=1e-4)


@then("the FX rate on 2025-01-03 is 0.7902")
def fx_rate_jan03(response: object) -> None:
    rates = response.json()["rates"]  # type: ignore[union-attr]
    entry = next(r for r in rates if r["date"] == "2025-01-03")
    assert entry["rate"] == pytest.approx(0.7902, rel=1e-4)


@then("the mock FX provider was not called")
def fx_provider_not_called(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.assert_not_called()
