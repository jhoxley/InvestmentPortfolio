"""BDD step implementations for pricing_errors.feature (US3)."""

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from tests.conftest import FakeIdentifierMappingRepository, FakeMarketDataService

scenarios("pricing_errors.feature")


def _make_multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart file dict."""
    return {
        "file": (
            "ledger.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def _ledger_bytes(sub_accounts: list[str], days_back: int = 30) -> bytes:
    """Build a minimal valid XLSX ledger for the given sub-accounts."""
    today = date.today()
    d1 = today - timedelta(days=days_back)
    rows = [
        {
            "date": d1,
            "sub_account": sa,
            "book_cost": 1000.0,
            "quantity": 1000.0 if sa == "Cash" else 10.0,
            "total_income": 0.0,
        }
        for sa in sub_accounts
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@given(
    parsers.parse(
        'a ledger for account "{account_name}" with sub-account "{sub_account}" active '
        "from a start date to today"
    ),
    target_fixture="ledger_bytes",
)
def ledger_single_sub_account(account_name: str, sub_account: str) -> bytes:
    """Provide a ledger with Cash and one named non-Cash sub-account."""
    return _ledger_bytes(["Cash", sub_account])


@given(
    parsers.parse('a ledger for account "{account_name}" with sub-account "{sub_account}"'),
    target_fixture="ledger_bytes",
)
def ledger_single_sub_account_unmapped(account_name: str, sub_account: str) -> bytes:
    """Provide a ledger with Cash and one named non-Cash sub-account (unmapped scenario)."""
    return _ledger_bytes(["Cash", sub_account])


@given(
    parsers.parse(
        'a ledger for account "{account_name}" with sub-accounts "{sub_account_a}" and '
        '"{sub_account_b}"'
    ),
    target_fixture="ledger_bytes",
)
def ledger_two_sub_accounts(account_name: str, sub_account_a: str, sub_account_b: str) -> bytes:
    """Provide a ledger with Cash and two named non-Cash sub-accounts."""
    return _ledger_bytes(["Cash", sub_account_a, sub_account_b])


@given(parsers.parse('the market data service has a gap in "{identifier}"\'s GBP price history'))
def market_data_has_gap(identifier: str, fake_market_data_service: FakeMarketDataService) -> None:
    """Configure the fake market-data-service to return no prices at all for an identifier."""
    fake_market_data_service.configure_prices(identifier, [])


@given(parsers.parse('the identifier mapping has no entry for "{sub_account}"'))
def mapping_has_no_entry(
    sub_account: str, fake_identifier_mapping_repository: FakeIdentifierMappingRepository
) -> None:
    """Configure the fake mapping repository to have no entry for a sub-account."""
    fake_identifier_mapping_repository.set_missing(sub_account)


@when(
    parsers.parse('the ledger is ingested for account "{account_name}"'),
    target_fixture="post_response",
)
def ingest_ledger(account_name: str, ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST the ledger to the ingestion endpoint."""
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(ledger_bytes),
    )


@then(parsers.parse("the ingestion request fails with status {status_code:d}"))
def check_failure_status(post_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert post_response.status_code == status_code, post_response.text


@then(parsers.parse('the error identifies "{name}"'))
def check_error_identifies(post_response: object, name: str) -> None:
    """Assert the error's detail text names the given sub-account."""
    body = post_response.json()
    assert name in body.get("detail", ""), f"'{name}' not found in error detail: {body}"


@then(parsers.parse('the error identifies both "{name_a}" and "{name_b}" in the same response'))
def check_error_identifies_both(post_response: object, name_a: str, name_b: str) -> None:
    """Assert the error's detail text names both sub-accounts together."""
    body = post_response.json()
    detail = body.get("detail", "")
    assert name_a in detail, f"'{name_a}' not found in error detail: {body}"
    assert name_b in detail, f"'{name_b}' not found in error detail: {body}"


@then(parsers.parse('no position ladder is persisted or updated for "{account_name}"'))
def check_no_ladder_persisted(account_name: str, app_client: TestClient) -> None:
    """Assert no ladder exists for the account after a failed ingestion."""
    resp = app_client.get(f"/v1/accounts/{account_name}/ladder")
    assert resp.status_code == 404, f"Expected no ladder to exist, got {resp.status_code}"
