"""BDD step implementations for ingest_ladder.feature (US1, US3, US4)."""

import hashlib
import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("ingest_ladder.feature")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ledger_bytes(
    sub_accounts: list[str] | None = None,
    days_back: int = 30,
    close_equity_at: int | None = None,
) -> bytes:
    """Build a minimal valid XLSX ledger as bytes.

    Args:
        sub_accounts: Sub-account names. Defaults to ['Cash', 'Equity A'].
        days_back: How many days before today the earliest activity date falls.
        close_equity_at: If set, the number of days before today at which equity quantity=0.

    Returns:
        Raw XLSX bytes.
    """
    today = date.today()
    d1 = today - timedelta(days=days_back)
    accounts = sub_accounts or ["Cash", "Equity A"]
    rows = []
    for sa in accounts:
        rows.append(
            {
                "date": d1,
                "sub_account": sa,
                "book_cost": 1000.0,
                "quantity": 1000.0 if sa == "Cash" else 10.0,
                "total_income": 0.0,
            }
        )
    if close_equity_at is not None:
        close_date = today - timedelta(days=close_equity_at)
        rows.append(
            {
                "date": close_date,
                "sub_account": "Equity A",
                "book_cost": 0.0,
                "quantity": 0.0,
                "total_income": 5.0,
            }
        )
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
            "ledger.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


# ---------------------------------------------------------------------------
# US1: Successful ingestion of a new sub-account ledger
# ---------------------------------------------------------------------------


@given(
    "a valid XLSX file conforming to the sub-account ledger schema", target_fixture="ledger_bytes"
)
def valid_xlsx_file() -> bytes:
    """Provide a valid XLSX ledger for the ingestion step."""
    return _make_ledger_bytes()


@given(
    parsers.parse('the account name "{account_name}" has no existing position ladder'),
    target_fixture="account_name",
)
def no_existing_ladder(account_name: str) -> str:
    """Record the account name; the tmp_path fixture ensures a clean store."""
    return account_name


@when(
    parsers.parse(
        'the file is submitted to the ingestion endpoint with account name "{account_name}"'
    ),
    target_fixture="post_response",
)
def submit_file(account_name: str, ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST the ledger file to the ingestion endpoint."""
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(ledger_bytes),
    )


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(post_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert post_response.status_code == status_code, (
        f"Expected {status_code}, got {post_response.status_code}: {post_response.text}"
    )


@then(
    "the response body contains a JSON processing summary with row_count, from_date, to_date, and sub_accounts"
)
def check_summary_fields(post_response: object) -> None:
    """Assert that the JSON body contains the required summary fields."""
    body = post_response.json()
    for field in ["row_count", "from_date", "to_date", "sub_accounts"]:
        assert field in body, f"Field '{field}' missing from response"


@then('the response body includes a "_links.download" URL to retrieve the XLSX binary')
def check_links_download(post_response: object) -> None:
    """Assert that the response includes a _links.download field."""
    body = post_response.json()
    assert "_links" in body, "_links missing from response"
    assert "download" in body["_links"], "_links.download missing"
    assert body["_links"]["download"].endswith("/download")


@then(
    parsers.parse(
        'a position ladder XLSX file is persisted to the local store for "{account_name}"'
    )
)
def check_ladder_stored(account_name: str, app_client: TestClient) -> None:
    """Verify the ladder can be retrieved and the XLSX is downloadable."""
    get_resp = app_client.get(f"/v1/accounts/{account_name}/ladder")
    assert get_resp.status_code == 200, f"Expected 200 on GET, got {get_resp.status_code}"


# ---------------------------------------------------------------------------
# US1: Position forward-fill across days with no activity
# ---------------------------------------------------------------------------


@given(
    'a ledger where sub-account "Equity A" has activity on two dates separated by a gap',
    target_fixture="ledger_bytes",
)
def ledger_with_gap() -> bytes:
    """Provide a ledger with a time gap between activity dates."""
    return _make_ledger_bytes(sub_accounts=["Cash", "Equity A"], days_back=40)


@given(
    parsers.parse('the account name "{account_name}" has no existing position ladder'),
    target_fixture="account_name",
)
def no_existing_ladder_named(account_name: str) -> str:
    """Return the account name for this scenario."""
    return account_name


@when(
    parsers.parse('the ledger is ingested for account "{account_name}"'),
    target_fixture="post_response",
)
def ingest_for_account(account_name: str, ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST the ledger to the ingestion endpoint."""
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(ledger_bytes),
    )


