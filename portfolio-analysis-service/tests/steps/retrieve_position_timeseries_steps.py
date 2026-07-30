"""BDD step implementations for retrieve_position_timeseries.feature (US1)."""

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("retrieve_position_timeseries.feature")


def _ledger_bytes(rows: list[dict]) -> bytes:
    """Build a raw sub-account ledger XLSX from explicit rows.

    Args:
        rows: List of dicts with keys date, sub_account, book_cost, quantity,
            total_income (feature 001's raw ledger schema).

    Returns:
        Raw XLSX bytes.
    """
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _ingest_ladder(account_name: str, rows: list[dict], app_client: TestClient) -> None:
    """POST a raw ledger to the /ladder endpoint for the given account.

    Args:
        account_name: Target account name.
        rows: Raw ledger rows (see _ledger_bytes).
        app_client: Test client fixture.
    """
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


def _ingest_capital_only(account_name: str, app_client: TestClient) -> None:
    """POST a raw capital ledger (no position ladder) for the given account.

    Args:
        account_name: Target account name.
        app_client: Test client fixture.
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
    resp = app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files={
            "file": (
                "capital.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Capital setup failed: {resp.text}"


def _held_row(earliest: date, sub_account: str, quantity: float = 10.0) -> dict:
    """Build a single buy-and-hold raw ledger row.

    Args:
        earliest: Activity date.
        sub_account: Position name.
        quantity: Quantity held from that date onward.

    Returns:
        Row dict matching the raw ledger schema.
    """
    return {
        "date": earliest,
        "sub_account": sub_account,
        "book_cost": quantity * 10.0,
        "quantity": quantity,
        "total_income": 0.0,
    }


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder containing positions '
        '"{pos1}" and "{pos2}"'
    ),
    target_fixture="account_name",
)
def two_positions_ladder(account_name: str, pos1: str, pos2: str, app_client: TestClient) -> str:
    """Ingest a ladger with two continuously-held positions, well in the past."""
    earliest = date.today() - timedelta(days=365 * 5)
    _ingest_ladder(account_name, [_held_row(earliest, pos1), _held_row(earliest, pos2)], app_client)
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder containing positions '
        '"{pos1}", "{pos2}", and "{pos3}"'
    ),
    target_fixture="account_name",
)
def three_positions_ladder(
    account_name: str, pos1: str, pos2: str, pos3: str, app_client: TestClient
) -> str:
    """Ingest a ladger with three continuously-held positions, recently opened."""
    earliest = date.today() - timedelta(days=30)
    _ingest_ladder(
        account_name,
        [_held_row(earliest, pos1), _held_row(earliest, pos2), _held_row(earliest, pos3)],
        app_client,
    )
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder containing position '
        '"{pos1}" but no position named "{missing}"'
    ),
    target_fixture="account_name",
)
def one_position_ladder_with_missing_name(
    account_name: str, pos1: str, missing: str, app_client: TestClient
) -> str:
    """Ingest a ladger with a single continuously-held position."""
    earliest = date.today() - timedelta(days=365 * 5)
    _ingest_ladder(account_name, [_held_row(earliest, pos1)], app_client)
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder containing position '
        '"{pos1}" but no position named "{m1}" or "{m2}"'
    ),
    target_fixture="account_name",
)
def one_position_ladder_with_two_missing_names(
    account_name: str, pos1: str, m1: str, m2: str, app_client: TestClient
) -> str:
    """Ingest a ladger with a single continuously-held position."""
    earliest = date.today() - timedelta(days=365 * 5)
    _ingest_ladder(account_name, [_held_row(earliest, pos1)], app_client)
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder containing position "{pos1}"'
    ),
    target_fixture="account_name",
)
def one_position_ladder(account_name: str, pos1: str, app_client: TestClient) -> str:
    """Ingest a ladger with a single continuously-held position."""
    earliest = date.today() - timedelta(days=365 * 5)
    _ingest_ladder(account_name, [_held_row(earliest, pos1)], app_client)
    return account_name


@given(
    parsers.parse('account "{account_name}" has an ingested position ladder'),
    target_fixture="account_name",
)
def generic_ladder(account_name: str, app_client: TestClient) -> str:
    """Ingest a minimal ladger — used by scenarios that only need account-level validity."""
    earliest = date.today() - timedelta(days=365 * 5)
    _ingest_ladder(account_name, [_held_row(earliest, "Cash")], app_client)
    return account_name


@given(
    parsers.parse('account "{account_name}" has an ingested capital ledger but no position ladder'),
    target_fixture="account_name",
)
def capital_only_account(account_name: str, app_client: TestClient) -> str:
    """Ingest a capital ledger only — no position ladder."""
    _ingest_capital_only(account_name, app_client)
    return account_name


@given(parsers.parse('no resource of any kind has been ingested for account "{account_name}"'))
def no_resource_ingested(account_name: str) -> None:
    """No setup needed — a fresh tmp_path store is used."""


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder in which position '
        '"{position}" was fully divested several business days before the ladder\'s own to_date'
    ),
    target_fixture="account_name",
)
def divested_position_ladder(account_name: str, position: str, app_client: TestClient) -> str:
    """Ingest a ladger where one position is bought, then fully divested well before to_date."""
    recent_bdays = pd.bdate_range(end=date.today(), periods=40)
    buy_date = recent_bdays[0].date()
    divest_date = recent_bdays[10].date()
    rows = [
        _held_row(buy_date, "Cash", quantity=1000.0),
        {
            "date": buy_date,
            "sub_account": position,
            "book_cost": 500.0,
            "quantity": 5.0,
            "total_income": 0.0,
        },
        {
            "date": divest_date,
            "sub_account": position,
            "book_cost": 500.0,
            "quantity": 0.0,
            "total_income": 0.0,
        },
    ]
    _ingest_ladder(account_name, rows, app_client)
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder in which position '
        '"{position}" is still held as of the ladder\'s own to_date'
    ),
    target_fixture="account_name",
)
def still_held_position_ladder(account_name: str, position: str, app_client: TestClient) -> str:
    """Ingest a ladger where one position is bought and never sold."""
    earliest = date.today() - timedelta(days=365 * 3)
    _ingest_ladder(
        account_name, [_held_row(earliest, "Cash"), _held_row(earliest, position)], app_client
    )
    return account_name


@when(
    parsers.parse(
        'a request is made for attributes "{attr1}" and "{attr2}", for positions "{pos1}" '
        'and "{pos2}", from {start} to {end}'
    ),
    target_fixture="ts_response",
)
def request_two_attributes_two_positions_with_range(
    account_name: str,
    attr1: str,
    attr2: str,
    pos1: str,
    pos2: str,
    start: str,
    end: str,
    app_client: TestClient,
) -> object:
    """GET the position endpoint for two attributes, two positions, and an explicit range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position",
        params=[
            ("attribute", attr1),
            ("attribute", attr2),
            ("position", pos1),
            ("position", pos2),
            ("start", start),
            ("end", end),
        ],
    )


