from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("observed_only_fallback.feature")


@pytest.fixture()
def fallback_client() -> dict[str, Any]:
    return {}


@given(
    'a local-only fallback file for "PRIV01" with rows on 2025-01-02, 2025-01-06 and 2025-01-09'
)
def seed_sparse_fallback(fallback_client: dict[str, Any]) -> None:
    from app.api.securities import get_pricing_service
    from app.exceptions import DataNotFoundError
    from app.main import app
    from app.providers import PricingProvider
    from app.providers.fallback_provider import FallbackPricingProvider
    from app.repositories.fallback_config import FallbackConfigRepository
    from app.services.gap_fill import GapFillService
    from app.services.minor_unit import SubUnitNormaliser
    from app.services.pricing_service import PricingService
    from app.services.series_fill import FillStrategyResolver, ObservedOnlyFiller

    mock_inner = MagicMock(spec=PricingProvider)
    mock_inner.get_price_history.side_effect = DataNotFoundError("PRIV01")
    mock_inner.get_current_price.side_effect = DataNotFoundError("PRIV01")

    repo = FallbackConfigRepository(Path("tests/fixtures/fallback_config_sparse.json"))

    def override() -> PricingService:
        provider = FallbackPricingProvider(inner=mock_inner, fallback_repo=repo)
        return PricingService(
            provider=provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
            fill_resolver=FillStrategyResolver(GapFillService(), ObservedOnlyFiller()),
        )

    app.dependency_overrides[get_pricing_service] = override
    fallback_client["client"] = TestClient(app)


@when(
    'a consumer requests observed-only history for "PRIV01" from 2025-01-02 to 2025-01-09',
    target_fixture="response",
)
def req_observed_full(fallback_client: dict[str, Any]) -> httpx.Response:
    client: TestClient = fallback_client["client"]
    return client.get(
        "/securities/PRIV01/history",
        params={"from": "2025-01-02", "to": "2025-01-09", "fill": "none"},
    )


@when(
    'a consumer requests observed-only history for "PRIV01" from 2025-01-05 to 2025-01-07',
    target_fixture="response",
)
def req_observed_narrow(fallback_client: dict[str, Any]) -> httpx.Response:
    client: TestClient = fallback_client["client"]
    return client.get(
        "/securities/PRIV01/history",
        params={"from": "2025-01-05", "to": "2025-01-07", "fill": "none"},
    )


@when(
    'a consumer requests default history for "PRIV01" from 2025-01-02 to 2025-01-09',
    target_fixture="response",
)
def req_default_full(fallback_client: dict[str, Any]) -> httpx.Response:
    client: TestClient = fallback_client["client"]
    return client.get(
        "/securities/PRIV01/history", params={"from": "2025-01-02", "to": "2025-01-09"}
    )


@then("the response status code is 200")
def status_200(response: httpx.Response) -> None:
    assert response.status_code == 200, response.text


@then("the response contains exactly 3 price entries")
def exactly_three(response: httpx.Response) -> None:
    assert len(response.json()["prices"]) == 3, response.json()["prices"]


@then("the response contains exactly 1 price entry")
def exactly_one(response: httpx.Response) -> None:
    assert len(response.json()["prices"]) == 1, response.json()["prices"]


@then("the returned dates are 2025-01-02, 2025-01-06 and 2025-01-09")
def dates_are_three(response: httpx.Response) -> None:
    assert [e["date"] for e in response.json()["prices"]] == [
        "2025-01-02",
        "2025-01-06",
        "2025-01-09",
    ]


@then("the returned date is 2025-01-06")
def date_is_jan06(response: httpx.Response) -> None:
    assert [e["date"] for e in response.json()["prices"]] == ["2025-01-06"]


@then("the response contains an entry for every business day from 2025-01-02 to 2025-01-09")
def every_business_day(response: httpx.Response) -> None:
    returned = {e["date"] for e in response.json()["prices"]}
    expected: set[str] = set()
    d = date(2025, 1, 2)
    while d <= date(2025, 1, 9):
        if d.weekday() < 5:
            expected.add(d.isoformat())
        d += timedelta(days=1)
    assert returned == expected, expected ^ returned
