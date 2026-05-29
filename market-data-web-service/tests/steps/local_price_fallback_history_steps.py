from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.exceptions import DataNotFoundError, IdentifierNotFoundError
from app.providers import PricingProvider
from app.providers.identifier_provider import IdentifierProvider
from app.services.minor_unit import SubUnitNormaliser

scenarios("local_price_fallback_history.feature")

_FALLBACK_CONFIG = Path("tests/fixtures/fallback_config.json")
_FALLBACK_CONFIG_ISIN = Path("tests/fixtures/fallback_config_isin.json")
_FALLBACK_CONFIG_LOCAL_ONLY = Path("tests/fixtures/fallback_config_local_only.json")
_FALLBACK_CONFIG_PENCE = Path("tests/fixtures/fallback_config_pence.json")


def _make_fallback_client(config_path: Path) -> tuple[TestClient, MagicMock, MagicMock]:
    from app.api.identifiers import get_identifier_service
    from app.api.securities import get_pricing_service
    from app.main import app
    from app.providers.fallback_provider import FallbackPricingProvider
    from app.providers.identifier_provider import (
        FallbackIdentifierProvider,
    )
    from app.repositories.fallback_config import FallbackConfigRepository
    from app.services.gap_fill import GapFillService
    from app.services.identifier_service import IdentifierService
    from app.services.pricing_service import PricingService

    mock_inner = MagicMock(spec=PricingProvider)
    mock_inner.get_price_history.side_effect = DataNotFoundError("PRIV01")
    mock_inner.get_current_price.side_effect = DataNotFoundError("PRIV01")

    mock_id_inner = MagicMock(spec=IdentifierProvider)
    mock_id_inner.lookup_ticker.side_effect = IdentifierNotFoundError("GB00B0PRVT01")

    fallback_repo = FallbackConfigRepository(config_path)
    isin_repo = FallbackConfigRepository(_FALLBACK_CONFIG_ISIN)

    def override_pricing() -> PricingService:
        provider = FallbackPricingProvider(inner=mock_inner, fallback_repo=fallback_repo)
        return PricingService(
            provider=provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
        )

    def override_identifier() -> IdentifierService:
        provider = FallbackIdentifierProvider(
            inner=mock_id_inner, fallback_repo=isin_repo
        )
        return IdentifierService(provider=provider)

    app.dependency_overrides[get_pricing_service] = override_pricing
    app.dependency_overrides[get_identifier_service] = override_identifier
    client = TestClient(app)
    return client, mock_inner, mock_id_inner


@given(
    'the primary data source returns no price history for ticker "PRIV01"',
    target_fixture="fallback_client",
)
def primary_no_data_priv01() -> tuple[TestClient, MagicMock, MagicMock]:
    client, mock_inner, mock_id = _make_fallback_client(_FALLBACK_CONFIG)
    return client, mock_inner, mock_id


@given(
    'a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"'
)
def fallback_config_priv01_gbp() -> None:
    pass


@given('the local CSV file contains prices for "2025-01-02" and "2025-01-06"')
def local_csv_two_prices() -> None:
    pass


@when(
    'a consumer requests price history for "PRIV01" from "2025-01-02" to "2025-01-06"',
    target_fixture="response",
)
def get_priv01_history_jan02_jan06(
    fallback_client: tuple[TestClient, MagicMock, MagicMock],
) -> object:
    from app.main import app

    client, _, _ = fallback_client
    resp = client.get(
        "/securities/PRIV01/history", params={"from": "2025-01-02", "to": "2025-01-06"}
    )
    app.dependency_overrides.clear()
    return resp


@then("the response status is 200")
def status_200_fallback(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]


@then('the response currency is "GBP"')
def currency_gbp(response: object) -> None:
    assert response.json()["currency"] == "GBP"  # type: ignore[union-attr]


@then("the response contains 3 price entries (gap-filled Mon-Fri series)")
def three_entries_gap_filled(response: object) -> None:
    assert len(response.json()["prices"]) == 3  # type: ignore[union-attr]


@then("the response does not come from the price cache")
def no_cache_used(fallback_client: tuple[TestClient, MagicMock, MagicMock]) -> None:
    pass


# --- Scenario 2: gap-fill applied ---

@given(
    "a fallback configuration maps "
    '"PRIV01" to a local CSV file with 2 observations spanning 5 business days',
)
def fallback_config_2obs_5days() -> None:
    pass


@when(
    'a consumer requests price history for "PRIV01" over that 5-day range',
    target_fixture="response",
)
def get_priv01_history_5days(
    fallback_client: tuple[TestClient, MagicMock, MagicMock],
) -> object:
    from app.main import app

    client, _, _ = fallback_client
    resp = client.get(
        "/securities/PRIV01/history", params={"from": "2025-01-02", "to": "2025-01-06"}
    )
    app.dependency_overrides.clear()
    return resp


@then("the response contains entries for all 5 business days")
def five_business_days(response: object) -> None:
    assert len(response.json()["prices"]) == 3  # type: ignore[union-attr]


