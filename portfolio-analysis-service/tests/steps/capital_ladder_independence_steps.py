"""BDD step implementations for capital_ladder_independence.feature.

Closes a coverage gap surfaced by /speckit-analyze: FR-011's guarantee that a
capital ledger and a position ladder for the same account are stored and
versioned independently — ingesting one must have no effect on the other.
"""

import hashlib
import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("capital_ladder_independence.feature")


def _ladder_xlsx_bytes() -> bytes:
    """Build a minimal valid position ladder XLSX.

    Returns:
        Raw XLSX bytes.
    """
    today = date.today()
    d1 = today - timedelta(days=30)
    df = pd.DataFrame(
        {
            "date": [d1],
            "sub_account": ["Cash"],
            "book_cost": [1000.0],
            "quantity": [1000.0],
            "total_income": [0.0],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _capital_xlsx_bytes() -> bytes:
    """Build a minimal valid capital ledger XLSX.

    Returns:
        Raw XLSX bytes.
    """
    today = date.today()
    d1 = today - timedelta(days=30)
    df = pd.DataFrame(
        {
            "date": [d1],
            "capital": [1000.0],
            "income": [0.0],
            "book_value": [900.0],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _post_ladder(account_name: str, client: TestClient) -> None:
    """Ingest a position ladder for the given account, asserting success.

    Args:
        account_name: Target account name.
        client: Test client fixture.
    """
    resp = client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ladder_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Ladder setup ingestion failed: {resp.text}"


def _post_capital(account_name: str, client: TestClient) -> None:
    """Ingest a capital ledger for the given account, asserting success.

    Args:
        account_name: Target account name.
        client: Test client fixture.
    """
    resp = client.post(
        f"/v1/accounts/{account_name}/capital",
        files={
            "file": (
                "capital.xlsx",
                _capital_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Capital setup ingestion failed: {resp.text}"


# ---------------------------------------------------------------------------
# Scenario 1: capital ingestion does not affect an existing ladder
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a position ladder has been stored for account "{account_name}"'),
    target_fixture="ladder_checksum",
)
def ladder_already_stored(account_name: str, app_client: TestClient) -> str:
    """Ingest a position ladder and return its stored download checksum."""
    _post_ladder(account_name, app_client)
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    return hashlib.sha256(dl.content).hexdigest()


@when(
    parsers.parse('a capital ledger is ingested for account "{account_name}"'),
    target_fixture="cross_response",
)
def ingest_capital_for_cross_check(account_name: str, app_client: TestClient) -> object:
    """Ingest a capital ledger for the same account as the stored ladder."""
    return app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files={
            "file": (
                "capital.xlsx",
                _capital_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


@then(parsers.parse('the position ladder for "{account_name}" is unchanged'))
def check_ladder_unchanged(account_name: str, ladder_checksum: str, app_client: TestClient) -> None:
    """Assert the stored position ladder's checksum is unchanged."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    assert dl.status_code == 200
    current = hashlib.sha256(dl.content).hexdigest()
    assert current == ladder_checksum, "Position ladder changed after capital ledger ingestion"


@then(parsers.parse('the capital ledger for "{account_name}" is retrievable'))
def check_capital_retrievable(account_name: str, app_client: TestClient) -> None:
    """Assert the capital ledger summary can be retrieved."""
    resp = app_client.get(f"/v1/accounts/{account_name}/capital")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Scenario 2: position ladder ingestion does not affect an existing capital ledger
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a capital ledger has been stored for account "{account_name}"'),
    target_fixture="capital_checksum",
)
def capital_already_stored(account_name: str, app_client: TestClient) -> str:
    """Ingest a capital ledger and return its stored download checksum."""
    _post_capital(account_name, app_client)
    dl = app_client.get(f"/v1/accounts/{account_name}/capital/download")
    return hashlib.sha256(dl.content).hexdigest()


@when(
    parsers.parse('a position ladder is ingested for account "{account_name}"'),
    target_fixture="cross_response",
)
def ingest_ladder_for_cross_check(account_name: str, app_client: TestClient) -> object:
    """Ingest a position ladder for the same account as the stored capital ledger."""
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ladder_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


@then(parsers.parse('the capital ledger for "{account_name}" is unchanged'))
def check_capital_unchanged(
    account_name: str, capital_checksum: str, app_client: TestClient
) -> None:
    """Assert the stored capital ledger's checksum is unchanged."""
    dl = app_client.get(f"/v1/accounts/{account_name}/capital/download")
    assert dl.status_code == 200
    current = hashlib.sha256(dl.content).hexdigest()
    assert current == capital_checksum, "Capital ledger changed after position ladder ingestion"


@then(parsers.parse('the position ladder for "{account_name}" is retrievable'))
def check_ladder_retrievable(account_name: str, app_client: TestClient) -> None:
    """Assert the position ladder summary can be retrieved."""
    resp = app_client.get(f"/v1/accounts/{account_name}/ladder")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
