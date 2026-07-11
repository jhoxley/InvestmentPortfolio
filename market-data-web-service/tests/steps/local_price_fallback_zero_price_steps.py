from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.exceptions import DataNotFoundError
from app.providers import PricingProvider
from app.services.minor_unit import SubUnitNormaliser

scenarios("local_price_fallback_zero_price.feature")

_FALLBACK_CONFIG_ZERO_LOCAL_ONLY = Path("tests/fixtures/fallback_config_zero_local_only.json")
_FALLBACK_CONFIG_ZERO_FALLBACK = Path("tests/fixtures/fallback_config_zero_fallback.json")


def _make_zero_price_client(config_path: Path) -> TestClient:
    from app.api.securities import get_pricing_service
    from app.main import app
    from app.providers.fallback_provider import FallbackPricingProvider
    from app.repositories.fallback_config import FallbackConfigRepository
    from app.services.gap_fill import GapFillService
    from app.services.pricing_service import PricingService

    mock_inner = MagicMock(spec=PricingProvider)
    mock_inner.get_price_history.side_effect = DataNotFoundError("PRIV01")
    mock_inner.get_current_price.side_effect = DataNotFoundError("PRIV01")

    fallback_repo = FallbackConfigRepository(config_path)

    def override_pricing() -> PricingService:
        provider = FallbackPricingProvider(inner=mock_inner, fallback_repo=fallback_repo)
        return PricingService(
            provider=provider, gap_fill=GapFillService(), normaliser=SubUnitNormaliser()
        )

    app.dependency_overrides[get_pricing_service] = override_pricing
    return TestClient(app)


@given(
    'a fallback configuration maps "PRIV01" to a local CSV file of all-zero prices '
    "with use_local_only set",
    target_fixture="zero_price_client",
)
def fallback_zero_local_only() -> TestClient:
    return _make_zero_price_client(_FALLBACK_CONFIG_ZERO_LOCAL_ONLY)


@given(
    'the primary data source returns no current price for ticker "PRIV01"',
    target_fixture="zero_price_client",
)
def primary_no_current_priv01() -> TestClient:
    return _make_zero_price_client(_FALLBACK_CONFIG_ZERO_FALLBACK)


@given(
    'a fallback configuration maps "PRIV01" to a local CSV file of all-zero prices '
    "without use_local_only set"
)
def fallback_zero_non_local_only() -> None:
    pass


@when(
    'a consumer requests the current price for "PRIV01"',
    target_fixture="response",
)
def get_priv01_current_price(zero_price_client: TestClient) -> object:
    from app.main import app

    resp = zero_price_client.get("/securities/PRIV01/price")
    app.dependency_overrides.clear()
    return resp


@then("the response status is 200")
def status_200(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the response price is 0.00")
def price_is_zero(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert data["price"] == 0.0


@then("the response status is 404")
def status_404(response: object) -> None:
    assert response.status_code == 404  # type: ignore[union-attr]
