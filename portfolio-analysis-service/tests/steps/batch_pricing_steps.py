"""BDD step implementations for batch_pricing.feature (US2)."""

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from tests.conftest import FakeMarketDataService

scenarios("batch_pricing.feature")


def _make_multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart file dict."""
    return {
        "file": (
            "ledger.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def _ledger_bytes(rows: list[dict[str, object]]) -> bytes:
    """Serialise the given rows to XLSX bytes."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@given(
    parsers.parse(
        'a ledger for account "{account_name}" with sub-account "{sub_account}" active '
        "over 60 business days"
    ),
    target_fixture="ledger_bytes",
)
def ledger_single_wide_range(account_name: str, sub_account: str) -> bytes:
    """Provide a ledger where one sub-account spans well over 60 business days."""
    today = date.today()
    start = today - timedelta(days=100)
    rows = [
        {
            "date": start,
            "sub_account": "Cash",
            "book_cost": 1000.0,
            "quantity": 1000.0,
            "total_income": 0.0,
        },
        {
            "date": start,
            "sub_account": sub_account,
            "book_cost": 500.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
    ]
    return _ledger_bytes(rows)


@given(
    parsers.parse(
        'a ledger for account "{account_name}" with sub-accounts "{sub_account_a}" and '
        '"{sub_account_b}" active over different ranges'
    ),
    target_fixture="ledger_bytes",
)
def ledger_two_different_ranges(account_name: str, sub_account_a: str, sub_account_b: str) -> bytes:
    """Provide a ledger where two sub-accounts start at different dates."""
    today = date.today()
    start_a = today - timedelta(days=100)
    start_b = today - timedelta(days=50)
    rows = [
        {
            "date": start_a,
            "sub_account": "Cash",
            "book_cost": 1000.0,
            "quantity": 1000.0,
            "total_income": 0.0,
        },
        {
            "date": start_a,
            "sub_account": sub_account_a,
            "book_cost": 500.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
        {
            "date": start_b,
            "sub_account": sub_account_b,
            "book_cost": 500.0,
            "quantity": 5.0,
            "total_income": 0.0,
        },
    ]
    return _ledger_bytes(rows)


@when(
    parsers.parse('the ledger is ingested for account "{account_name}"'),
    target_fixture="post_response",
)
def ingest_ledger(account_name: str, ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST the ledger to the ingestion endpoint."""
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(ledger_bytes),
    )
    assert resp.status_code == 201, resp.text
    return resp


@then(parsers.parse('exactly one price-history request is made for "{identifier}"'))
def check_exactly_one_call(
    identifier: str, post_response: object, fake_market_data_service: FakeMarketDataService
) -> None:
    """Assert exactly one request was made for the given identifier."""
    calls = fake_market_data_service.calls_for(identifier)
    assert len(calls) == 1, f"Expected exactly 1 call for '{identifier}', got {len(calls)}"


@then('no price-history request is made for the "Cash" sub-account')
def check_no_cash_call(
    post_response: object, fake_market_data_service: FakeMarketDataService
) -> None:
    """Assert Cash never triggers a price-history request."""
    assert fake_market_data_service.calls_for("Cash") == []
