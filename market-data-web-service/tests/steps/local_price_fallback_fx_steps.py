from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.exceptions import DataNotFoundError
from app.providers import PricingProvider
from app.services.minor_unit import SubUnitNormaliser

scenarios("local_price_fallback_fx.feature")

_FALLBACK_CONFIG = Path("tests/fixtures/fallback_config.json")


@given(
    'the primary data source returns no price history for ticker "PRIV01"',
    target_fixture="fx_mocks",
)
def primary_no_data_priv01_fx() -> tuple[MagicMock, MagicMock]:
    mock_inner = MagicMock(spec=PricingProvider)
    mock_inner.get_price_history.side_effect = DataNotFoundError("PRIV01")
    mock_inner.get_current_price.side_effect = DataNotFoundError("PRIV01")

    mock_fx = MagicMock(spec=PricingProvider)
    return mock_inner, mock_fx


@given(
    'a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"'
)
def fallback_config_gbp_fx() -> None:
    pass


@given('the local file contains a price of 100.00 on "2025-01-02"')
def local_file_100_jan02() -> None:
    pass


@given(
    'the FX rate for GBPUSD on "2025-01-02" is 1.25',
    target_fixture="fx_client",
)
def fx_rate_gbpusd_125(fx_mocks: tuple[MagicMock, MagicMock]) -> TestClient:
    from app.api.securities import get_currency_service, get_pricing_service
    from app.main import app
    from app.providers.fallback_provider import FallbackPricingProvider
    from app.repositories.fallback_config import FallbackConfigRepository
    from app.services.currency_service import CurrencyService
    from app.services.fx_aligner import FxAligner
    from app.services.gap_fill import GapFillService
    from app.services.pricing_service import PricingService

    mock_inner, mock_fx = fx_mocks
    mock_fx.get_price_history.return_value = [(date(2025, 1, 2), 1.25)]

    fallback_repo = FallbackConfigRepository(_FALLBACK_CONFIG)

    def override_pricing() -> PricingService:
        provider = FallbackPricingProvider(inner=mock_inner, fallback_repo=fallback_repo)
        return PricingService(
            provider=provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
        )

    def override_currency() -> CurrencyService:
        return CurrencyService(
            fx_provider=mock_fx, aligner=FxAligner(), gap_fill=GapFillService()
        )

    app.dependency_overrides[get_pricing_service] = override_pricing
    app.dependency_overrides[get_currency_service] = override_currency
    return TestClient(app)


@when(
    'a consumer requests price history for "PRIV01" from "2025-01-02" to "2025-01-02"'
    ' with currency "USD"',
    target_fixture="response",
)
def get_priv01_history_gbp_to_usd(fx_client: TestClient) -> object:
    from app.main import app

    resp = fx_client.get(
        "/securities/PRIV01/history",
        params={"from": "2025-01-02", "to": "2025-01-02", "currency": "USD"},
    )
    app.dependency_overrides.clear()
    return resp


@then('the response price for "2025-01-02" is 125.00')
def price_jan02_is_125(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    prices = {p["date"]: p["close"] for p in data["prices"]}
    assert abs(prices["2025-01-02"] - 125.00) < 0.01


@then('the response currency is "USD"')
def currency_usd(response: object) -> None:
    assert response.json()["currency"] == "USD"  # type: ignore[union-attr]
