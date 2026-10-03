"""BDD step implementations for var_calculation_runs.feature (User Story 1).

These scenarios assert against the VaR store (VarRepository) directly rather than
through an HTTP read endpoint: feature 012 computes and persists VaR/ES, but the public
read API over that store is a separate feature (013). This mirrors the spec's own
"Independent Test" framing ("compare the stored VaR and ES ... against values calculated
by hand") and the precedent in return_histogram_steps.py, which seeds controlled ladder
data directly through LadderRepository rather than only through the HTTP surface.
"""

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

scenarios("var_calculation_runs.feature")


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
def run_context() -> dict[str, Any]:
    """Mutable scratch space shared between When/Then steps for one scenario."""
    return {}


def _write_var_ladder(repo: LadderRepository, account: str, rows: list[dict[str, Any]]) -> None:
    """Write a stored position ladder with real quantity/market_value (VaR-ready).

    Unlike tests/risk_helpers.py's write_ladder (built for the return-histogram and
    performance features, which only need weighted_position_return), this sets
    quantity/market_value so build_exposures() has real holdings to work with.

    Args:
        repo: LadderRepository to write through.
        account: Target account name.
        rows: Dicts with keys date, sub_account, quantity, market_value.
    """
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
        checksum="var-bdd-test",
        row_count=len(df),
        from_date=df["date"].min(),
        to_date=df["date"].max(),
        sub_accounts=sorted(df["sub_account"].unique().tolist()),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


def _set_lookbacks(lookbacks: dict[str, int]) -> None:
    """Replace the app's VaR look-back configuration for the rest of this test.

    Args:
        lookbacks: Look-back code to business-day window length.
    """
    current = app.dependency_overrides[get_settings]()
    new_var = current.var.model_copy(update={"lookbacks": lookbacks})
    new_settings = current.model_copy(update={"var": new_var})
    app.dependency_overrides[get_settings] = lambda: new_settings


def _configure_series(
    fake_market_data_service: FakeMarketDataService, ticker: str, start: date, prices: list[float]
) -> None:
    """Configure a fake observed price series starting at a given business day.

    Args:
        fake_market_data_service: The shared FakeMarketDataService fixture.
        ticker: Identifier to configure.
        start: First business day of the series.
        prices: Close prices, one per consecutive business day from start.
    """
    days = pd.bdate_range(start=start, periods=len(prices))
    points = [PriceHistoryPoint(date=d.date(), close=p) for d, p in zip(days, prices, strict=True)]
    fake_market_data_service.configure_observed_prices(ticker, points)


@given(
    parsers.parse(
        'account "{account}" holds "{sub_a}" and "{sub_b}" with daily GBP prices '
        "from {start} to {end}"
    )
)
def holds_two_with_daily_prices(
    account: str,
    sub_a: str,
    sub_b: str,
    start: str,
    end: str,
    ladder_repo: LadderRepository,
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
) -> None:
    """Seed a ladder where two sub-accounts hold a flat 1000 GBP each, every business day."""
    days = pd.bdate_range(start=start, end=end)
    rows = [
        {"date": d.date(), "sub_account": sub, "quantity": 10.0, "market_value": 1000.0}
        for d in days
        for sub in (sub_a, sub_b)
    ]
    _write_var_ladder(ladder_repo, account, rows)
    fake_identifier_mapping_repository.set_entry(sub_a, ticker=sub_a)
    fake_identifier_mapping_repository.set_entry(sub_b, ticker=sub_b)


@given(
    parsers.parse('account "{account}" holds "{sub_a}" with daily GBP prices from {start} to {end}')
)
def holds_one_with_daily_prices(
    account: str,
    sub_a: str,
    start: str,
    end: str,
    ladder_repo: LadderRepository,
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
) -> None:
    """Seed a ladder where one sub-account holds a flat 1000 GBP, every business day."""
    days = pd.bdate_range(start=start, end=end)
    rows = [
        {"date": d.date(), "sub_account": sub_a, "quantity": 10.0, "market_value": 1000.0}
        for d in days
    ]
    _write_var_ladder(ladder_repo, account, rows)
    fake_identifier_mapping_repository.set_entry(sub_a, ticker=sub_a)


