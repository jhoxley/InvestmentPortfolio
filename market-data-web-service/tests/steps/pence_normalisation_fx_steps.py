from collections.abc import Generator
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pytest_bdd import given, scenarios, then, when

scenarios("pence_normalisation_fx.feature")

_D22 = date(2026, 5, 22)


@pytest.fixture()
def pence_fx_client(
    mock_inner_provider: MagicMock,
    mock_fx_provider: MagicMock,
    tmp_cache_dir: Path,
) -> Generator[TestClient, None, None]:
    from app.api.fx import get_fx_provider
    from app.api.securities import get_currency_service, get_pricing_service
    from app.cache.repository import CacheRepository
    from app.main import app
    from app.providers.cached_provider import CachedPricingProvider
    from app.services.currency_service import CurrencyService
    from app.services.fx_aligner import FxAligner
    from app.services.gap_fill import GapFillService
    from app.services.minor_unit import SubUnitNormaliser
    from app.services.pricing_service import PricingService

    def override_pricing() -> PricingService:
        return PricingService(
            provider=mock_inner_provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
        )

    def override_currency() -> CurrencyService:
        repo = CacheRepository(tmp_cache_dir)
        fx_prov = CachedPricingProvider(mock_fx_provider, repo)
        return CurrencyService(fx_provider=fx_prov, aligner=FxAligner(), gap_fill=GapFillService())

    def override_fx_provider() -> CachedPricingProvider:
        repo = CacheRepository(tmp_cache_dir)
        return CachedPricingProvider(mock_fx_provider, repo)

    app.dependency_overrides[get_pricing_service] = override_pricing
    app.dependency_overrides[get_currency_service] = override_currency
    app.dependency_overrides[get_fx_provider] = override_fx_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@given('the pricing source returns "GBp" history with raw close 31140 on 2026-05-22')
def mock_gbp_pence_fx_history(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [(_D22, 31140.0)]
    mock_inner_provider.get_current_price.return_value = {
        "price": 31140,
        "currency": "GBp",
        "market_state": "closed",
        "as_of_date": _D22,
    }


@given('the pricing source returns a current price of 31140 in currency "GBp"')
def mock_gbp_pence_current_fx(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_current_price.return_value = {
        "price": 31140,
        "currency": "GBp",
        "market_state": "closed",
        "as_of_date": _D22,
    }


@given("an FX rate of 1.25 from GBP to USD exists for 2026-05-22")
def mock_gbpusd_rate(mock_fx_provider: MagicMock) -> None:
    mock_fx_provider.get_price_history.return_value = [(_D22, 1.25)]


@when(
    'a consumer requests pence-quoted history with currency "USD" on 2026-05-22',
    target_fixture="response",
)
def get_pence_history_usd(pence_fx_client: TestClient) -> Response:
    return pence_fx_client.get(
        "/securities/CNKY.L/history",
        params={"from": "2026-05-22", "to": "2026-05-22", "currency": "USD"},
    )


@when(
    'a consumer requests the current price for that ticker with currency "USD"',
    target_fixture="response",
)
def get_pence_current_usd(pence_fx_client: TestClient) -> Response:
    return pence_fx_client.get("/securities/CNKY.L/price?currency=USD")


@then("the response status code is 200")
def fx_status_200(response: Response) -> None:
    assert response.status_code == 200


@then('the fx history response currency is "USD"')
def fx_history_currency_usd(response: Response) -> None:
    assert response.json()["currency"] == "USD"


@then("the fx history close on 2026-05-22 is 389.25")
def fx_history_close_389(response: Response) -> None:
    prices = response.json()["prices"]
    entry = next(p for p in prices if p["date"] == "2026-05-22")
    assert entry["close"] == pytest.approx(389.25, rel=1e-3)


@then('the fx response currency is "USD"')
def fx_response_currency_usd(response: Response) -> None:
    assert response.json()["currency"] == "USD"


@then("the fx response price is 389.25")
def fx_response_price_389(response: Response) -> None:
    assert response.json()["price"] == pytest.approx(389.25, rel=1e-3)