@when(
    parsers.parse('a request is made for attribute "{attribute}" with no position names specified'),
    target_fixture="ts_response",
)
def request_attribute_no_positions(
    account_name: str, attribute: str, app_client: TestClient
) -> object:
    """GET the position endpoint for one attribute, no position filter."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position", params=[("attribute", attribute)]
    )


@when(
    parsers.parse(
        'a request is made for attribute "{attribute}" for positions "{pos1}" and "{pos2}"'
    ),
    target_fixture="ts_response",
)
def request_attribute_two_positions(
    account_name: str, attribute: str, pos1: str, pos2: str, app_client: TestClient
) -> object:
    """GET the position endpoint for one attribute and two named positions."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position",
        params=[("attribute", attribute), ("position", pos1), ("position", pos2)],
    )


@when(
    "a request is made with that position name percent-encoded in the query string",
    target_fixture="ts_response",
)
def request_with_percent_encoded_position(account_name: str, app_client: TestClient) -> object:
    """GET the position endpoint with a spaces/symbols position name.

    httpx/TestClient percent-encodes query parameter values automatically; passing the
    raw name here still exercises the server's decoding path end-to-end.
    """
    return app_client.get(
        f"/v1/accounts/{account_name}/position",
        params=[
            ("attribute", "market_value"),
            ("position", "Berkshire Hathaway Class B (BRK.B)"),
        ],
    )


