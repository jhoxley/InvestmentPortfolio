"""BDD step implementations for retrieve_projection.feature (US1, US2, US3)."""

import io
from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("retrieve_projection.feature")

_LONG_HISTORY_START = date(2016, 1, 2)


def _ledger_bytes(rows: list[dict]) -> bytes:
    """Build a raw sub-account ledger XLSX from explicit rows.

    Args:
        rows: List of dicts matching the raw ledger schema.

    Returns:
        Raw XLSX bytes.
    """
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _held_row(earliest: date, sub_account: str = "Cash", quantity: float = 10.0) -> dict:
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


def _ingest_ladder(account_name: str, rows: list[dict], app_client: TestClient) -> None:
    """POST a raw ledger to the /ladder endpoint for the given account.

    Args:
        account_name: Target account name.
        rows: Raw ledger rows (see _held_row).
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
    assert resp.status_code == 201, f"Capital ledger setup failed: {resp.text}"


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder spanning 2016-01-02 '
        "through today"
    ),
    target_fixture="account_name",
)
def long_history_account(account_name: str, app_client: TestClient) -> str:
    """Ingest a ladger starting 2016-01-02 (expansion naturally runs through ~today)."""
    _ingest_ladder(account_name, [_held_row(_LONG_HISTORY_START)], app_client)
    return account_name


@given(
    parsers.parse('account "{account_name}" has an ingested position ladder starting 6 months ago'),
    target_fixture="account_name",
)
def short_history_account(account_name: str, app_client: TestClient) -> str:
    """Ingest a ladger starting six months ago — not enough for a computable 5Y measure."""
    earliest = date.today() - timedelta(days=182)
    _ingest_ladder(account_name, [_held_row(earliest)], app_client)
    return account_name


@given(
    parsers.parse('account "{account_name}" has an ingested capital ledger but no position ladder'),
    target_fixture="account_name",
)
def capital_only_account(account_name: str, app_client: TestClient) -> str:
    """Ingest a capital ledger only — no position ladder."""
    _ingest_capital_only(account_name, app_client)
    return account_name


@given(
    parsers.parse('no resource of any kind has been ingested for account "{account_name}"'),
    target_fixture="account_name",
)
def no_resource_ingested(account_name: str) -> str:
    """No setup needed — a fresh tmp_path store is used."""
    return account_name


def _resolve_date_phrase(phrase: str) -> str | None:
    """Resolve a feature-file date phrase into an ISO date string, or None.

    Args:
        phrase: One of "no start"/"no return" (-> None), an explicit ISO date, or
            "N years from today"/"N months ago".

    Returns:
        ISO date string, or None if the phrase means "omit this parameter".
    """
    if phrase in ("no start", "no return"):
        return None
    if phrase.endswith("years from today"):
        years = int(phrase.split()[0])
        today = date.today()
        try:
            return today.replace(year=today.year + years).isoformat()
        except ValueError:
            return today.replace(year=today.year + years, day=28).isoformat()
    return phrase


@when(
    parsers.parse(
        "a projection request is made with start {start}, projection_date {projection_date}, "
        'and return "{return_name}"'
    ),
    target_fixture="projection_response",
)
def request_with_start_and_one_return(
    account_name: str, start: str, projection_date: str, return_name: str, app_client: TestClient
) -> object:
    """GET the projection endpoint with an explicit start, projection_date, and one return."""
    return app_client.get(
        f"/v1/accounts/{account_name}/projection",
        params=[
            ("start", start),
            ("projection_date", projection_date),
            ("return", return_name),
        ],
    )


@when(
    parsers.parse(
        "a projection request is made with start {start}, projection_date {projection_date}, "
        "and no return"
    ),
    target_fixture="projection_response",
)
def request_with_start_and_no_return(
    account_name: str, start: str, projection_date: str, app_client: TestClient
) -> object:
    """GET the projection endpoint with an explicit start/projection_date and zero returns."""
    return app_client.get(
        f"/v1/accounts/{account_name}/projection",
        params=[("start", start), ("projection_date", projection_date)],
    )


@when(
    parsers.parse(
        "a projection request is made with start {start}, projection_date {projection_date}, "
        'and returns "{return1}" and "{return2}"'
    ),
    target_fixture="projection_response",
)
def request_with_start_and_two_returns(
    account_name: str,
    start: str,
    projection_date: str,
    return1: str,
    return2: str,
    app_client: TestClient,
) -> object:
    """GET the projection endpoint with an explicit start/projection_date and two returns."""
    return app_client.get(
        f"/v1/accounts/{account_name}/projection",
        params=[
            ("start", start),
            ("projection_date", projection_date),
            ("return", return1),
            ("return", return2),
        ],
    )


@when(
    parsers.parse(
        "a projection request is made with no start, a projection_date {years_phrase}, "
        'and returns "{return1}" and "{return2}"'
    ),
    target_fixture="projection_response",
)
def request_no_start_two_returns(
    account_name: str, years_phrase: str, return1: str, return2: str, app_client: TestClient
) -> object:
    """GET the projection endpoint with no start, a relative projection_date, two returns."""
    projection_date = _resolve_date_phrase(years_phrase)
    return app_client.get(
        f"/v1/accounts/{account_name}/projection",
        params=[
            ("projection_date", projection_date),
            ("return", return1),
            ("return", return2),
        ],
    )


@when(
    parsers.parse(
        "a projection request is made with no start, a projection_date {years_phrase}, "
        "and no return"
    ),
    target_fixture="projection_response",
)
def request_no_start_no_return(
    account_name: str, years_phrase: str, app_client: TestClient
) -> object:
    """GET the projection endpoint with no start, a relative projection_date, zero returns."""
    projection_date = _resolve_date_phrase(years_phrase)
    return app_client.get(
        f"/v1/accounts/{account_name}/projection",
        params=[("projection_date", projection_date)],
    )


@when(
    parsers.parse(
        "a projection request is made with no start, a projection_date {years_phrase}, "
        'and return "{return_name}"'
    ),
    target_fixture="projection_response",
)
def request_no_start_one_return(
    account_name: str, years_phrase: str, return_name: str, app_client: TestClient
) -> object:
    """GET the projection endpoint with no start, a relative projection_date, one return."""
    projection_date = _resolve_date_phrase(years_phrase)
    return app_client.get(
        f"/v1/accounts/{account_name}/projection",
        params=[("projection_date", projection_date), ("return", return_name)],
    )


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(projection_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert projection_response.status_code == status_code, (
        f"Expected {status_code}, got {projection_response.status_code}: "
        f"{projection_response.text}"
    )


@then(parsers.parse('the problem detail type ends with "{slug}"'))
def check_problem_type_slug(projection_response: object, slug: str) -> None:
    """Assert the RFC 7807 problem detail's type URI ends with the given slug."""
    assert projection_response.json()["type"].endswith(slug)


