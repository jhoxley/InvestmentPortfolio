from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.exceptions import DataNotFoundError
from app.providers import PricingProvider
from app.services.minor_unit import SubUnitNormaliser

scenarios("local_price_fallback_edge.feature")

_FALLBACK_CONFIG_MISSING = Path("tests/fixtures/fallback_config_missing_file.json")
_FALLBACK_CONFIG_EMPTY = Path("tests/fixtures/fallback_config_empty.json")


def _make_edge_client(config_path: Path) -> TestClient:
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
    return TestClient(app)


@given(
    'a fallback configuration maps "PRIV01" to a non-existent CSV file',
    target_fixture="edge_client",
)
def fallback_missing_file() -> TestClient:
    return _make_edge_client(_FALLBACK_CONFIG_MISSING)


@given(
    'a fallback configuration maps "PRIV01" to an empty CSV file',
    target_fixture="edge_client",
)
def fallback_empty_file() -> TestClient:
    return _make_edge_client(_FALLBACK_CONFIG_EMPTY)


@when(
    'a consumer requests price history for "PRIV01"',
    target_fixture="response",
)
def get_priv01_edge(edge_client: TestClient) -> object:
    from app.main import app

    resp = edge_client.get(
        "/securities/PRIV01/history", params={"from": "2025-01-02", "to": "2025-01-06"}
    )
    app.dependency_overrides.clear()
    return resp


@then("the response status is 503")
def status_503_edge(response: object) -> None:
    assert response.status_code == 503  # type: ignore[union-attr]


@then("the response contains a descriptive error message")
def descriptive_error(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert "detail" in data
    assert len(data["detail"]) > 10


@then("the response status is 404")
def status_404_edge(response: object) -> None:
    assert response.status_code == 404  # type: ignore[union-attr]
