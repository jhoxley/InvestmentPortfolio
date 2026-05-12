from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("currency_translation_history.feature")


@given(
    "AAPL has USD price history for 2025-01-02 at 185.50 and 2025-01-03 at 186.20"
)
def aapl_usd_history_jan02_jan03(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 185.50),
        (date(2025, 1, 3), 186.20),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "price": 185.50,
        "currency": "USD",
        "market_state": "closed",
        "as_of_date": date(2025, 1, 3),
    }


@given(
    "the USDGBP FX series has rate 0.7884 on 2025-01-02 and 0.7902 on 2025-01-03"
)
def usdgbp_series_jan02_jan03(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 0.7884),
        (date(2025, 1, 3), 0.7902),
    ]


@given(
    "AAPL has USD price history for 2025-01-17 at 143.10 and 2025-01-20 at 144.50"
)
def aapl_usd_history_jan17_jan20(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 17), 143.10),
        (date(2025, 1, 20), 144.50),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "price": 143.10,
        "currency": "USD",
        "market_state": "closed",
        "as_of_date": date(2025, 1, 20),
    }


@given("the USDGBP FX series has only rate 0.7900 on 2025-01-17")
def usdgbp_only_jan17(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [(date(2025, 1, 17), 0.7900)]


@given(
    "AAPL has USD price history for 2025-01-02 at 145.88 and 2025-01-03 at 146.22"
)
def aapl_usd_history_145_146(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 145.88),
        (date(2025, 1, 3), 146.22),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "price": 145.88,
        "currency": "USD",
        "market_state": "closed",
        "as_of_date": date(2025, 1, 3),
    }


@given("the USDGBP FX series has only rate 0.7895 on 2025-01-03")
def usdgbp_only_jan03(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [(date(2025, 1, 3), 0.7895)]


@given(
    "BARC.L has GBP price history for 2025-01-02 at 2.18 and 2025-01-03 at 2.20"
)
def barcl_gbp_history(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 2.18),
        (date(2025, 1, 3), 2.20),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "price": 2.18,
        "currency": "GBP",
        "market_state": "closed",
        "as_of_date": date(2025, 1, 3),
    }


@when(
    "a client requests AAPL history from 2025-01-02 to 2025-01-03 with currency \"GBP\"",
    target_fixture="response",
)
def get_aapl_history_gbp_jan02_jan03(client_with_fx: TestClient) -> object:
    return client_with_fx.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-02", "to": "2025-01-03", "currency": "GBP"},
    )


@when(
    "a client requests AAPL history from 2025-01-17 to 2025-01-20 with currency \"GBP\"",
    target_fixture="response",
)
def get_aapl_history_gbp_jan17_jan20(client_with_fx: TestClient) -> object:
    return client_with_fx.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-17", "to": "2025-01-20", "currency": "GBP"},
    )


@when(
    "a client requests BARC.L history from 2025-01-02 to 2025-01-03 with currency \"GBP\"",
    target_fixture="response",
)
def get_barcl_history_gbp(client_with_fx: TestClient) -> object:
    return client_with_fx.get(
        "/securities/BARC.L/history",
        params={"from": "2025-01-02", "to": "2025-01-03", "currency": "GBP"},
    )


@then("the response status code is 200")
def status_200(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then('the response history currency is "GBP"')
def response_currency_gbp(response: object) -> None:
    assert response.json()["currency"] == "GBP"  # type: ignore[union-attr]


@then("the entry for 2025-01-02 has close approximately 146.22 and fx_rate 0.7884")
def entry_jan02_translated(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    entry = next(p for p in prices if p["date"] == "2025-01-02")
    assert entry["close"] == pytest.approx(185.50 * 0.7884, rel=1e-3)
    assert entry["fx_rate"] == pytest.approx(0.7884, rel=1e-4)


@then("the entry for 2025-01-03 has close approximately 147.01 and fx_rate 0.7902")
def entry_jan03_translated(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    entry = next(p for p in prices if p["date"] == "2025-01-03")
    assert entry["close"] == pytest.approx(186.20 * 0.7902, rel=1e-3)
    assert entry["fx_rate"] == pytest.approx(0.7902, rel=1e-4)


@then("the entry for 2025-01-17 has fx_rate 0.7900")
def entry_jan17_fx(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    entry = next(p for p in prices if p["date"] == "2025-01-17")
    assert entry["fx_rate"] == pytest.approx(0.7900, rel=1e-4)


@then("the entry for 2025-01-20 has fx_rate 0.7900")
def entry_jan20_fx(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    entry = next(p for p in prices if p["date"] == "2025-01-20")
    assert entry["fx_rate"] == pytest.approx(0.7900, rel=1e-4)


@then("the entry for 2025-01-02 has fx_rate 0.7895")
def entry_jan02_backward_fx(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    entry = next(p for p in prices if p["date"] == "2025-01-02")
    assert entry["fx_rate"] == pytest.approx(0.7895, rel=1e-4)


@then("the entry for 2025-01-03 has fx_rate 0.7895")
def entry_jan03_backward_fx(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    entry = next(p for p in prices if p["date"] == "2025-01-03")
    assert entry["fx_rate"] == pytest.approx(0.7895, rel=1e-4)


@then("all entries have null fx_rate")
def all_fx_rate_null(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    for entry in prices:
        assert entry.get("fx_rate") is None, f"Expected fx_rate=null on {entry['date']}"
