"""BDD step implementations for list_accounts.feature (US3)."""

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("list_accounts.feature")


def _ladder_bytes() -> bytes:
    """Build a minimal valid sub-account ledger XLSX starting well in the past.

    Returns:
        Raw XLSX bytes.
    """
    earliest = date.today() - timedelta(days=365 * 5)
    df = pd.DataFrame(
        {
            "date": [earliest],
            "sub_account": ["Cash"],
            "book_cost": [1000.0],
            "quantity": [1000.0],
            "total_income": [0.0],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _capital_bytes() -> bytes:
    """Build a minimal valid capital ledger XLSX.

    Returns:
        Raw XLSX bytes.
    """
    df = pd.DataFrame(
        {
            "date": [date(2020, 1, 2), date(2021, 6, 1)],
            "capital": [1000.0, 2000.0],
            "income": [0.0, 10.0],
            "book_value": [900.0, 1800.0],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@given(parsers.parse('account "{account_name}" has an ingested capital ledger and position ladder'))
def dual_resource_account(account_name: str, app_client: TestClient) -> None:
    """Ingest both a position ladder and a capital ledger for the given account."""
    ladder_resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ladder_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert ladder_resp.status_code == 201, f"Ladder setup failed: {ladder_resp.text}"

    capital_resp = app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files={
            "file": (
                "capital.xlsx",
                _capital_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert capital_resp.status_code == 201, f"Capital setup failed: {capital_resp.text}"


@given(
    parsers.parse('account "{account_name}" has an ingested capital ledger but no position ladder')
)
def capital_only_account(account_name: str, app_client: TestClient) -> None:
    """Ingest only a capital ledger for the given account."""
    resp = app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files={
            "file": (
                "capital.xlsx",
                _capital_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Capital setup failed: {resp.text}"


@when("a request is made to the accounts endpoint", target_fixture="accounts_response")
def request_accounts(app_client: TestClient) -> object:
    """GET the accounts-enumeration endpoint."""
    return app_client.get("/v1/accounts")


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(accounts_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert accounts_response.status_code == status_code, (
        f"Expected {status_code}, got {accounts_response.status_code}: {accounts_response.text}"
    )


@then(
    parsers.parse(
        '"{account_name}" appears with its capital ledger date range and position ladder date range'
    )
)
def check_both_ranges_present(accounts_response: object, account_name: str) -> None:
    """Assert the named account has both a capital_ledger and position_ladder range."""
    accounts = {a["account_name"]: a for a in accounts_response.json()["accounts"]}
    assert account_name in accounts, f"'{account_name}' not found in accounts response"
    entry = accounts[account_name]
    assert entry["capital_ledger"] is not None
    assert entry["position_ladder"] is not None


@then(
    parsers.parse(
        '"{account_name}" appears with a capital ledger date range and no position ladder range'
    )
)
def check_capital_only_range(accounts_response: object, account_name: str) -> None:
    """Assert the named account has a capital_ledger range and a null position_ladder."""
    accounts = {a["account_name"]: a for a in accounts_response.json()["accounts"]}
    assert account_name in accounts, f"'{account_name}' not found in accounts response"
    entry = accounts[account_name]
    assert entry["capital_ledger"] is not None
    assert entry["position_ladder"] is None


@then('the response body includes a "_links.self" URL')
def check_self_link_present(accounts_response: object) -> None:
    """Assert the _links.self key is present."""
    assert "self" in accounts_response.json()["_links"]
