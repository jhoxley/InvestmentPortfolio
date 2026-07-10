"""BDD step implementations for retrieve_capital.feature (US2)."""

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("retrieve_capital.feature")


def _ingest(account_name: str, client: TestClient) -> None:
    """Helper: ingest a minimal capital ledger for the given account.

    Args:
        account_name: Account identifier to use.
        client: TestClient to POST against.
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
    resp = client.post(
        f"/v1/accounts/{account_name}/capital",
        files={
            "file": (
                "capital.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Setup ingestion failed: {resp.text}"


# ---------------------------------------------------------------------------
# Retrieve summary scenarios
# ---------------------------------------------------------------------------


@given(parsers.parse('a capital ledger has previously been stored for account "{account_name}"'))
def setup_stored_capital_ledger(account_name: str, app_client: TestClient) -> None:
    """Ingest a capital ledger so the GET endpoint has something to return."""
    _ingest(account_name, app_client)


@given(parsers.parse('no capital ledger exists for account "{account_name}"'))
def no_capital_ledger_for_account(account_name: str) -> None:
    """No setup needed — a fresh tmp_path store is used."""


@when(
    parsers.parse('a GET request is made for the capital ledger summary of "{account_name}"'),
    target_fixture="get_response",
)
def get_capital_ledger(account_name: str, app_client: TestClient) -> object:
    """Make a GET request for the capital ledger summary."""
    return app_client.get(f"/v1/accounts/{account_name}/capital")


@then(parsers.parse("the response status is {status_code:d}"))
def check_response_status(get_response: object, status_code: int) -> None:
    """Assert the HTTP status code."""
    assert get_response.status_code == status_code, (
        f"Expected {status_code}, got {get_response.status_code}: {get_response.text}"
    )


@then("the response body is a JSON object containing row count and date range")
def check_summary_shape(get_response: object) -> None:
    """Assert all required summary fields are present."""
    body = get_response.json()
    for field in ["row_count", "from_date", "to_date"]:
        assert field in body, f"'{field}' missing from GET response"


@then('the response body includes a "_links.self" and a "_links.download" URL')
def check_hateoas_links(get_response: object) -> None:
    """Assert both HATEOAS links are present."""
    body = get_response.json()
    assert "_links" in body, "_links missing"
    assert "self" in body["_links"], "_links.self missing"
    assert "download" in body["_links"], "_links.download missing"


@then("the response body contains a descriptive error message")
def check_error_message(get_response: object) -> None:
    """Assert the 404 body has RFC 7807 shape."""
    body = get_response.json()
    assert "detail" in body, "No 'detail' field in error response"
    assert len(body["detail"]) > 0, "Empty error detail"


# ---------------------------------------------------------------------------
# Download scenarios
# ---------------------------------------------------------------------------


@given(parsers.parse('a capital ledger has previously been stored for account "{account_name}"'))
def setup_stored_capital_ledger_for_download(account_name: str, app_client: TestClient) -> None:
    """Ingest a capital ledger for the download scenario."""
    _ingest(account_name, app_client)


@when(
    parsers.parse('a download request is made for the capital ledger of "{account_name}"'),
    target_fixture="download_response",
)
def download_capital_ledger(account_name: str, app_client: TestClient) -> object:
    """Make a GET request to the download endpoint."""
    return app_client.get(f"/v1/accounts/{account_name}/capital/download")


@then(parsers.parse("the download response status is {status_code:d}"))
def check_download_status(download_response: object, status_code: int) -> None:
    """Assert the download HTTP status code."""
    assert download_response.status_code == status_code, (
        f"Expected {status_code}, got {download_response.status_code}"
    )


@then("the content type is the XLSX MIME type")
def check_content_type(download_response: object) -> None:
    """Assert the Content-Type is the XLSX MIME type."""
    ct = download_response.headers.get("content-type", "")
    assert "spreadsheetml" in ct, f"Unexpected content type: {ct}"


@then("the Content-Disposition header specifies an attachment filename")
def check_content_disposition(download_response: object) -> None:
    """Assert Content-Disposition is an attachment with a .xlsx filename."""
    cd = download_response.headers.get("content-disposition", "")
    assert "attachment" in cd, f"Not an attachment: {cd}"
    assert ".xlsx" in cd, f"No .xlsx filename in Content-Disposition: {cd}"
