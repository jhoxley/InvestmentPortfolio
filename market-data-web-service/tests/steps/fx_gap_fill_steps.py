from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("fx_gap_fill.feature")


@given("the FX provider returns rates for GBPUSD on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only")
def mock_fx_gbpusd_gap(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [
        (date(2025, 1, 2), 1.25),
        (date(2025, 1, 6), 1.27),
    ]


@when(
    "a client requests GBPUSD history from 2025-01-02 to 2025-01-06",
    target_fixture="response",
)
def get_fx_history_jan02_jan06(client_with_gap_fill: TestClient) -> object:
    return client_with_gap_fill.get(
        "/fx/GBPUSD/history", params={"from": "2025-01-02", "to": "2025-01-06"}
    )


@then("the FX response contains 3 rate entries")
def assert_fx_3_entries(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]
    assert len(response.json()["rates"]) == 3  # type: ignore[union-attr]


@then("the rate for 2025-01-03 is 1.25")
def assert_rate_jan03_125(response: object) -> None:
    rates = {r["date"]: r["rate"] for r in response.json()["rates"]}  # type: ignore[union-attr]
    assert rates["2025-01-03"] == pytest.approx(1.25)
