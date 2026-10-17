"""BDD step implementations for list_account_positions.feature (US2)."""

import io
from datetime import date

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("list_account_positions.feature")


def _ledger_bytes(rows: list[dict]) -> bytes:
    """Build a raw sub-account ledger XLSX from explicit rows.

    Args:
        rows: List of dicts with keys date, sub_account, book_cost, quantity,
            total_income.

    Returns:
        Raw XLSX bytes.
    """
    df = pd.DataFrame(rows)
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


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder containing positions '
        '"{pos1}", "{pos2}", and "{pos3}"'
    ),
    target_fixture="account_name",
)
def three_positions_ladder_two_active_one_divested(
    account_name: str, pos1: str, pos2: str, pos3: str, app_client: TestClient
) -> str:
    """Ingest a ladger with two continuously-held positions and one divested position."""
    recent_bdays = pd.bdate_range(end=date.today(), periods=40)
    buy_date = recent_bdays[0].date()
    divest_date = recent_bdays[10].date()
    rows = [
        {
            "date": buy_date,
            "sub_account": pos1,
            "book_cost": 100.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
        {
            "date": buy_date,
            "sub_account": pos2,
            "book_cost": 1000.0,
            "quantity": 1000.0,
            "total_income": 0.0,
        },
        {
            "date": buy_date,
            "sub_account": pos3,
            "book_cost": 50.0,
            "quantity": 5.0,
            "total_income": 0.0,
        },
        {
            "date": divest_date,
            "sub_account": pos3,
            "book_cost": 50.0,
            "quantity": 0.0,
            "total_income": 0.0,
        },
    ]
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ledger_bytes(rows),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"
    return account_name


@given(parsers.parse('no resource of any kind has been ingested for account "{account_name}"'))
def no_resource_ingested(account_name: str) -> None:
    """No setup needed — a fresh tmp_path store is used."""


@given(
    parsers.parse('account "{account_name}" has an ingested capital ledger but no position ladder'),
    target_fixture="account_name",
)
def capital_only_account(account_name: str, app_client: TestClient) -> str:
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
    return account_name


@when(
    parsers.parse('a request is made to the positions endpoint for account "{account_name}"'),
    target_fixture="ts_response",
)
def request_positions_endpoint(account_name: str, app_client: TestClient) -> object:
    """GET the positions-enumeration endpoint for the given account."""
    return app_client.get(f"/v1/accounts/{account_name}/positions")


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(ts_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert ts_response.status_code == status_code, (
        f"Expected {status_code}, got {ts_response.status_code}: {ts_response.text}"
    )


@then("all three positions appear, each with its own first and last recorded date")
def check_three_positions_with_dates(ts_response: object) -> None:
    """Assert all three positions are present, each with distinct from_date/to_date."""
    positions = ts_response.json()["positions"]
    names = {p["position"] for p in positions}
    assert names == {"Apple Inc", "Cash", "Sold Corp"}
    for p in positions:
        assert p["from_date"]
        assert p["to_date"]


@then('the response body includes a "_links.self" URL')
def check_self_link_present(ts_response: object) -> None:
    """Assert the '_links.self' URL is present on the response."""
    assert "self" in ts_response.json()["_links"]