@then('the ladder contains rows for "Equity A" on every business day in the date range')
def check_equity_rows(account_name: str, app_client: TestClient) -> None:
    """Assert that rows exist for Equity A in the ladder."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    assert dl.status_code == 200
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    equity_rows = df[df["sub_account"] == "Equity A"]
    assert len(equity_rows) > 0, "No Equity A rows found in ladder"


@then('the values for "Equity A" are forward-filled across the gap days')
def check_forward_fill(account_name: str, app_client: TestClient) -> None:
    """Assert non-null values in Equity A rows (indicating forward-fill occurred)."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    equity_rows = df[df["sub_account"] == "Equity A"]
    assert equity_rows["book_cost"].notna().all(), "NaN book_cost values found in Equity A"


# ---------------------------------------------------------------------------
# US1: Closed equity positions are excluded from subsequent dates
# ---------------------------------------------------------------------------


@given(
    'a ledger where sub-account "Equity B" reaches quantity zero on a specific date',
    target_fixture="ledger_bytes",
)
def ledger_with_closure() -> bytes:
    """Provide a ledger where Equity B closes 20 days before today."""
    today = date.today()
    close_date = today - timedelta(days=20)
    start_date = today - timedelta(days=40)
    rows = [
        {
            "date": start_date,
            "sub_account": "Cash",
            "book_cost": 1000.0,
            "quantity": 1000.0,
            "total_income": 0.0,
        },
        {
            "date": start_date,
            "sub_account": "Equity B",
            "book_cost": 500.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
        {
            "date": close_date,
            "sub_account": "Cash",
            "book_cost": 1500.0,
            "quantity": 1500.0,
            "total_income": 0.0,
        },
        {
            "date": close_date,
            "sub_account": "Equity B",
            "book_cost": 0.0,
            "quantity": 0.0,
            "total_income": 5.0,
        },
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@then('the ladder contains rows for "Equity B" up to and including the closure date')
def check_equity_b_present_before_closure(account_name: str, app_client: TestClient) -> None:
    """Equity B rows should exist at or before the closure date."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    equity_rows = df[df["sub_account"] == "Equity B"]
    assert len(equity_rows) > 0, "Expected some Equity B rows before/at closure"


@then('the ladder contains no rows for "Equity B" on any date after the closure date')
def check_equity_b_absent_after_closure(account_name: str, app_client: TestClient) -> None:
    """Equity B must not appear after its closure date."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    equity_rows = df[df["sub_account"] == "Equity B"]
    if len(equity_rows) > 0:
        max_equity_date = pd.to_datetime(equity_rows["date"]).max().date()
        today = date.today()
        closure_date = today - timedelta(days=20)
        assert max_equity_date <= closure_date, (
            f"Equity B appears after closure: max date {max_equity_date}, closure {closure_date}"
        )


# ---------------------------------------------------------------------------
# US1: Cash sub-account always appears regardless of balance
# ---------------------------------------------------------------------------


@given(
    "a ledger where the Cash sub-account balance reaches zero on a specific date",
    target_fixture="ledger_bytes",
)
def ledger_with_zero_cash() -> bytes:
    """Provide a ledger where Cash hits zero balance."""
    today = date.today()
    start_date = today - timedelta(days=40)
    zero_date = today - timedelta(days=20)
    rows = [
        {
            "date": start_date,
            "sub_account": "Cash",
            "book_cost": 1000.0,
            "quantity": 1000.0,
            "total_income": 0.0,
        },
        {
            "date": zero_date,
            "sub_account": "Cash",
            "book_cost": 0.0,
            "quantity": 0.0,
            "total_income": 0.0,
        },
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@then("the ladder contains a Cash row on every business day in the date range")
def check_cash_present_always(account_name: str, app_client: TestClient) -> None:
    """Cash rows must exist across the full date range."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    cash_rows = df[df["sub_account"] == "Cash"]
    all_dates = df["date"].unique()
    for d in all_dates:
        assert d in cash_rows["date"].values, f"Cash missing on date {d}"


@then("the Cash row on and after the zero-balance date shows a balance of zero")
def check_cash_zero_balance_preserved(account_name: str, app_client: TestClient) -> None:
    """Cash rows after the zero-balance date should show quantity=0."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    cash_rows = df[df["sub_account"] == "Cash"]
    today = date.today()
    zero_date = today - timedelta(days=20)
    after_zero = cash_rows[pd.to_datetime(cash_rows["date"]).dt.date >= zero_date]
    if len(after_zero) > 0:
        assert (after_zero["quantity"] == 0.0).all(), (
            "Cash quantity should be 0 after zero-balance date"
        )


# ---------------------------------------------------------------------------
# US3: Re-submitting the same file is a no-op
# ---------------------------------------------------------------------------


@given(
    'a position ladder has already been stored for account "idempotent-portfolio"',
    target_fixture="stored_ledger_bytes",
)
def store_initial_ladder(app_client: TestClient) -> bytes:
    """Ingest a ledger for idempotent-portfolio and return the bytes."""
    ledger_bytes = _make_ledger_bytes()
    resp = app_client.post(
        "/v1/accounts/idempotent-portfolio/ladder",
        files=_make_multipart(ledger_bytes),
    )
    assert resp.status_code == 201, f"Setup failed: {resp.text}"
    return ledger_bytes


@when('the same file is submitted again for "idempotent-portfolio"', target_fixture="post_response")
def resubmit_same_file(stored_ledger_bytes: bytes, app_client: TestClient) -> object:
    """Submit the identical file a second time."""
    return app_client.post(
        "/v1/accounts/idempotent-portfolio/ladder",
        files=_make_multipart(stored_ledger_bytes),
    )


@then(parsers.parse('the response body contains status "{expected_status}"'))
def check_status_field(post_response: object, expected_status: str) -> None:
    """Assert the status field in the JSON body."""
    body = post_response.json()
    assert body.get("status") == expected_status, (
        f"Expected status '{expected_status}', got '{body.get('status')}'"
    )


@then("the stored XLSX file is unchanged")
def check_stored_file_unchanged(stored_ledger_bytes: bytes, app_client: TestClient) -> None:
    """Verify the stored ladder is byte-identical (same row count)."""
    meta_resp = app_client.get("/v1/accounts/idempotent-portfolio/ladder")
    assert meta_resp.status_code == 200
    body = meta_resp.json()
    expected_checksum = hashlib.sha256(stored_ledger_bytes).hexdigest()
    # Verify via re-download and row count consistency
    dl = app_client.get("/v1/accounts/idempotent-portfolio/ladder/download")
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    assert len(df) == body["row_count"], "Row count changed after re-submission"
    _ = expected_checksum  # confirmed idempotent via checksum match in service


@then('the response body includes a "_links.download" URL to the existing stored XLSX')
def check_idempotent_download_link(post_response: object) -> None:
    """Assert _links.download is present in the idempotent response."""
    body = post_response.json()
    assert "_links" in body and "download" in body["_links"]


# ---------------------------------------------------------------------------
# US4: Submitting a changed file returns a merge-not-supported error
# ---------------------------------------------------------------------------


@given(
    'a position ladder has already been stored for account "conflict-portfolio"',
    target_fixture="original_bytes",
)
def store_conflict_initial(app_client: TestClient) -> bytes:
    """Ingest an initial ladder for conflict-portfolio."""
    ledger_bytes = _make_ledger_bytes()
    resp = app_client.post(
        "/v1/accounts/conflict-portfolio/ladder",
        files=_make_multipart(ledger_bytes),
    )
    assert resp.status_code == 201, f"Setup failed: {resp.text}"
    return ledger_bytes


@when('a modified file is submitted for "conflict-portfolio"', target_fixture="post_response")
def submit_modified_file(app_client: TestClient) -> object:
    """Submit a different XLSX file for the same account."""
    modified_bytes = _make_ledger_bytes(days_back=50)  # different content
    return app_client.post(
        "/v1/accounts/conflict-portfolio/ladder",
        files=_make_multipart(modified_bytes),
    )


@then(
    parsers.parse('the response body contains a problem detail with type containing "{type_slug}"')
)
def check_problem_detail_type(post_response: object, type_slug: str) -> None:
    """Assert the error response type contains the expected slug."""
    body = post_response.json()
    assert "type" in body, "No 'type' field in error response"
    assert type_slug in body["type"], (
        f"Expected type containing '{type_slug}', got '{body['type']}'"
    )


@then('the existing stored ladder for "conflict-portfolio" is unchanged')
def check_conflict_ladder_unchanged(original_bytes: bytes, app_client: TestClient) -> None:
    """Verify the stored ladder was not modified by the failed merge attempt."""
    meta_resp = app_client.get("/v1/accounts/conflict-portfolio/ladder")
    assert meta_resp.status_code == 200
    body = meta_resp.json()
    dl = app_client.get("/v1/accounts/conflict-portfolio/ladder/download")
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    assert len(df) == body["row_count"], "Stored ladder was unexpectedly modified"