@then(parsers.parse('the projection response\'s positions are "{pos1}" and "{pos2}"'))
def check_positions_two(projection_response: object, pos1: str, pos2: str) -> None:
    """Assert the response's positions list contains exactly these two labels."""
    assert set(projection_response.json()["positions"]) == {pos1, pos2}


@then(parsers.parse('the projection response\'s positions are "{pos1}", "{pos2}", and "{pos3}"'))
def check_positions_three(projection_response: object, pos1: str, pos2: str, pos3: str) -> None:
    """Assert the response's positions list contains exactly these three labels."""
    assert set(projection_response.json()["positions"]) == {pos1, pos2, pos3}


@then(parsers.parse('the projection response\'s positions are "{pos1}"'))
def check_positions_one(projection_response: object, pos1: str) -> None:
    """Assert the response's positions list contains exactly this one label."""
    assert projection_response.json()["positions"] == [pos1]


@then(parsers.parse('the projection response\'s positions do not include "{pos}"'))
def check_position_absent(projection_response: object, pos: str) -> None:
    """Assert a series label is absent from the response's positions list."""
    assert pos not in projection_response.json()["positions"]


@then(parsers.parse('the "{label}" series\' final entry date is {expected_date}'))
def check_series_final_date(projection_response: object, label: str, expected_date: str) -> None:
    """Assert a labeled series' latest-dated entry falls on the given date."""
    entries = [e for e in projection_response.json()["entries"] if e["position"] == label]
    assert entries, f"No entries for series '{label}'"
    assert max(e["date"] for e in entries) == expected_date


