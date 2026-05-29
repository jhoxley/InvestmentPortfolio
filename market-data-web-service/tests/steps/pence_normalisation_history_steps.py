from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pytest_bdd import given, scenarios, then, when

scenarios("pence_normalisation_history.feature")

_D20 = date(2026, 5, 20)
_D21 = date(2026, 5, 21)
_D22 = date(2026, 5, 22)


@pytest.fixture()
def pence_history_client(mock_inner_provider: MagicMock) -> Generator[TestClient, None, None]:
    from app.api.securities import get_pricing_service
    from app.main import app
    from app.services.gap_fill import GapFillService
    from app.services.minor_unit import SubUnitNormaliser
    from app.services.pricing_service import PricingService

    def override() -> PricingService:
        return PricingService(
            provider=mock_inner_provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
        )

    app.dependency_overrides[get_pricing_service] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@given('the history source returns "GBp" prices for "CNKY.L" on 2026-05-20/21/22')
def mock_gbp_pence_history_cnky(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (_D20, 31000.0),
        (_D21, 31100.0),
        (_D22, 31140.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "price": 31140,
        "currency": "GBp",
        "market_state": "closed",
        "as_of_date": _D22,
    }


@given('the history source returns "EUR" prices for a ticker on 2026-05-20 and 2026-05-21')
def mock_eur_history(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (_D20, 100.0),
        (_D21, 101.0),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "price": 100.0,
        "currency": "EUR",
        "market_state": "closed",
        "as_of_date": _D21,
    }


@when(
    'a consumer requests price history for "CNKY.L" from 2026-05-20 to 2026-05-22',
    target_fixture="response",
)
def get_cnky_history(pence_history_client: TestClient) -> Response:
    return pence_history_client.get(
        "/securities/CNKY.L/history",
        params={"from": "2026-05-20", "to": "2026-05-22"},
    )


@when(
    "a consumer requests price history from 2026-05-20 to 2026-05-21",
    target_fixture="response",
)
def get_eur_history(pence_history_client: TestClient) -> Response:
    return pence_history_client.get(
        "/securities/CNKY.L/history",
        params={"from": "2026-05-20", "to": "2026-05-21"},
    )


@then("the response status code is 200")
def history_status_200(response: Response) -> None:
    assert response.status_code == 200


@then('the history response currency is "GBP"')
def history_currency_gbp(response: Response) -> None:
    assert response.json()["currency"] == "GBP"


@then('the history response currency is "EUR"')
def history_currency_eur(response: Response) -> None:
    assert response.json()["currency"] == "EUR"


@then("the history close on 2026-05-20 is 310.00")
def history_close_d20_gbp(response: Response) -> None:
    prices = response.json()["prices"]
    entry = next(p for p in prices if p["date"] == "2026-05-20")
    assert entry["close"] == pytest.approx(310.00, rel=1e-4)


@then("the history close on 2026-05-21 is 311.00")
def history_close_d21_gbp(response: Response) -> None:
    prices = response.json()["prices"]
    entry = next(p for p in prices if p["date"] == "2026-05-21")
    assert entry["close"] == pytest.approx(311.00, rel=1e-4)


@then("the history close on 2026-05-22 is 311.40")
def history_close_d22_gbp(response: Response) -> None:
    prices = response.json()["prices"]
    entry = next(p for p in prices if p["date"] == "2026-05-22")
    assert entry["close"] == pytest.approx(311.40, rel=1e-4)


@then("the history close on 2026-05-20 is 100.00")
def history_close_d20_eur(response: Response) -> None:
    prices = response.json()["prices"]
    entry = next(p for p in prices if p["date"] == "2026-05-20")
    assert entry["close"] == pytest.approx(100.00, rel=1e-4)


@then("the history close on 2026-05-21 is 101.00")
def history_close_d21_eur(response: Response) -> None:
    prices = response.json()["prices"]
    entry = next(p for p in prices if p["date"] == "2026-05-21")
    assert entry["close"] == pytest.approx(101.00, rel=1e-4)
