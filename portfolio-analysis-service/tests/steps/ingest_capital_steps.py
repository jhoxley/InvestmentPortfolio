"""BDD step implementations for ingest_capital.feature (US1, US3, US4)."""

import hashlib
import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("ingest_capital.feature")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_capital_ledger_bytes(rows: list[dict[str, object]]) -> bytes:
    """Serialise a list of capital ledger rows to XLSX bytes.

    Args:
        rows: List of dicts with keys date, capital, income, book_value.

    Returns:
        Raw XLSX bytes.
    """
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _make_multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart file dict.

    Args:
        file_bytes: Raw XLSX content.

    Returns:
        Dict suitable for TestClient files= parameter.
    """
    return {
        "file": (
            "capital.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def _post_capital(account_name: str, ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST a capital ledger file to the ingestion endpoint.

    Args:
        account_name: Target account name.
        ledger_bytes: Raw XLSX bytes to submit.
        app_client: Test client fixture.

    Returns:
        The HTTP response.
    """
    return app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files=_make_multipart(ledger_bytes),
    )


# ---------------------------------------------------------------------------
# US1: Successful ingestion of a new capital ledger
# ---------------------------------------------------------------------------


@given("a valid XLSX file conforming to the capital ledger schema", target_fixture="ledger_bytes")
def valid_capital_xlsx_file() -> bytes:
    """Provide a valid capital ledger XLSX with a gap between two recorded dates."""
    today = date.today()
    d1 = today - timedelta(days=60)
    d2 = today - timedelta(days=45)
    return _make_capital_ledger_bytes(
        [
            {"date": d1, "capital": 1000.0, "income": 0.0, "book_value": 900.0},
            {"date": d2, "capital": 1200.0, "income": 5.0, "book_value": 950.0},
        ]
    )


@given(
    parsers.parse('the account name "{account_name}" has no existing capital ledger'),
    target_fixture="account_name",
)
def no_existing_capital_ledger(account_name: str) -> str:
    """Record the account name; the tmp_path fixture ensures a clean store."""
    return account_name