@given(parsers.parse("the VaR look-backs are configured as {spec}"))
def configure_lookbacks(spec: str) -> None:
    """Parse 'code:days, code:days' into the VaR settings' look-backs mapping."""
    lookbacks = {}
    for part in spec.split(","):
        code, days = part.strip().split(":")
        lookbacks[code.strip()] = int(days)
    _set_lookbacks(lookbacks)


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


@given(
    parsers.parse(
        'account "{account}" holds "{sub_a}" worth {value_a:d} and "{sub_b}" worth {value_b:d} '
        "on {as_of}"
    )
)
def holds_two_no_cash_on_date(
    account: str,
    sub_a: str,
    value_a: int,
    sub_b: str,
    value_b: int,
    as_of: str,
    ladder_repo: LadderRepository,
    fake_identifier_mapping_repository: FakeIdentifierMappingRepository,
) -> None:
    """Seed a single-date ladder with two risky positions and no Cash."""
    d = date.fromisoformat(as_of)
    rows = [
        {"date": d, "sub_account": sub_a, "quantity": 1.0, "market_value": float(value_a)},
        {"date": d, "sub_account": sub_b, "quantity": 1.0, "market_value": float(value_b)},
    ]
    _write_var_ladder(ladder_repo, account, rows)
    fake_identifier_mapping_repository.set_entry(sub_a, ticker=sub_a)
    fake_identifier_mapping_repository.set_entry(sub_b, ticker=sub_b)


def _parse_pair_list(text: str) -> list[tuple[float, float]]:
    """Parse '"-1.2%,0.4%", "0.5%,-2.0%"' into [(-0.012, 0.004), (0.005, -0.02)]."""
    pairs = []
    for chunk in text.split('", "'):
        cleaned = chunk.strip().strip('"')
        a_str, b_str = cleaned.split(",")
        pairs.append(
            (float(a_str.strip().rstrip("%")) / 100.0, float(b_str.strip().rstrip("%")) / 100.0)
        )
    return pairs


