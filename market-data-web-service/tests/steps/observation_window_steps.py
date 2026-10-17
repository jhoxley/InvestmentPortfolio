from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from app.cache.repository import CacheRepository

scenarios("observation_window.feature")

_AAPL_RECORDS: list[tuple[date, float]] = [
    (date(2024, 3, 1), 150.00),
    (date(2025, 1, 2), 185.50),
    (date(2025, 1, 31), 190.00),
    (date(2025, 5, 1), 192.00),
    (date(2025, 5, 30), 193.00),
    (date(2025, 6, 30), 195.00),
]


@pytest.fixture()
def client_fallback_window() -> httpx.Response:
    """Built per-scenario by the fallback Given steps; replaced in place."""
    return {}


# ── Given steps ────────────────────────────────────────────────────────────────

@given('a cache file exists for ticker "AAPL" covering 2024-03-01 to 2025-06-30')
def seed_aapl(tmp_cache_dir: Path) -> None:
    CacheRepository(tmp_cache_dir).write("AAPL", _AAPL_RECORDS)


@given('the data source returns observations for "AAPL" starting 2023-02-15')
def mock_earlier_segment(mock_inner_provider: MagicMock) -> None:
    mock_inner_provider.get_price_history.return_value = [
        (date(2023, 2, 15), 120.00),
        (date(2023, 12, 29), 140.00),
    ]
    mock_inner_provider.get_current_price.return_value = {
        "currency": "USD",
        "price": 195.00,
        "as_of_date": date(2025, 6, 30),
        "market_state": "CLOSED",
    }


def _build_fallback_client(config_name: str, local_only: bool) -> TestClient:
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

    repo = FallbackConfigRepository(Path(f"tests/fixtures/{config_name}"))

    def override() -> PricingService:
        provider = FallbackPricingProvider(inner=mock_inner, fallback_repo=repo)
        return PricingService(
            provider=provider,
            gap_fill=GapFillService(),
            normaliser=SubUnitNormaliser(),
            fill_resolver=FillStrategyResolver(GapFillService(), ObservedOnlyFiller()),
        )

    app.dependency_overrides[get_pricing_service] = override
    return TestClient(app)


@given('a local-only fallback file for "PRIV01" contains rows from 2022-01-03 to 2024-12-31')
def seed_local_only(client_fallback_window: dict[str, Any]) -> None:
    client_fallback_window["client"] = _build_fallback_client(
        "fallback_config_window_local_only.json", local_only=True
    )


@given(
    'a fallback file for "PRIV01" contains rows from 2022-01-03 to 2024-12-31 '
    "and is not local-only"
)
def seed_triggered(client_fallback_window: dict[str, Any]) -> None:
    client_fallback_window["client"] = _build_fallback_client(
        "fallback_config_window_triggered.json", local_only=False
    )


@given('the primary data source returns no observations for "PRIV01"')
def primary_empty() -> None:
    # Already configured by _build_fallback_client: the inner provider raises DataNotFoundError.
    pass


# ── When steps ─────────────────────────────────────────────────────────────────

@when(
    'a consumer requests observed-only history for "AAPL" from 2025-01-02 to 2025-01-31',
    target_fixture="response",
)
def req_observed_aapl(client_with_cache: TestClient) -> httpx.Response:
    return client_with_cache.get(
        "/securities/AAPL/history",
        params={"from": "2025-01-02", "to": "2025-01-31", "fill": "none"},
    )


@when(
    'a consumer requests default history for "AAPL" from 2025-01-02 to 2025-01-31',
    target_fixture="response",
)
def req_default_aapl_jan(client_with_cache: TestClient) -> httpx.Response:
    return client_with_cache.get(
        "/securities/AAPL/history", params={"from": "2025-01-02", "to": "2025-01-31"}
    )


@when(
    'a consumer requests default history for "AAPL" from 2025-05-01 to 2025-05-30',
    target_fixture="response",
)
def req_default_aapl_may(client_with_cache: TestClient) -> httpx.Response:
    return client_with_cache.get(
        "/securities/AAPL/history", params={"from": "2025-05-01", "to": "2025-05-30"}
    )