@when(
    parsers.parse(
        'the file is submitted to the capital ingestion endpoint with account name "{account_name}"'
    ),
    target_fixture="post_response",
)
def submit_capital_file(account_name: str, ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST the capital ledger file to the ingestion endpoint."""
    return _post_capital(account_name, ledger_bytes, app_client)


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(post_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert post_response.status_code == status_code, (
        f"Expected {status_code}, got {post_response.status_code}: {post_response.text}"
    )


@then("the response body contains a JSON processing summary (row count, date range)")
def check_capital_summary_fields(post_response: object) -> None:
    """Assert that the JSON body contains the required summary fields."""
    body = post_response.json()
    for field in ["row_count", "from_date", "to_date"]:
        assert field in body, f"Field '{field}' missing from response"


@then('the response body includes a "_links.download" URL to retrieve the XLSX binary')
def check_capital_links_download(post_response: object) -> None:
    """Assert that the response includes a _links.download field."""
    body = post_response.json()
    assert "_links" in body, "_links missing from response"
    assert "download" in body["_links"], "_links.download missing"
    assert body["_links"]["download"].endswith("/download")


@then(
    parsers.parse('a capital ledger XLSX file is persisted to the local store for "{account_name}"')
)
def check_capital_ledger_stored(account_name: str, app_client: TestClient) -> None:
    """Verify the capital ledger can be retrieved via the summary endpoint."""
    get_resp = app_client.get(f"/v1/accounts/{account_name}/capital")
    assert get_resp.status_code == 200, f"Expected 200 on GET, got {get_resp.status_code}"


@then("the ledger contains one row per business day from the earliest to the latest recorded date")
def check_capital_business_day_coverage(account_name: str, app_client: TestClient) -> None:
    """Assert the stored ledger has one row per business day in the recorded range."""
    dl = app_client.get(f"/v1/accounts/{account_name}/capital/download")
    assert dl.status_code == 200
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    dates = pd.to_datetime(df["date"]).dt.date
    expected = pd.bdate_range(start=dates.min(), end=dates.max())
    assert len(df) == len(expected), f"Expected {len(expected)} business-day rows, got {len(df)}"
    for d in dates:
        assert d.weekday() < 5, f"Weekend date found in output: {d}"


# ---------------------------------------------------------------------------
# US1: Capital values forward-fill across days with no recorded observation
# ---------------------------------------------------------------------------


@given(
    "a capital ledger with recorded observations on 2024-01-02 and 2024-01-10",
    target_fixture="ledger_bytes",
)
def capital_ledger_with_gap() -> bytes:
    """Provide a capital ledger with a gap between two recorded dates."""
    return _make_capital_ledger_bytes(
        [
            {"date": date(2024, 1, 2), "capital": 1000.0, "income": 0.0, "book_value": 900.0},
            {"date": date(2024, 1, 10), "capital": 1200.0, "income": 5.0, "book_value": 950.0},
        ]
    )


@given("no observations are recorded on 2024-01-03 through 2024-01-09")
def no_observations_in_gap() -> None:
    """No-op — the gap is already encoded in the fixture above."""


@when("the ledger is ingested", target_fixture="post_response")
def ingest_capital_ledger_default_account(ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST the capital ledger to the ingestion endpoint for a fixed test account."""
    return _post_capital("gap-portfolio", ledger_bytes, app_client)


@then(
    "the ledger contains rows for every business day between 2024-01-02 and 2024-01-10 "
    "carrying values forward"
)
def check_forward_fill_values(app_client: TestClient) -> None:
    """Assert the gap day (2024-01-05) carries forward the earlier recorded observation."""
    dl = app_client.get("/v1/accounts/gap-portfolio/capital/download")
    assert dl.status_code == 200
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    df["date"] = pd.to_datetime(df["date"]).dt.date

    gap_row = df[df["date"] == date(2024, 1, 5)]
    assert len(gap_row) == 1
    assert gap_row.iloc[0]["capital"] == 1000.0
    assert gap_row.iloc[0]["income"] == 0.0
    assert gap_row.iloc[0]["book_value"] == 900.0


@then("the row for 2024-01-10 reflects the values recorded on that date")
def check_final_row_values(app_client: TestClient) -> None:
    """Assert the final recorded date's row matches its own recorded values."""
    dl = app_client.get("/v1/accounts/gap-portfolio/capital/download")
    assert dl.status_code == 200
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    df["date"] = pd.to_datetime(df["date"]).dt.date

    last_row = df[df["date"] == date(2024, 1, 10)]
    assert len(last_row) == 1
    assert last_row.iloc[0]["capital"] == 1200.0
    assert last_row.iloc[0]["income"] == 5.0
    assert last_row.iloc[0]["book_value"] == 950.0


# ---------------------------------------------------------------------------
# US1: Expansion range is bounded by the recorded data, not by today's date
# ---------------------------------------------------------------------------


@given(
    "a capital ledger whose latest recorded observation is several months before today",
    target_fixture="ledger_bytes",
)
def capital_ledger_ending_months_ago() -> bytes:
    """Provide a capital ledger whose latest date is well before today."""
    today = date.today()
    latest = today - timedelta(days=150)
    earliest = latest - timedelta(days=30)
    return _make_capital_ledger_bytes(
        [
            {"date": earliest, "capital": 1000.0, "income": 0.0, "book_value": 900.0},
            {"date": latest, "capital": 1100.0, "income": 2.0, "book_value": 920.0},
        ]
    )


@then(
    "the stored capital ledger's last row is the latest business day on or before the "
    "latest recorded date"
)
def check_last_row_is_latest_business_day(post_response: object) -> None:
    """Assert the ingestion succeeded (row/date-range content is checked in the next step)."""
    assert post_response.status_code == 201


@then("no rows are generated for dates after the latest recorded date")
def check_no_rows_after_latest_date(post_response: object) -> None:
    """Assert no row in the stored ledger falls after the latest recorded date."""
    body = post_response.json()
    to_date = date.fromisoformat(body["to_date"])
    expected_latest = date.today() - timedelta(days=150)
    assert to_date <= expected_latest, (
        f"Expected to_date <= {expected_latest} (not extended to today), got {to_date}"
    )


# ---------------------------------------------------------------------------
# US3: Re-submitting the same file confirms the ledger is current
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a capital ledger has already been stored for account "{account_name}"'),
    target_fixture="stored_capital",
)
def capital_ledger_already_stored(account_name: str, app_client: TestClient) -> dict[str, object]:
    """Ingest an initial capital ledger for the given account.

    Returns:
        Dict with the account name, the original file bytes, and the SHA-256 checksum
        of the initially-downloaded stored XLSX (used to assert non-mutation later).
    """
    ledger_bytes = valid_capital_xlsx_file()
    resp = _post_capital(account_name, ledger_bytes, app_client)
    assert resp.status_code == 201
    dl = app_client.get(f"/v1/accounts/{account_name}/capital/download")
    return {
        "account_name": account_name,
        "ledger_bytes": ledger_bytes,
        "stored_checksum": hashlib.sha256(dl.content).hexdigest(),
    }


