from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pytest_bdd import given, scenarios, then, when

scenarios("pence_normalisation_current.feature")

_AS_OF = date(2026, 5, 26)


@pytest.fixture()
def pence_current_client(mock_inner_provider: MagicMock) -> Generator[TestClient, None, None]:
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


@given('the pricing source returns a price of 31140 in currency "GBp" for ticker "CNKY.L"')
def mock_gbp_pence_cnky(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 31140,
        "currency": "GBp",
        "market_state": "closed",
        "as_of_date": _AS_OF,
    }


@given('the pricing source returns a price of 150.00 in currency "USD" for ticker "AAPL"')
def mock_usd_aapl(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 150.00,
        "currency": "USD",
        "market_state": "closed",
        "as_of_date": _AS_OF,
    }


@given('the pricing source returns a price of 15000 in currency "USd" for a ticker')
def mock_usd_cents(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 15000,
        "currency": "USd",
        "market_state": "closed",
        "as_of_date": _AS_OF,
    }


@given('the pricing source returns a price of 311.40 in currency "GBP" for a ticker')
def mock_gbp_major(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 311.40,
        "currency": "GBP",
        "market_state": "closed",
        "as_of_date": _AS_OF,
    }


@given('the pricing source returns a price of 31140 in currency "gBp" for a ticker')
def mock_gbp_pence_variant_casing(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 31140,
        "currency": "gBp",
        "market_state": "closed",
        "as_of_date": _AS_OF,
    }


@when('a consumer requests the current price for "CNKY.L"', target_fixture="response")
def get_cnky_current_price(pence_current_client: TestClient) -> Response:
    return pence_current_client.get("/securities/CNKY.L/price")


@when('a consumer requests the current price for "AAPL"', target_fixture="response")
def get_aapl_current_price(pence_current_client: TestClient) -> Response:
    return pence_current_client.get("/securities/AAPL/price")


@when("a consumer requests the current price for that ticker", target_fixture="response")
def get_that_ticker_current_price(pence_current_client: TestClient) -> Response:
    return pence_current_client.get("/securities/CNKY.L/price")


@then("the response status code is 200")
def pence_status_200(response: Response) -> None:
    assert response.status_code == 200


@then('the pence response currency is "GBP"')
def pence_currency_gbp(response: Response) -> None:
    assert response.json()["currency"] == "GBP"


@then('the pence response currency is "USD"')
def pence_currency_usd(response: Response) -> None:
    assert response.json()["currency"] == "USD"


@then("the pence response price is 311.40")
def pence_price_311_40(response: Response) -> None:
    assert response.json()["price"] == pytest.approx(311.40, rel=1e-4)


@then("the pence response price is 150.00")
def pence_price_150(response: Response) -> None:
    assert response.json()["price"] == pytest.approx(150.00, rel=1e-4)