@when(
    parsers.parse('a request is made for attribute "{attribute}"'),
    target_fixture="ts_response",
)
def request_single_attribute(account_name: str, attribute: str, app_client: TestClient) -> object:
    """GET the position endpoint for a single attribute, no position/date filters."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position", params=[("attribute", attribute)]
    )


@when(
    parsers.parse('a request is made for attribute "{attribute}" for account "{account_name}"'),
    target_fixture="ts_response",
)
def request_attribute_for_account(
    attribute: str, account_name: str, app_client: TestClient
) -> object:
    """GET the position endpoint for an explicit account name."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position", params=[("attribute", attribute)]
    )


@when(
    parsers.parse('a request is made for attribute "{attribute}" for positions "{m1}" and "{m2}"'),
    target_fixture="ts_response",
)
def request_attribute_two_unrecognised_positions(
    account_name: str, attribute: str, m1: str, m2: str, app_client: TestClient
) -> object:
    """GET the position endpoint requesting two unrecognised position names."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position",
        params=[("attribute", attribute), ("position", m1), ("position", m2)],
    )


@when("a request is made with no attribute specified", target_fixture="ts_response")
def request_no_attribute(account_name: str, app_client: TestClient) -> object:
    """GET the position endpoint with zero attribute params."""
    return app_client.get(f"/v1/accounts/{account_name}/position")


@when(
    parsers.parse(
        'a request is made for attribute "{attribute}" with start date {start} and end date {end}'
    ),
    target_fixture="ts_response",
)
def request_with_explicit_start_end(
    account_name: str, attribute: str, start: str, end: str, app_client: TestClient
) -> object:
    """GET the position endpoint with an explicit (invalid) start/end pair."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position",
        params=[("attribute", attribute), ("start", start), ("end", end)],
    )


@when(
    parsers.parse('a request is made for attribute "{attribute}" with an end date after today'),
    target_fixture="ts_response",
)
def request_with_future_end(account_name: str, attribute: str, app_client: TestClient) -> object:
    """GET the position endpoint with an end date far in the future."""
    future = (date.today() + timedelta(days=30)).isoformat()
    return app_client.get(
        f"/v1/accounts/{account_name}/position",
        params=[("attribute", attribute), ("end", future)],
    )