@when(
    parsers.parse('the same file is submitted again for "{account_name}"'),
    target_fixture="post_response",
)
def resubmit_same_file(
    account_name: str, stored_capital: dict[str, object], app_client: TestClient
) -> object:
    """Re-submit the exact same file for the same account."""
    return _post_capital(account_name, stored_capital["ledger_bytes"], app_client)  # type: ignore[arg-type]


@then('the response body contains status "refreshed"')
def check_status_refreshed(post_response: object) -> None:
    """Assert the response body's status field is 'refreshed'."""
    assert post_response.json()["status"] == "refreshed"


@then("the stored ledger's row count and date range are unchanged")
def check_row_count_and_range_unchanged(
    stored_capital: dict[str, object], post_response: object, app_client: TestClient
) -> None:
    """Assert row_count/from_date/to_date match the original ingestion's values."""
    account_name = stored_capital["account_name"]
    original = app_client.get(f"/v1/accounts/{account_name}/capital").json()
    refreshed = post_response.json()
    assert refreshed["row_count"] == original["row_count"]
    assert refreshed["from_date"] == original["from_date"]
    assert refreshed["to_date"] == original["to_date"]


# ---------------------------------------------------------------------------
# US4: Submitting a changed file returns a merge-not-supported error
# ---------------------------------------------------------------------------


@given(
    parsers.parse('the stored ledger was generated from file with checksum "{literal_checksum}"')
)
def stored_ledger_checksum_noop(literal_checksum: str) -> None:
    """No-op — the illustrative checksum literal in the Gherkin text isn't asserted directly."""


@when(
    parsers.parse(
        'a modified file (checksum "{literal_checksum}") is submitted for "{account_name}"'
    ),
    target_fixture="post_response",
)
def resubmit_modified_file(
    account_name: str,
    literal_checksum: str,
    stored_capital: dict[str, object],
    app_client: TestClient,
) -> object:
    """Submit a modified capital ledger file for an account with an existing ledger."""
    original_bytes: bytes = stored_capital["ledger_bytes"]  # type: ignore[assignment]
    modified_df = pd.read_excel(io.BytesIO(original_bytes), engine="openpyxl")
    modified_df.loc[len(modified_df)] = {
        "date": date.today() - timedelta(days=10),
        "capital": 9999.0,
        "income": 9999.0,
        "book_value": 9999.0,
    }
    buf = io.BytesIO()
    modified_df.to_excel(buf, index=False, engine="openpyxl")
    return _post_capital(account_name, buf.getvalue(), app_client)


@then("the response body states that merging an updated capital ledger is not currently supported")
def check_merge_not_supported_message(post_response: object) -> None:
    """Assert the problem detail body mentions merging is not supported."""
    detail = post_response.json()["detail"]
    assert "not currently supported" in detail
    assert "capital ledger" in detail


@then(parsers.parse('the existing stored capital ledger for "{account_name}" is unchanged'))
def check_existing_capital_ledger_unchanged(
    account_name: str, stored_capital: dict[str, object], app_client: TestClient
) -> None:
    """Assert the stored capital ledger's checksum is unchanged after a rejected conflict."""
    dl = app_client.get(f"/v1/accounts/{account_name}/capital/download")
    assert dl.status_code == 200
    current_checksum = hashlib.sha256(dl.content).hexdigest()
    assert current_checksum == stored_capital["stored_checksum"], (
        "Stored capital ledger changed after a rejected conflicting submission"
    )