@then(parsers.parse('the "{label}" series spans {start} through {end}'))
def check_series_spans(projection_response: object, label: str, start: str, end: str) -> None:
    """Assert a labeled series' entries run from start through end (inclusive)."""
    entries = [e for e in projection_response.json()["entries"] if e["position"] == label]
    assert entries, f"No entries for series '{label}'"
    dates = [e["date"] for e in entries]
    assert min(dates) == start
    assert max(dates) == end


@then(
    parsers.parse(
        'the "{label}" series\' first entry\'s market_value equals the "Historical" series\' '
        "final entry's market_value"
    )
)
def check_projected_starts_at_historical_final(projection_response: object, label: str) -> None:
    """Assert a projected series' first market_value equals the historical series' last."""
    body = projection_response.json()
    historical = sorted(
        (e for e in body["entries"] if e["position"] == "Historical"), key=lambda e: e["date"]
    )
    projected = sorted(
        (e for e in body["entries"] if e["position"] == label), key=lambda e: e["date"]
    )
    assert historical[-1]["market_value"] == pytest.approx(projected[0]["market_value"])


@then('the "1Y" and "3Y" series\' first entries share the same market_value')
def check_1y_3y_share_first_value(projection_response: object) -> None:
    """Assert the 1Y and 3Y series' earliest entries carry the same market_value."""
    body = projection_response.json()
    one_y = sorted(
        (e for e in body["entries"] if e["position"] == "1Y"), key=lambda e: e["date"]
    )
    three_y = sorted(
        (e for e in body["entries"] if e["position"] == "3Y"), key=lambda e: e["date"]
    )
    assert one_y[0]["market_value"] == pytest.approx(three_y[0]["market_value"])


@then(
    "every \"3Y\" entry's market_value matches the compounding formula using the account's own "
    "3Y return on 2024-01-02"
)
def check_3y_compounding_formula(
    projection_response: object, account_name: str, app_client: TestClient
) -> None:
    """Cross-check each 3Y entry against the compounding formula.

    Uses the account's own real 3Y performance measure as the oracle for r — no
    hand-picked fixture value needed.
    """
    perf_resp = app_client.get(
        f"/v1/accounts/{account_name}/performance",
        params=[("attribute", "3Y"), ("start", "2024-01-02"), ("end", "2024-01-02")],
    )
    assert perf_resp.status_code == 200, perf_resp.text
    r = perf_resp.json()["entries"][0]["3Y"]
    daily_rate = (1 + r) ** (1 / 260) - 1

    body = projection_response.json()
    historical_final = next(
        e
        for e in body["entries"]
        if e["position"] == "Historical" and e["date"] == "2024-01-02"
    )
    v0 = historical_final["market_value"]
    projected = sorted(
        (e for e in body["entries"] if e["position"] == "3Y"), key=lambda e: e["date"]
    )
    for t, entry in enumerate(projected):
        expected = v0 * (1 + daily_rate) ** t
        assert entry["market_value"] == pytest.approx(expected)


@then("the \"Historical\" series' final entry date equals the account's own most recently recorded date")
def check_historical_final_matches_account_latest(
    projection_response: object, account_name: str, app_client: TestClient
) -> None:
    """Assert the historical series' last date equals the account's own ladder to_date."""
    accounts_resp = app_client.get("/v1/accounts")
    assert accounts_resp.status_code == 200, accounts_resp.text
    account = next(
        a for a in accounts_resp.json()["accounts"] if a["account_name"] == account_name
    )
    expected_to_date = account["position_ladder"]["to_date"]

    entries = [e for e in projection_response.json()["entries"] if e["position"] == "Historical"]
    assert max(e["date"] for e in entries) == expected_to_date