@when(
    'a consumer requests default history for "AAPL" from 2023-01-02 to 2023-12-29',
    target_fixture="response",
)
def req_default_aapl_2023(client_with_cache: TestClient) -> httpx.Response:
    return client_with_cache.get(
        "/securities/AAPL/history", params={"from": "2023-01-02", "to": "2023-12-29"}
    )


@when(
    'a consumer requests observed-only history for "PRIV01" from 2022-01-03 to 2024-12-31',
    target_fixture="response",
)
def req_observed_priv01(client_fallback_window: dict[str, Any]) -> httpx.Response:
    client: TestClient = client_fallback_window["client"]
    return client.get(
        "/securities/PRIV01/history",
        params={"from": "2022-01-03", "to": "2024-12-31", "fill": "none"},
    )


@when(
    'a consumer requests default history for "PRIV01" from 2022-01-03 to 2024-12-31',
    target_fixture="response",
)
def req_default_priv01(client_fallback_window: dict[str, Any]) -> httpx.Response:
    client: TestClient = client_fallback_window["client"]
    return client.get(
        "/securities/PRIV01/history", params={"from": "2022-01-03", "to": "2024-12-31"}
    )


# ── Then steps ─────────────────────────────────────────────────────────────────

@then("the response status code is 200")
def status_200(response: httpx.Response) -> None:
    assert response.status_code == 200, response.text


@then("the response reports first observed date 2024-03-01")
def first_observed_2024_03_01(response: httpx.Response) -> None:
    assert response.json()["first_observed_date"] == "2024-03-01"


@then("the response reports last observed date 2025-06-30")
def last_observed_2025_06_30(response: httpx.Response) -> None:
    assert response.json()["last_observed_date"] == "2025-06-30"


@then("the response reports first observed date 2023-02-15")
def first_observed_2023_02_15(response: httpx.Response) -> None:
    assert response.json()["first_observed_date"] == "2023-02-15"


@then("the response reports first observed date 2022-01-03")
def first_observed_2022_01_03(response: httpx.Response) -> None:
    assert response.json()["first_observed_date"] == "2022-01-03"


@then("the response reports last observed date 2024-12-31")
def last_observed_2024_12_31(response: httpx.Response) -> None:
    assert response.json()["last_observed_date"] == "2024-12-31"


@then("the reported first observed date is earlier than the requested start date")
def first_earlier_than_start(response: httpx.Response) -> None:
    first = date.fromisoformat(response.json()["first_observed_date"])
    assert first < date(2025, 5, 1), first


@then("the reported last observed date is later than the requested end date")
def last_later_than_end(response: httpx.Response) -> None:
    last = date.fromisoformat(response.json()["last_observed_date"])
    assert last > date(2025, 5, 30), last


@then("the response contains an entry for every business day from 2025-01-02 to 2025-01-31")
def every_business_day(response: httpx.Response) -> None:
    returned = {e["date"] for e in response.json()["prices"]}
    expected: set[str] = set()
    d = date(2025, 1, 2)
    while d <= date(2025, 1, 31):
        if d.weekday() < 5:
            expected.add(d.isoformat())
        d += timedelta(days=1)
    assert returned == expected, expected ^ returned


@then("the response contains the ticker, currency and prices fields")
def has_core_fields(response: httpx.Response) -> None:
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert isinstance(body["currency"], str) and body["currency"]
    assert isinstance(body["prices"], list) and body["prices"]


@then("each price entry contains only the date, close and fx_rate fields")
def price_entry_shape(response: httpx.Response) -> None:
    for entry in response.json()["prices"]:
        assert set(entry) == {"date", "close", "fx_rate"}, set(entry)


@then("the response contains exactly the two observation window fields in addition")
def additive_fields_only(response: httpx.Response) -> None:
    assert set(response.json()) == {
        "ticker",
        "currency",
        "prices",
        "first_observed_date",
        "last_observed_date",
    }, set(response.json())
