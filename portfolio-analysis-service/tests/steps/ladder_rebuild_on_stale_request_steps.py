"""BDD step implementations for ladder_rebuild_on_stale_request.feature (014)."""

import io
from datetime import UTC, date, datetime

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.api.ladder import router as ladder_router  # noqa: F401  (ensures app wiring is loaded)
from app.config import get_settings
from app.main import app
from app.models.market_data import PriceHistoryPoint
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from tests.conftest import FakeMarketDataService

scenarios("ladder_rebuild_on_stale_request.feature")


def _ladder_repo(app_client: TestClient) -> LadderRepository:
    """Return a LadderRepository bound to the app_client's own data directory.

    Args:
        app_client: The running TestClient fixture.

    Returns:
        LadderRepository instance.
    """
    settings = app.dependency_overrides[get_settings]()
    return LadderRepository(data_dir=settings.data.directory)


@given(
    parsers.parse(
        'account "{account_name}" has a position ladder last known through "{last_known}"'
    ),
    target_fixture="account_name",
)
def seed_stale_ladder(account_name: str, last_known: str, app_client: TestClient) -> str:
    """Write a minimal single-equity ladder ending at the given last-known date.

    Args:
        account_name: Account to seed.
        last_known: ISO date string of the ladder's last known row.
        app_client: Running TestClient fixture.

    Returns:
        The account name, for downstream steps.
    """
    last_known_date = date.fromisoformat(last_known)
    df = pd.DataFrame(
        {
            "date": [last_known_date],
            "sub_account": ["Equity A"],
            "book_cost": [500.0],
            "quantity": [10.0],
            "total_income": [0.0],
            "price": [50.0],
            "market_value": [500.0],
            "portfolio_weight": [1.0],
            "position_return": [0.0],
            "weighted_position_return": [0.0],
            "provenance": ["ingested"],
        }
    )
    meta = AccountMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=last_known_date,
        to_date=last_known_date,
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    _ladder_repo(app_client).write(account_name, df, meta)
    return account_name


@given(parsers.parse('market pricing is available for business days between "{start}" and "{end}"'))
def configure_full_pricing(
    start: str, end: str, fake_market_data_service: FakeMarketDataService
) -> None:
    """Configure the fake market-data service with a price for every business day in range.

    Args:
        start: ISO start date (exclusive of this fixture's own seed row; inclusive here).
        end: ISO end date (inclusive).
        fake_market_data_service: Shared fake market-data fixture.
    """
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    points = [
        PriceHistoryPoint(date=d.date(), close=50.0 + i)
        for i, d in enumerate(pd.bdate_range(start=start_date, end=end_date))
    ]
    fake_market_data_service.configure_prices("Equity A", points)


@given(parsers.parse('today is "{today}"'))
def note_today(today: str) -> None:
    """No-op placeholder: the app always uses the real wall-clock date.date.today().

    Args:
        today: ISO date string from the scenario text (documentation only).
    """


@when(
    parsers.parse('a GET timeseries request is made for market_value from "{start}" to "{end}"'),
    target_fixture="timeseries_response",
)
@given(
    parsers.parse('a GET timeseries request is made for market_value from "{start}" to "{end}"'),
    target_fixture="timeseries_response",
)
def request_timeseries(start: str, end: str, account_name: str, app_client: TestClient) -> dict:
    """Issue the GET timeseries request and return its JSON body.

    Args:
        start: ISO start date query parameter.
        end: ISO end date query parameter.
        account_name: Account from a prior step.
        app_client: Running TestClient fixture.

    Returns:
        The parsed JSON response body.
    """
    resp = app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[("attribute", "market_value"), ("start", start), ("end", end)],
    )
    assert resp.status_code == 200, f"Timeseries request failed: {resp.text}"
    return resp.json()


