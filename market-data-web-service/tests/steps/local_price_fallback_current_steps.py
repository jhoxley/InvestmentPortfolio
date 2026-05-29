from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.exceptions import DataNotFoundError
from app.providers import PricingProvider
from app.services.minor_unit import SubUnitNormaliser

scenarios("local_price_fallback_current.feature")

_FALLBACK_CONFIG_150 = Path("tests/fixtures/fallback_config_150.json")
_FALLBACK_CONFIG = Path("tests/fixtures/fallback_config.json")


def _make_current_client(config_path: Path) -> tuple[TestClient, MagicMock]:
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
            provider=provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
        )

    app.dependency_overrides[get_pricing_service] = override_pricing
    return TestClient(app), mock_inner


# --- Scenario 1: current price from local file ---

@given(
    'the primary data source returns no current price for ticker "PRIV01"',
    target_fixture="current_client",
)
def primary_no_current_priv01() -> tuple[TestClient, MagicMock]:
    return _make_current_client(_FALLBACK_CONFIG_150)


@given(
    'a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"'
)
def fallback_config_priv01_gbp_current() -> None:
    pass


@given('the most recent entry in the local file is "2025-01-06" at 150.00')
def most_recent_entry_150() -> None:
    pass


@when(
    'a consumer requests the current price for "PRIV01"',
    target_fixture="response",
)
def get_priv01_current_price(current_client: tuple[TestClient, MagicMock]) -> object:
    from app.main import app

    client, _ = current_client
    resp = client.get("/securities/PRIV01/price")
    app.dependency_overrides.clear()
    return resp


@then("the response status is 200")
def status_200_current(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then("the response price is 150.00")
def price_is_150(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert abs(data["price"] - 150.00) < 0.01


@then('the response currency is "GBP"')
def currency_gbp_current(response: object) -> None:
    assert response.json()["currency"] == "GBP"  # type: ignore[union-attr]


@then('the response as-of date is "2025-01-06"')
def as_of_date_jan06(response: object) -> None:
    assert response.json()["as_of_date"] == "2025-01-06"  # type: ignore[union-attr]


@then('the response market status is "closed"')
def market_status_closed(response: object) -> None:
    assert response.json()["market_status"] == "closed"  # type: ignore[union-attr]


# --- Scenario 2: unknown current price no fallback ---

@given(
    'the primary data source returns no current price for ticker "UNKNOWN"',
    target_fixture="unknown_current_client",
)
def primary_no_current_unknown() -> TestClient:
    from app.api.securities import get_pricing_service
    from app.main import app
    from app.providers.fallback_provider import FallbackPricingProvider
    from app.repositories.fallback_config import FallbackConfigRepository
    from app.services.gap_fill import GapFillService
    from app.services.pricing_service import PricingService

    mock_inner = MagicMock(spec=PricingProvider)
    mock_inner.get_price_history.side_effect = DataNotFoundError("UNKNOWN")
    mock_inner.get_current_price.side_effect = DataNotFoundError("UNKNOWN")

    fallback_repo = FallbackConfigRepository(_FALLBACK_CONFIG)

    def override_pricing() -> PricingService:
        provider = FallbackPricingProvider(inner=mock_inner, fallback_repo=fallback_repo)
        return PricingService(
            provider=provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
        )

    app.dependency_overrides[get_pricing_service] = override_pricing
    return TestClient(app)


@given('no fallback configuration exists for "UNKNOWN"')
def no_fallback_unknown_current() -> None:
    pass


@when(
    'a consumer requests the current price for "UNKNOWN"',
    target_fixture="response",
)
def get_unknown_current(unknown_current_client: TestClient) -> object:
    from app.main import app

    resp = unknown_current_client.get("/securities/UNKNOWN/price")
    app.dependency_overrides.clear()
    return resp


@then("the response status is 404")
def status_404_current(response: object) -> None:
    assert response.status_code == 404  # type: ignore[union-attr]