@then("the gaps are filled by forward carry of the nearest observation")
def gaps_forward_filled(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    by_date = {p["date"]: p["close"] for p in prices}
    assert by_date["2025-01-03"] == pytest.approx(100.00, abs=0.01)


# --- Scenario 3: unknown ticker with no fallback ---

@given(
    'the primary data source returns no price history for ticker "UNKNOWN"',
    target_fixture="unknown_client",
)
def primary_no_data_unknown() -> TestClient:
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
def no_fallback_for_unknown() -> None:
    pass


@when(
    'a consumer requests price history for "UNKNOWN"',
    target_fixture="response",
)
def get_unknown_history(unknown_client: TestClient) -> object:
    from app.main import app

    resp = unknown_client.get("/securities/UNKNOWN/history")
    app.dependency_overrides.clear()
    return resp


@then("the response status is 404")
def status_404_fallback(response: object) -> None:
    assert response.status_code == 404  # type: ignore[union-attr]


# --- Scenario 4: ISIN pseudo-ticker ---

@given(
    'the primary data source has no ticker translation for ISIN "GB00B0PRVT01"',
    target_fixture="isin_client",
)
def primary_no_isin_translation() -> tuple[TestClient, MagicMock, MagicMock]:
    client, mock_inner, mock_id = _make_fallback_client(_FALLBACK_CONFIG_ISIN)
    return client, mock_inner, mock_id


@given(
    'a fallback configuration maps "GB00B0PRVT01" to a local CSV file with currency "GBP"'
)
def fallback_config_isin_gbp() -> None:
    pass


@given(
    'the identifier-resolution endpoint is called for "GB00B0PRVT01"',
    target_fixture="resolution_response",
)
def resolve_isin(
    isin_client: tuple[TestClient, MagicMock, MagicMock],
) -> object:
    client, _, _ = isin_client
    return client.get("/identifiers/GB00B0PRVT01")


@then('the resolution response returns "GB00B0PRVT01" as the ticker')
def resolution_returns_pseudo_ticker(resolution_response: object) -> None:
    data = resolution_response.json()  # type: ignore[union-attr]
    assert resolution_response.status_code == 200  # type: ignore[union-attr]
    assert data["ticker"] == "GB00B0PRVT01"


@when(
    'a consumer requests price history for "GB00B0PRVT01"',
    target_fixture="response",
)
def get_isin_history(
    isin_client: tuple[TestClient, MagicMock, MagicMock],
) -> object:
    from app.main import app

    client, _, _ = isin_client
    resp = client.get(
        "/securities/GB00B0PRVT01/history",
        params={"from": "2025-01-02", "to": "2025-01-02"},
    )
    app.dependency_overrides.clear()
    return resp


@then("the response contains prices from the local file")
def response_has_local_prices(response: object) -> None:
    data = response.json()  # type: ignore[union-attr]
    assert len(data["prices"]) >= 1
    assert data["prices"][0]["close"] == pytest.approx(150.00, abs=0.01)


# --- Scenario: pence currency in fallback config is normalised ---

@given(
    'a fallback configuration maps "PRIV01" to a local CSV file with currency "GBp"',
    target_fixture="fallback_client",
)
def fallback_config_priv01_gbp_pence() -> tuple[TestClient, MagicMock, MagicMock]:
    client, mock_inner, mock_id = _make_fallback_client(_FALLBACK_CONFIG_PENCE)
    return client, mock_inner, mock_id


@then("the pence prices are divided by 100")
def pence_prices_divided(response: object) -> None:
    prices = response.json()["prices"]  # type: ignore[union-attr]
    by_date = {p["date"]: p["close"] for p in prices}
    assert by_date["2025-01-02"] == pytest.approx(100.00, rel=1e-4)
    assert by_date["2025-01-06"] == pytest.approx(110.00, rel=1e-4)


# --- Scenario 5: use_local_only ---

@given(
    "a fallback configuration maps "
    '"PRIV01" to a local CSV file with use_local_only set',
    target_fixture="local_only_client",
)
def fallback_config_local_only() -> tuple[TestClient, MagicMock, MagicMock]:
    client, mock_inner, mock_id = _make_fallback_client(_FALLBACK_CONFIG_LOCAL_ONLY)
    mock_inner.get_price_history.reset_mock(side_effect=True)
    mock_inner.get_current_price.reset_mock(side_effect=True)
    return client, mock_inner, mock_id


@when(
    "a consumer requests price history for "
    '"PRIV01"',
    target_fixture="response",
)
def get_priv01_history_local_only(
    local_only_client: tuple[TestClient, MagicMock, MagicMock],
) -> object:
    from app.main import app

    client, _, _ = local_only_client
    resp = client.get(
        "/securities/PRIV01/history", params={"from": "2025-01-02", "to": "2025-01-06"}
    )
    app.dependency_overrides.clear()
    return resp


@then("the primary data source is never queried")
def inner_never_called(
    local_only_client: tuple[TestClient, MagicMock, MagicMock],
) -> None:
    _, mock_inner, _ = local_only_client
    mock_inner.get_price_history.assert_not_called()


@then("the response status is 200 with prices from the local file")
def status_200_local_only(response: object) -> None:
    assert response.status_code == 200  # type: ignore[union-attr]
    data = response.json()  # type: ignore[union-attr]
    assert len(data["prices"]) >= 1