@when(
    parsers.parse(
        'a request is made for attribute "{attribute}" for position "{position}" ending '
        "on the most recent business day"
    ),
    target_fixture="ts_response",
)
def request_attribute_position_default_end(
    account_name: str, attribute: str, position: str, app_client: TestClient
) -> object:
    """GET the position endpoint for one position, no explicit start/end (defaults apply)."""
    return app_client.get(
        f"/v1/accounts/{account_name}/position",
        params=[("attribute", attribute), ("position", position)],
    )


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(ts_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert ts_response.status_code == status_code, (
        f"Expected {status_code}, got {ts_response.status_code}: {ts_response.text}"
    )


@then("the response contains one entry per business day per position in that range")
def check_entry_count_per_position(ts_response: object) -> None:
    """Assert entries cover every business day for every requested position."""
    body = ts_response.json()
    expected_days = len(pd.bdate_range(start=body["from_date"], end=body["to_date"]))
    expected = expected_days * len(body["positions"])
    assert len(body["entries"]) == expected, (
        f"Expected {expected} entries, got {len(body['entries'])}"
    )


@then(parsers.parse('every entry contains a "{attr1}" value and a "{attr2}" value'))
def check_entries_have_both_attributes(ts_response: object, attr1: str, attr2: str) -> None:
    """Assert every entry carries both requested attribute keys."""
    for entry in ts_response.json()["entries"]:
        assert attr1 in entry, f"'{attr1}' missing from entry: {entry}"
        assert attr2 in entry, f"'{attr2}' missing from entry: {entry}"


@then(
    'the response body includes "_links.self", "_links.positions", "_links.attributes", '
    'and "_links.accounts" URLs'
)
def check_links_present(ts_response: object) -> None:
    """Assert all four HATEOAS links are present on the main response."""
    links = ts_response.json()["_links"]
    assert "self" in links
    assert "positions" in links
    assert "attributes" in links
    assert "accounts" in links


@then('entries are present for all three positions, including "Cash"')
def check_three_positions_present(ts_response: object) -> None:
    """Assert all three positions, including Cash, appear in the response."""
    positions = {e["position"] for e in ts_response.json()["entries"]}
    assert "Cash" in positions
    assert len(positions) == 3


@then(parsers.parse('entries are present only for "{position}"'))
def check_entries_only_for_position(ts_response: object, position: str) -> None:
    """Assert every entry belongs to the given position, and it appears at least once."""
    positions = {e["position"] for e in ts_response.json()["entries"]}
    assert positions == {position}


@then(parsers.parse('no error is returned on account of "{position}"'))
def check_no_error_for_position(ts_response: object, position: str) -> None:
    """Assert the response is a normal 200 success (no problem-detail body)."""
    assert ts_response.status_code == 200
    assert "detail" not in ts_response.json()


@then(parsers.parse('entries are present for "{position}"'))
def check_entries_present_for_position(ts_response: object, position: str) -> None:
    """Assert at least one entry exists for the given position."""
    positions = {e["position"] for e in ts_response.json()["entries"]}
    assert position in positions


@then(
    parsers.parse(
        'the response identifies "{attribute}" as an unsupported attribute for this endpoint'
    )
)
def check_unsupported_attribute_detail(ts_response: object, attribute: str) -> None:
    """Assert the problem detail names the unsupported attribute."""
    detail = ts_response.json()["detail"]
    assert attribute in detail


@then("the response identifies the position ladder as the missing required source")
def check_missing_position_ladder_source(ts_response: object) -> None:
    """Assert the problem detail names the missing position ladder."""
    detail = ts_response.json()["detail"].lower()
    assert "position ladder" in detail


@then("the response contains zero entries")
def check_zero_entries(ts_response: object) -> None:
    """Assert the response succeeded with an empty entries list."""
    assert ts_response.json()["entries"] == []


@then(parsers.parse('"{position}" has no entries after its own last recorded (divestment) date'))
def check_no_entries_after_divestment(ts_response: object, position: str) -> None:
    """Assert the position's last entry date is strictly before the response's to_date."""
    body = ts_response.json()
    dates = [e["date"] for e in body["entries"] if e["position"] == position]
    assert dates, f"Expected at least one entry for {position}"
    assert max(dates) < body["to_date"], (
        f"{position}'s last entry {max(dates)} should be before to_date {body['to_date']}"
    )


@then(
    parsers.parse(
        '"{position}" has entries through the resolved end date, with every entry after '
        "its last ingested date carrying the same forward-filled market_value"
    )
)
def check_forward_filled_through_resolved_end(ts_response: object, position: str) -> None:
    """Assert the position's last entry lands exactly on the response's to_date."""
    body = ts_response.json()
    entries = sorted(
        (e for e in body["entries"] if e["position"] == position), key=lambda e: e["date"]
    )
    assert entries, f"Expected at least one entry for {position}"
    assert entries[-1]["date"] == body["to_date"]
    values = {e["market_value"] for e in entries}
    assert len(values) == 1, f"Expected a single constant forward-filled value, got {values}"
