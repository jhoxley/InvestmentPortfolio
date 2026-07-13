"""BDD step implementations for retrieve_timeseries.feature (US1)."""

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("retrieve_timeseries.feature")


def _ladder_bytes(earliest: date) -> bytes:
    """Build a minimal valid sub-account ledger XLSX starting well in the past.

    Args:
        earliest: The earliest activity date to record.

    Returns:
        Raw XLSX bytes.
    """
    df = pd.DataFrame(
        {
            "date": [earliest, earliest],
            "sub_account": ["Cash", "Equity A"],
            "book_cost": [1000.0, 500.0],
            "quantity": [1000.0, 10.0],
            "total_income": [0.0, 0.0],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _capital_bytes() -> bytes:
    """Build a capital ledger XLSX with two recorded observations, both well in the past.

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


def _ingest_dual_resource_account(account_name: str, app_client: TestClient) -> None:
    """Ingest both a position ladder and a capital ledger for an account.

    Args:
        account_name: Target account name.
        app_client: Test client fixture.
    """
    ladder_resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ladder_bytes(date.today() - timedelta(days=365 * 5)),
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
    parsers.parse('account "{account_name}" has an ingested capital ledger and position ladder'),
    target_fixture="account_name",
)
def dual_resource_account(account_name: str, app_client: TestClient) -> str:
    """Ingest both resources for the given account."""
    _ingest_dual_resource_account(account_name, app_client)
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has a capital ledger whose latest recorded date is before today'
    ),
    target_fixture="account_name",
)
def account_with_stale_capital_ledger(account_name: str, app_client: TestClient) -> str:
    """Ingest both resources; the capital ledger fixture is always well in the past."""
    _ingest_dual_resource_account(account_name, app_client)
    return account_name


@given(
    parsers.parse('account "{account_name}" has an ingested position ladder but no capital ledger'),
    target_fixture="account_name",
)
def ladder_only_account(account_name: str, app_client: TestClient) -> str:
    """Ingest only a position ladder for the given account."""
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ladder_bytes(date.today() - timedelta(days=365 * 5)),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"
    return account_name


@given(parsers.parse('no ledger of any kind has been ingested for account "{account_name}"'))
def no_ledger_ingested(account_name: str) -> None:
    """No setup needed — a fresh tmp_path store is used."""


@when(
    parsers.parse('a request is made for attributes "{attr1}" and "{attr2}" from {start} to {end}'),
    target_fixture="ts_response",
)
def request_two_attributes_with_range(
    account_name: str, attr1: str, attr2: str, start: str, end: str, app_client: TestClient
) -> object:
    """GET the timeseries endpoint for two attributes and an explicit date range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[("attribute", attr1), ("attribute", attr2), ("start", start), ("end", end)],
    )


@when(
    parsers.parse(
        'a request is made for attribute "{attribute}" ending on the most recent business day'
    ),
    target_fixture="ts_response",
)
def request_attribute_default_end(
    account_name: str, attribute: str, app_client: TestClient
) -> object:
    """GET the timeseries endpoint for one attribute with no end (defaults to T-1)."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries", params=[("attribute", attribute)]
    )


@when(
    parsers.parse('a request is made for attribute "{attribute}"'),
    target_fixture="ts_response",
)
def request_single_attribute(account_name: str, attribute: str, app_client: TestClient) -> object:
    """GET the timeseries endpoint for a single attribute, no date range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries", params=[("attribute", attribute)]
    )


@when("a request is made with no attribute specified", target_fixture="ts_response")
def request_no_attribute(account_name: str, app_client: TestClient) -> object:
    """GET the timeseries endpoint with zero attribute params."""
    return app_client.get(f"/v1/accounts/{account_name}/timeseries")


@when(
    parsers.parse('a request is made for attribute "{attribute}" for account "{account_name}"'),
    target_fixture="ts_response",
)
def request_attribute_for_account(
    attribute: str, account_name: str, app_client: TestClient
) -> object:
    """GET the timeseries endpoint for an explicit account name (unknown-account case)."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries", params=[("attribute", attribute)]
    )


@when(
    parsers.parse("a request is made with start date {start} and end date {end}"),
    target_fixture="ts_response",
)
def request_with_explicit_start_end(
    account_name: str, start: str, end: str, app_client: TestClient
) -> object:
    """GET the timeseries endpoint with an explicit (invalid) start/end pair."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[("attribute", "capital"), ("start", start), ("end", end)],
    )


@when("a request is made with an end date after today", target_fixture="ts_response")
def request_with_future_end(account_name: str, app_client: TestClient) -> object:
    """GET the timeseries endpoint with an end date far in the future."""
    future = (date.today() + timedelta(days=30)).isoformat()
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[("attribute", "capital"), ("end", future)],
    )


@when("a request is made with a start date that falls on a Saturday", target_fixture="ts_response")
def request_with_saturday_start(account_name: str, app_client: TestClient) -> object:
    """GET the timeseries endpoint with an explicit Saturday start date."""
    return app_client.get(
        f"/v1/accounts/{account_name}/timeseries",
        params=[("attribute", "capital"), ("start", "2024-01-06")],
    )


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(ts_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert ts_response.status_code == status_code, (
        f"Expected {status_code}, got {ts_response.status_code}: {ts_response.text}"
    )


@then(parsers.parse("the response contains one entry per business day from {start} to {end}"))
def check_entry_count(ts_response: object, start: str, end: str) -> None:
    """Assert the entry count matches the number of business days in range."""
    expected = len(pd.bdate_range(start=start, end=end))
    entries = ts_response.json()["entries"]
    assert len(entries) == expected, f"Expected {expected} entries, got {len(entries)}"


@then(parsers.parse('every entry contains a "{attr1}" value and a "{attr2}" value'))
def check_entries_have_both_attributes(ts_response: object, attr1: str, attr2: str) -> None:
    """Assert every entry carries both requested attribute keys."""
    for entry in ts_response.json()["entries"]:
        assert attr1 in entry, f"'{attr1}' missing from entry: {entry}"
        assert attr2 in entry, f"'{attr2}' missing from entry: {entry}"


@then('the response body includes "_links.self", "_links.attributes", and "_links.accounts" URLs')
def check_links_present(ts_response: object) -> None:
    """Assert all three HATEOAS links are present on the main response."""
    links = ts_response.json()["_links"]
    assert "self" in links
    assert "attributes" in links
    assert "accounts" in links


@then("entries after the capital ledger's latest recorded date carry the last recorded value")
def check_forward_filled_value(ts_response: object) -> None:
    """Assert the most recent entries carry the latest recorded capital value (2000.0)."""
    entries = ts_response.json()["entries"]
    assert entries[-1]["capital"] == 2000.0


@then("the response identifies that the capital ledger source is missing for this account")
def check_missing_capital_source(ts_response: object) -> None:
    """Assert the problem detail names the missing capital_ledger source."""
    detail = ts_response.json()["detail"]
    assert "capital_ledger" in detail


@then("the first entry in the response is dated on or after the following Monday")
def check_first_entry_after_monday(ts_response: object) -> None:
    """Assert the first entry's date is on/after 2024-01-08 (the Monday after 2024-01-06)."""
    first_date = date.fromisoformat(ts_response.json()["entries"][0]["date"])
    assert first_date >= date(2024, 1, 8)
