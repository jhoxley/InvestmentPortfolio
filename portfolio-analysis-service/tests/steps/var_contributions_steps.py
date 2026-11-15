"""BDD step implementations for var_contributions.feature (015-var-contributions)."""

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.config import get_settings
from app.main import app
from app.models.market_data import PriceHistoryPoint
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.repositories.var_repository import VarRepository
from tests.conftest import FakeIdentifierMappingRepository, FakeMarketDataService

scenarios("var_contributions.feature")


@pytest.fixture()
def ladder_repo(app_client: TestClient) -> LadderRepository:
    """Return a LadderRepository over the same data directory the app under test uses."""
    settings = app.dependency_overrides[get_settings]()
    return LadderRepository(data_dir=settings.data.directory)


@pytest.fixture()
def var_repo(app_client: TestClient) -> VarRepository:
    """Return a VarRepository over the same data directory the app under test uses."""
    settings = app.dependency_overrides[get_settings]()
    return VarRepository(data_dir=settings.data.directory)


@pytest.fixture()
def context() -> dict[str, Any]:
    """Mutable scratch space shared between Given/When/Then steps for one scenario."""
    return {}


def _write_var_ladder(repo: LadderRepository, account: str, rows: list[dict[str, Any]]) -> None:
    """Write a stored position ladder with real quantity/market_value (VaR-ready)."""
    df = pd.DataFrame(
        [
            {
                "date": r["date"],
                "sub_account": r["sub_account"],
                "book_cost": 0.0,
                "quantity": r["quantity"],
                "total_income": 0.0,
                "price": r["market_value"] / r["quantity"] if r["quantity"] else 0.0,
                "market_value": r["market_value"],
                "portfolio_weight": 0.0,
                "position_return": 0.0,
                "weighted_position_return": 0.0,
            }
            for r in rows
        ]
    )
    meta = AccountMeta(
        account_name=account,
        checksum="contrib-bdd-test",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=df["date"].max(),
        sub_accounts=sorted(df["sub_account"].unique().tolist()),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


@given(
    parsers.parse(
        'account "{account}" holds "{sub_a}" worth {value_a:d} and "{sub_b}" worth {value_b:d} '
        "and Cash worth {cash:d} on {as_of}"
    )
)
def holds_two_and_cash_on_date(
    account: str,
    sub_a: str,
    value_a: int,
    sub_b: str,
    value_b: int,
    cash: int,
    as_of: str,
    ladder_repo: LadderRepository,
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
) -> None:
    """Seed a single-date ladder with two risky positions and Cash."""
    d = date.fromisoformat(as_of)
    rows = [
        {"date": d, "sub_account": sub_a, "quantity": 1.0, "market_value": float(value_a)},
        {"date": d, "sub_account": sub_b, "quantity": 1.0, "market_value": float(value_b)},
        {"date": d, "sub_account": "Cash", "quantity": float(cash), "market_value": float(cash)},
    ]
    _write_var_ladder(ladder_repo, account, rows)
    fake_identifier_mapping_repository.set_entry(sub_a, ticker=sub_a)
    fake_identifier_mapping_repository.set_entry(sub_b, ticker=sub_b)


@given(parsers.parse('account "{account}" holds "{sub_a}" worth {value_a:d} on {as_of}'))
def holds_one_on_date(
    account: str,
    sub_a: str,
    value_a: int,
    as_of: str,
    ladder_repo: LadderRepository,
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
) -> None:
    """Seed a single-date ladder with one risky position and no Cash."""
    d = date.fromisoformat(as_of)
    rows = [{"date": d, "sub_account": sub_a, "quantity": 1.0, "market_value": float(value_a)}]
    _write_var_ladder(ladder_repo, account, rows)
    fake_identifier_mapping_repository.set_entry(sub_a, ticker=sub_a)


@given(parsers.parse('"{sub_a}" and "{sub_b}" share theme "{theme}"'))
def share_theme(
    sub_a: str,
    sub_b: str,
    theme: str,
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
) -> None:
    """Re-configure two sub-accounts' mapping entries with a shared theme."""
    fake_identifier_mapping_repository.set_entry(sub_a, ticker=sub_a, theme=theme)
    fake_identifier_mapping_repository.set_entry(sub_b, ticker=sub_b, theme=theme)


@given(parsers.parse("the contributions VaR look-backs are configured as {spec}"))
def configure_lookbacks(spec: str) -> None:
    """Parse 'code:days, code:days' into the VaR settings' look-backs mapping."""
    lookbacks: dict[str, int] = {}
    for part in spec.split(","):
        code, days = part.strip().split(":")
        lookbacks[code.strip()] = int(days)
    current = app.dependency_overrides[get_settings]()
    new_var = current.var.model_copy(
        update={"lookbacks": lookbacks, "headline_lookback": next(iter(lookbacks))}
    )
    new_settings = current.model_copy(update={"var": new_var})
    app.dependency_overrides[get_settings] = lambda: new_settings


@given(
    parsers.parse(
        '"{sub_a}" has distinct daily GBP prices covering the {n:d}-day window ending {as_of} '
        "starting at {base:d}"
    )
)
def configure_distinct_prices(
    sub_a: str,
    n: int,
    as_of: str,
    base: int,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """Configure a short, strictly-increasing-then-decreasing price series for one identifier."""
    scenario_days = pd.bdate_range(end=as_of, periods=n)
    seed_day = pd.bdate_range(end=scenario_days[0], periods=2)[0]
    all_days = pd.DatetimeIndex([seed_day, *scenario_days])
    prices = [float(base) + (i if i % 2 == 0 else -i) for i in range(len(all_days))]
    points = [
        PriceHistoryPoint(date=d.date(), close=p) for d, p in zip(all_days, prices, strict=True)
    ]
    fake_market_data_service.configure_observed_prices(sub_a, points)


@given(parsers.parse('a full VaR run is requested for "{account}" and completes'))
@when(parsers.parse('a full VaR run is requested for "{account}" and completes'))
def request_full_run(account: str, app_client: TestClient, context: dict[str, Any]) -> None:
    """POST a full run and (the test scheduler being inline) read back its final status."""
    response = app_client.post(f"/v1/accounts/{account}/risk/var/runs", json={"mode": "full"})
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    final = app_client.get(f"/v1/accounts/{account}/risk/var/runs/{run_id}")
    assert final.json()["status"] == "succeeded", final.json()
    context["account"] = account


@when(
    parsers.parse(
        'the contributions for "{account}" on {as_of} at look-back "{code}" grouped by '
        '"{group_by}" are requested'
    )
)
def request_contributions(
    account: str,
    as_of: str,
    code: str,
    group_by: str,
    app_client: TestClient,
    context: dict[str, Any],
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """GET the contributions endpoint, recording the market-data call count beforehand."""
    context["market_data_calls_before"] = len(fake_market_data_service.requests)
    context["account"] = account
    context["response"] = app_client.get(
        f"/v1/accounts/{account}/risk/var/contributions"
        f"?date={as_of}&lookback={code}&confidence=95&group_by={group_by}"
    )


@then(parsers.parse("the response status is {status:d}"))
def check_response_status(status: int, context: dict[str, Any]) -> None:
    """Assert the raw HTTP response status code."""
    response = context["response"]
    assert response.status_code == status, response.text


@then(parsers.parse('the problem type is "{type_slug}" naming "{field}"'))
def check_problem_type(type_slug: str, field: str, context: dict[str, Any]) -> None:
    """Assert the 422 problem body's type and that its detail names the offending field."""
    body = context["response"].json()
    assert body["type"].endswith(type_slug), body
    assert field in body["detail"], body


@then(
    parsers.parse(
        'the contributions response has one group for each of "{key_a}", "{key_b}", "{key_c}"'
    )
)
def check_three_groups(key_a: str, key_b: str, key_c: str, context: dict[str, Any]) -> None:
    """Assert the response's groups have exactly these three keys."""
    body = context["response"].json()
    keys = {g["key"] for g in body["groups"]}
    assert keys == {key_a, key_b, key_c}, body["groups"]


@then(parsers.parse('the contributions response has one group for each of "{key_a}", "{key_b}"'))
def check_two_groups(key_a: str, key_b: str, context: dict[str, Any]) -> None:
    """Assert the response's groups have exactly these two keys."""
    body = context["response"].json()
    keys = {g["key"] for g in body["groups"]}
    assert keys == {key_a, key_b}, body["groups"]


@then("the sum of component ES across the contributions groups equals the stored total ES")
def check_component_es_sum(context: dict[str, Any], var_repo: VarRepository) -> None:
    """Assert the summed component_es_gbp matches the stored es_9500_gbp within 0.5%."""
    body = context["response"].json()
    total_component_es = sum(g["component_es_gbp"] for g in body["groups"])

    estimates = var_repo.read_estimates(context["account"])
    row = estimates[
        (estimates["date"] == pd.Timestamp(body["date"]))
        & (estimates["lookback_code"] == body["lookback_code"])
    ]
    assert len(row) == 1, estimates.to_string()
    stored_es = float(row.iloc[0]["es_9500_gbp"])

    assert total_component_es == pytest.approx(stored_es, rel=0.005)


@then("requesting the contributions made no new market-data calls")
def check_no_new_market_data_calls(
    context: dict[str, Any], fake_market_data_service: FakeMarketDataService
) -> None:
    """Assert the contributions request itself triggered zero new market-data calls."""
    assert len(fake_market_data_service.requests) == context["market_data_calls_before"]


@then("the contributions response is not computed")
def check_not_computed(context: dict[str, Any]) -> None:
    """Assert the empty 'not computed' shape: no date, no groups, status/runs links."""
    body = context["response"].json()
    assert body["date"] is None
    assert body["groups"] == []
    assert "status" in body["_links"]
    assert "runs" in body["_links"]


@then(parsers.parse('the contributions response has quality "{quality}"'))
def check_quality(quality: str, context: dict[str, Any]) -> None:
    """Assert the response's top-level quality field."""
    body = context["response"].json()
    assert body["quality"] == quality, body


@then("the contributions response groups are empty")
def check_groups_empty(context: dict[str, Any]) -> None:
    """Assert the response's groups list is empty."""
    assert context["response"].json()["groups"] == []


@then("the contributions response has a total value")
def check_has_total_value(context: dict[str, Any]) -> None:
    """Assert total_value_gbp is populated (not null) even for an insufficient-quality date."""
    assert context["response"].json()["total_value_gbp"] is not None