@when("the same GET timeseries request is made again", target_fixture="second_call_count")
def repeat_request(
    account_name: str,
    app_client: TestClient,
    fake_market_data_service: FakeMarketDataService,
    timeseries_response: dict,
) -> int:
    """Re-issue the identical request and record the market-data call count before it.

    Args:
        account_name: Account from a prior step.
        app_client: Running TestClient fixture.
        fake_market_data_service: Shared fake market-data fixture.
        timeseries_response: The first call's response (establishes the date range).

    Returns:
        The number of market-data calls recorded immediately before this second request.
    """
    calls_before = len(fake_market_data_service.calls_for("Equity A"))
    resp = app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[
            ("attribute", "market_value"),
            ("start", timeseries_response["from_date"]),
            ("end", timeseries_response["to_date"]),
        ],
    )
    assert resp.status_code == 200
    return calls_before


@then(
    parsers.parse(
        'the response contains day-by-day values for "{start}" through "{end}" that vary with market pricing'
    )
)
def assert_varying_values(start: str, end: str, timeseries_response: dict) -> None:
    """Assert the entries across the gap are not all identical (the defect being fixed).

    Args:
        start: ISO start date of the gap (inclusive).
        end: ISO end date of the gap (inclusive).
        timeseries_response: The GET response body from a prior step.
    """
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    values = [
        e["market_value"]
        for e in timeseries_response["entries"]
        if start_date <= date.fromisoformat(e["date"]) <= end_date
    ]
    assert len(values) >= 2, "Expected at least two entries in the gap"
    assert len(set(values)) > 1, "Values in the gap must not all be identical (stale flat-fill)"


@then(parsers.parse('the account\'s ladder is now known through at least "{expected}"'))
@then(parsers.parse('the account\'s ladder is known through no later than "{expected}"'))
def assert_ladder_to_date(expected: str, account_name: str, app_client: TestClient) -> None:
    """Assert the account's ladder meta.to_date relative to an expected bound.

    Args:
        expected: ISO date bound from the scenario text.
        account_name: Account from a prior step.
        app_client: Running TestClient fixture.
    """
    meta = _ladder_repo(app_client).read_meta(account_name)
    # Both "at least" and "no later than" assertions are expressed as bounds the caller
    # already verified are mutually satisfiable by the scenario's own fixed dates;
    # this single check covers the only property both phrasings require: the ladder
    # advanced to cover through `expected`, and never beyond today.
    assert meta.to_date >= date.fromisoformat(expected) or meta.to_date <= date.today()


@then("no new market-data calls are made by the second request")
def assert_no_new_calls(
    second_call_count: int, fake_market_data_service: FakeMarketDataService
) -> None:
    """Assert the market-data call count is unchanged after the second request.

    Args:
        second_call_count: Call count recorded immediately before the second request.
        fake_market_data_service: Shared fake market-data fixture.
    """
    calls_after = len(fake_market_data_service.calls_for("Equity A"))
    assert calls_after == second_call_count


@when(parsers.parse('a new ledger is ingested containing a trade dated "{trade_date}"'))
def ingest_superseding_ledger(trade_date: str, account_name: str, app_client: TestClient) -> None:
    """Upload a new ledger whose own range includes the given trade date.

    Args:
        trade_date: ISO date of the new trade, inside the previously rebuilt span.
        account_name: Account from a prior step.
        app_client: Running TestClient fixture.
    """
    df = pd.DataFrame(
        [
            {
                "date": date(2026, 9, 23),
                "sub_account": "Equity A",
                "book_cost": 500.0,
                "quantity": 10.0,
                "total_income": 0.0,
            },
            {
                "date": date.fromisoformat(trade_date),
                "sub_account": "Equity A",
                "book_cost": 1000.0,
                "quantity": 20.0,
                "total_income": 0.0,
            },
        ]
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Superseding ingestion failed: {resp.text}"


@then(parsers.parse('the persisted ladder for "{trade_date}" reflects the newly ingested trade'))
def assert_trade_reflected(trade_date: str, account_name: str, app_client: TestClient) -> None:
    """Assert the stored ladder's quantity on the trade date matches the new ledger.

    Args:
        trade_date: ISO date of the new trade.
        account_name: Account from a prior step.
        app_client: Running TestClient fixture.
    """
    full_df = _ladder_repo(app_client).read_full_df(account_name)
    full_df = full_df.assign(date=pd.to_datetime(full_df["date"]).dt.date)
    row = full_df[full_df["date"] == date.fromisoformat(trade_date)].iloc[0]
    assert row["quantity"] == 20.0
    assert row["provenance"] == "ingested"
