"""BDD step implementations for validation.feature (edge cases and error paths)."""

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("validation.feature")


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    """Serialise a DataFrame to XLSX bytes.

    Args:
        df: DataFrame to serialise.

    Returns:
        XLSX file contents as bytes.
    """
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _multipart(
    file_bytes: bytes,
    filename: str = "ledger.xlsx",
    mime: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
) -> dict[str, tuple[str, bytes, str]]:
    """Build a multipart file dict for TestClient.

    Args:
        file_bytes: File content.
        filename: Filename to report.
        mime: MIME type to report.

    Returns:
        Dict for use as files= argument.
    """
    return {"file": (filename, file_bytes, mime)}


def _valid_df() -> pd.DataFrame:
    """Return a minimal valid ledger DataFrame.

    Returns:
        DataFrame with all required columns and valid data.
    """
    d1 = date(2020, 1, 2)
    return pd.DataFrame(
        {
            "date": [d1],
            "sub_account": ["Cash"],
            "book_cost": [100.0],
            "quantity": [100.0],
            "total_income": [0.0],
        }
    )


# ---------------------------------------------------------------------------
# Account name validation
# ---------------------------------------------------------------------------


@when(
    parsers.parse('a POST is made with account name "{account_name}"'),
    target_fixture="val_response",
)
def post_bad_account_name(account_name: str, app_client: TestClient) -> object:
    """POST to an endpoint with an invalid account name."""
    file_bytes = _xlsx_bytes(_valid_df())
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_multipart(file_bytes),
    )


@then(parsers.parse("the validation response status is {status_code:d}"))
def check_val_status(val_response: object, status_code: int) -> None:
    """Assert the validation response HTTP status code."""
    assert val_response.status_code == status_code, (
        f"Expected {status_code}, got {val_response.status_code}: {val_response.text}"
    )


@then(parsers.parse('the response is a problem detail with type "{type_slug}"'))
def check_problem_type(val_response: object, type_slug: str) -> None:
    """Assert the RFC 7807 type field contains the expected slug."""
    body = val_response.json()
    assert "type" in body, f"No 'type' in response: {body}"
    assert type_slug in body["type"], (
        f"Expected type containing '{type_slug}', got '{body['type']}'"
    )


# ---------------------------------------------------------------------------
# File format validation
# ---------------------------------------------------------------------------


@when(
    parsers.parse('a non-XLSX file is uploaded for account "{account_name}"'),
    target_fixture="val_response",
)
def upload_non_xlsx(account_name: str, app_client: TestClient) -> object:
    """Upload a CSV-disguised-as-xlsx file."""
    csv_bytes = b"date,sub_account,book_cost,quantity,total_income\n2020-01-02,Cash,100,100,0"
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={"file": ("ledger.csv", csv_bytes, "text/csv")},
    )


@when(
    parsers.parse('an XLSX missing the "{column}" column is uploaded for account "{account_name}"'),
    target_fixture="val_response",
)
def upload_missing_column(column: str, account_name: str, app_client: TestClient) -> object:
    """Upload an XLSX that is missing the specified column."""
    df = _valid_df().drop(columns=[column])
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_multipart(_xlsx_bytes(df)),
    )


@when(
    parsers.parse(
        'an XLSX with a non-numeric "{column}" value is uploaded for account "{account_name}"'
    ),
    target_fixture="val_response",
)
def upload_non_numeric(column: str, account_name: str, app_client: TestClient) -> object:
    """Upload an XLSX with a non-numeric value in the specified column."""
    df = _valid_df()
    df[column] = "not-a-number"
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_multipart(_xlsx_bytes(df)),
    )


@when(
    parsers.parse('an XLSX with an unparseable date is uploaded for account "{account_name}"'),
    target_fixture="val_response",
)
def upload_bad_date(account_name: str, app_client: TestClient) -> object:
    """Upload an XLSX where the date column contains a non-date string."""
    df = _valid_df()
    df["date"] = "not-a-date"
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_multipart(_xlsx_bytes(df)),
    )


@when(
    parsers.parse('an XLSX with no data rows is uploaded for account "{account_name}"'),
    target_fixture="val_response",
)
def upload_empty_xlsx(account_name: str, app_client: TestClient) -> object:
    """Upload an XLSX that has headers but no data rows."""
    df = pd.DataFrame(columns=["date", "sub_account", "book_cost", "quantity", "total_income"])
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_multipart(_xlsx_bytes(df)),
    )


@when(
    parsers.parse('an XLSX whose earliest date is today is uploaded for account "{account_name}"'),
    target_fixture="val_response",
)
def upload_today_date(account_name: str, app_client: TestClient) -> object:
    """Upload an XLSX whose only date is today, inside the T-2 boundary."""
    df = _valid_df()
    df["date"] = date.today()
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_multipart(_xlsx_bytes(df)),
    )


# ---------------------------------------------------------------------------
# Capital ledger endpoint validation
# ---------------------------------------------------------------------------


def _valid_capital_df() -> pd.DataFrame:
    """Return a minimal valid capital ledger DataFrame.

    Returns:
        DataFrame with all required columns and valid data, spanning two weekdays.
    """
    return pd.DataFrame(
        {
            "date": [date(2020, 1, 2), date(2020, 1, 10)],
            "capital": [1000.0, 1200.0],
            "income": [0.0, 5.0],
            "book_value": [0.0, 900.0],
        }
    )


@when(
    parsers.parse('a capital POST is made with account name "{account_name}"'),
    target_fixture="val_response",
)
def post_bad_capital_account_name(account_name: str, app_client: TestClient) -> object:
    """POST to the capital endpoint with an invalid account name."""
    file_bytes = _xlsx_bytes(_valid_capital_df())
    return app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files=_multipart(file_bytes),
    )