@given(
    parsers.parse(
        'the observed returns of "{sub_a}" and "{sub_b}" on the 5 business days ending '
        "{as_of} are {pairs}"
    )
)
def configure_five_day_returns(
    sub_a: str,
    sub_b: str,
    as_of: str,
    pairs: str,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """Build a 6-point price series per instrument reproducing the given 5 daily returns."""
    return_pairs = _parse_pair_list(pairs)
    assert len(return_pairs) == 5
    scenario_days = pd.bdate_range(end=as_of, periods=5)
    seed_day = pd.bdate_range(end=scenario_days[0], periods=2)[0]

    for col, ticker in enumerate((sub_a, sub_b)):
        prices = [100.0]
        for row in return_pairs:
            prices.append(prices[-1] * (1.0 + row[col]))
        all_days = pd.DatetimeIndex([seed_day, *scenario_days])
        points = [
            PriceHistoryPoint(date=d.date(), close=p) for d, p in zip(all_days, prices, strict=True)
        ]
        fake_market_data_service.configure_observed_prices(ticker, points)


@given(parsers.parse('"{sub_a}" has no observed price on {missing_date} within the 5-day window'))
def configure_missing_day(
    sub_a: str,
    missing_date: str,
    fake_market_data_service: FakeMarketDataService,
) -> None:
    """Configure sub_a with daily prices over a wide window except for one missing date."""
    missing = date.fromisoformat(missing_date)
    window_start = pd.bdate_range(end=missing, periods=10)[0]
    window_end = pd.bdate_range(start=missing, periods=10)[-1]
    days = pd.bdate_range(start=window_start, end=window_end)
    points = [
        PriceHistoryPoint(date=d.date(), close=100.0 + i)
        for i, d in enumerate(days)
        if d.date() != missing
    ]
    fake_market_data_service.configure_observed_prices(sub_a, points)
    # The second instrument in the scenario (Equity B) keeps the fake's default flat
    # 100.0 price for every business day, so it is always observed.


@when(parsers.parse('a full VaR run is requested for "{account}" and completes'))
def request_full_run(account: str, app_client: TestClient, run_context: dict[str, Any]) -> None:
    """POST a full run and (the test scheduler being inline) read back its final status."""
    response = app_client.post(f"/v1/accounts/{account}/risk/var/runs", json={"mode": "full"})
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    final = app_client.get(f"/v1/accounts/{account}/risk/var/runs/{run_id}")
    run_context["account"] = account
    run_context["run"] = final.json()


@when(
    parsers.parse('a full VaR run is requested for "{account}" from {start} to {end} and completes')
)
def request_full_run_ranged(
    account: str, start: str, end: str, app_client: TestClient, run_context: dict[str, Any]
) -> None:
    """POST a full run restricted to [start, end] and read back its final status."""
    response = app_client.post(
        f"/v1/accounts/{account}/risk/var/runs",
        json={"mode": "full", "start": start, "end": end},
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    final = app_client.get(f"/v1/accounts/{account}/risk/var/runs/{run_id}")
    run_context["account"] = account
    run_context["run"] = final.json()


@then(parsers.parse('the run status is "{status}"'))
def check_run_status(status: str, run_context: dict[str, Any]) -> None:
    """Assert the final run status, printing its failure detail if present for debugging."""
    run = run_context["run"]
    assert run["status"] == status, run.get("failure")


@then(
    parsers.parse(
        'every business date in the ladder has an estimate for look-back "{code_a}" and "{code_b}"'
    )
)
def check_every_date_has_both_lookbacks(
    code_a: str, code_b: str, run_context: dict[str, Any], var_repo: VarRepository
) -> None:
    """Assert every ladder business date has exactly one estimate per look-back code."""
    df = var_repo.read_estimates(run_context["account"])
    dates = sorted(df["date"].unique())
    for code in (code_a, code_b):
        codes_present = set(df.loc[df["date"].isin(dates), "lookback_code"]) if len(df) else set()
        assert code in codes_present, f"missing look-back '{code}'"
        assert len(df[df["lookback_code"] == code]) == len(dates)


@then("every estimate's 99% VaR is at least its 97.5% VaR, which is at least its 95% VaR")
def check_var_ordering(run_context: dict[str, Any], var_repo: VarRepository) -> None:
    """Assert VaR is monotonically non-decreasing in confidence for every stored row."""
    df = var_repo.read_estimates(run_context["account"])
    assert len(df) > 0
    assert (df["var_9900_gbp"] >= df["var_9750_gbp"] - 1e-9).all()
    assert (df["var_9750_gbp"] >= df["var_9500_gbp"] - 1e-9).all()


@then("every estimate's Expected Shortfall is at least its VaR at the same confidence level")
def check_es_at_least_var(run_context: dict[str, Any], var_repo: VarRepository) -> None:
    """Assert ES >= VaR at each of the three confidence levels, for every stored row."""
    df = var_repo.read_estimates(run_context["account"])
    for p in (9500, 9750, 9900):
        assert (df[f"es_{p}_gbp"] >= df[f"var_{p}_gbp"] - 1e-9).all()


@then(parsers.parse('the stored 95% VaR for {as_of} at look-back "{code}" is {expected:d} GBP'))
def check_stored_var_95(
    as_of: str, code: str, expected: int, run_context: dict[str, Any], var_repo: VarRepository
) -> None:
    """Assert the stored 95% VaR for one date/look-back matches a hand-computed value."""
    df = var_repo.read_estimates(run_context["account"])
    row = df[(df["date"] == pd.Timestamp(as_of)) & (df["lookback_code"] == code)]
    assert len(row) == 1, df.to_string()
    assert row.iloc[0]["var_9500_gbp"] == pytest.approx(float(expected), abs=1e-6)


@then(parsers.parse('the stored scenario count for {as_of} at look-back "{code}" is {expected:d}'))
def check_scenario_count(
    as_of: str, code: str, expected: int, run_context: dict[str, Any], var_repo: VarRepository
) -> None:
    """Assert the stored scenario_count for one date/look-back matches an expected value."""
    df = var_repo.read_estimates(run_context["account"])
    row = df[(df["date"] == pd.Timestamp(as_of)) & (df["lookback_code"] == code)]
    assert len(row) == 1, df.to_string()
    assert int(row.iloc[0]["scenario_count"]) == expected


@then(parsers.parse('only dates from {start} to {end} have an estimate for look-back "{code}"'))
def check_only_range_has_estimates(
    start: str, end: str, code: str, run_context: dict[str, Any], var_repo: VarRepository
) -> None:
    """Assert the stored dates for a look-back are exactly the requested range."""
    df = var_repo.read_estimates(run_context["account"])
    stored_dates = set(df.loc[df["lookback_code"] == code, "date"])
    expected_dates = {pd.Timestamp(d.date()) for d in pd.bdate_range(start=start, end=end)}
    assert stored_dates == expected_dates