@when(
    parsers.parse(
        'a non-XLSX file is uploaded for the capital endpoint for account "{account_name}"'
    ),
    target_fixture="val_response",
)
def upload_non_xlsx_capital(account_name: str, app_client: TestClient) -> object:
    """Upload a CSV-disguised-as-xlsx file to the capital endpoint."""
    csv_bytes = b"date,capital,income,book_value\n2020-01-02,1000,0,0"
    return app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files={"file": ("capital.csv", csv_bytes, "text/csv")},
    )


@when(
    parsers.parse(
        'a capital XLSX missing the "{column}" column is uploaded for account "{account_name}"'
    ),
    target_fixture="val_response",
)
def upload_missing_capital_column(column: str, account_name: str, app_client: TestClient) -> object:
    """Upload a capital XLSX that is missing the specified column."""
    df = _valid_capital_df().drop(columns=[column])
    return app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files=_multipart(_xlsx_bytes(df)),
    )


@when(
    parsers.parse(
        'a capital XLSX with a non-numeric "{column}" value is uploaded for account "{account_name}"'
    ),
    target_fixture="val_response",
)
def upload_non_numeric_capital(column: str, account_name: str, app_client: TestClient) -> object:
    """Upload a capital XLSX with a non-numeric value in the specified column."""
    df = _valid_capital_df()
    df[column] = "not-a-number"
    return app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files=_multipart(_xlsx_bytes(df)),
    )


@when(
    parsers.parse(
        "a capital XLSX whose only recorded date is a Saturday is uploaded for account "
        '"{account_name}"'
    ),
    target_fixture="val_response",
)
def upload_capital_saturday_only(account_name: str, app_client: TestClient) -> object:
    """Upload a capital XLSX whose only recorded date falls on a weekend."""
    df = pd.DataFrame(
        {
            "date": [date(2024, 1, 6)],  # Saturday
            "capital": [1000.0],
            "income": [0.0],
            "book_value": [0.0],
        }
    )
    return app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files=_multipart(_xlsx_bytes(df)),
    )


# ---------------------------------------------------------------------------
# Timeseries endpoint edge cases
# ---------------------------------------------------------------------------


def _val_ledger_bytes(earliest: date) -> bytes:
    """Build a minimal valid sub-account ledger XLSX starting well in the past.

    Args:
        earliest: The earliest activity date to record.

    Returns:
        Raw XLSX bytes.
    """
    df = pd.DataFrame(
        {
            "date": [earliest],
            "sub_account": ["Cash"],
            "book_cost": [1000.0],
            "quantity": [1000.0],
            "total_income": [0.0],
        }
    )
    return _xlsx_bytes(df)


def _val_capital_bytes() -> bytes:
    """Build a minimal valid capital ledger XLSX with a single recorded observation.

    Returns:
        Raw XLSX bytes.
    """
    return _xlsx_bytes(
        pd.DataFrame(
            {
                "date": [date(2020, 1, 2)],
                "capital": [1000.0],
                "income": [0.0],
                "book_value": [900.0],
            }
        )
    )


@given(parsers.parse('account "{account_name}" has only a position ladder ingested for validation'))
def val_ladder_only_account(account_name: str, app_client: TestClient) -> None:
    """Ingest only a position ladder for the given account."""
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_multipart(_val_ledger_bytes(date.today() - timedelta(days=365 * 5))),
    )
    assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"


@given(parsers.parse('account "{account_name}" has an ingested capital ledger for validation'))
def val_capital_only_account(account_name: str, app_client: TestClient) -> None:
    """Ingest only a capital ledger for the given account."""
    resp = app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files=_multipart(_val_capital_bytes()),
    )
    assert resp.status_code == 201, f"Capital setup failed: {resp.text}"


@when(
    parsers.parse(
        'a timeseries request is made for attribute "{attribute}" for account "{account_name}"'
    ),
    target_fixture="val_response",
)
def request_timeseries_attribute(
    attribute: str, account_name: str, app_client: TestClient
) -> object:
    """GET the timeseries endpoint for a single attribute, no date range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries", params=[("attribute", attribute)]
    )


@when(
    parsers.parse(
        'a timeseries request is made for attribute "{attribute}" with start "{start}" and '
        'end "{end}" for account "{account_name}"'
    ),
    target_fixture="val_response",
)
def request_timeseries_attribute_with_start_end(
    attribute: str, start: str, end: str, account_name: str, app_client: TestClient
) -> object:
    """GET the timeseries endpoint for a single attribute with an explicit start/end date."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[("attribute", attribute), ("start", start), ("end", end)],
    )


@when(
    parsers.parse(
        'a timeseries request is made for attribute "{attribute}" starting "{start}" '
        'for account "{account_name}"'
    ),
    target_fixture="val_response",
)
def request_timeseries_attribute_with_start(
    attribute: str, start: str, account_name: str, app_client: TestClient
) -> object:
    """GET the timeseries endpoint for a single attribute with an explicit start date."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[("attribute", attribute), ("start", start)],
    )


@then(parsers.parse("the timeseries response contains exactly {count:d} entry"))
@then(parsers.parse("the timeseries response contains exactly {count:d} entries"))
def check_timeseries_entry_count(val_response: object, count: int) -> None:
    """Assert the timeseries response contains exactly the given number of entries."""
    entries = val_response.json()["entries"]
    assert len(entries) == count, f"Expected {count} entries, got {len(entries)}"
