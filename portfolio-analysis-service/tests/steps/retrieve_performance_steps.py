"""BDD step implementations for retrieve_performance.feature (US1, US2, US3)."""

import io
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("retrieve_performance.feature")

LONG_HISTORY_START = date(2020, 1, 2)


@pytest.fixture()
def perf_responses() -> list[object]:
    """Accumulate multiple performance-endpoint responses within a single scenario.

    Returns:
        An empty list, mutated in place by request steps issued multiple times.
    """
    return []


def _ladder_bytes(earliest: date) -> bytes:
    """Build a minimal valid sub-account ledger XLSX starting on the given date.

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


def _download_ladder(account_name: str, app_client: TestClient) -> pd.DataFrame:
    """Download and parse the stored ladder for an account.

    Args:
        account_name: The account identifier.
        app_client: Test client fixture.

    Returns:
        Parsed ladder DataFrame.
    """
    resp = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    assert resp.status_code == 200, f"Download failed: {resp.text}"
    df = pd.read_excel(io.BytesIO(resp.content), engine="openpyxl")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder spanning 2020-01-02 '
        "through 2025-06-02"
    ),
    target_fixture="account_name",
)
def long_history_account(account_name: str, app_client: TestClient) -> str:
    """Ingest a ladger starting 2020-01-02 (expansion naturally runs through ~today)."""
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ladder_bytes(LONG_HISTORY_START),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"
    return account_name


@when(
    parsers.parse(
        'a performance request is made for attributes "{attr1}" and "{attr2}" from {start} to {end}'
    ),
    target_fixture="perf_response",
)
def request_two_attributes_with_range(
    account_name: str, attr1: str, attr2: str, start: str, end: str, app_client: TestClient
) -> object:
    """GET the performance endpoint for two attributes and an explicit date range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/performance",
        params=[("attribute", attr1), ("attribute", attr2), ("start", start), ("end", end)],
    )


@when(
    parsers.parse(
        'a performance request is made for attribute "{attribute}" with no start or end date'
    ),
    target_fixture="perf_response",
)
def request_single_attribute_no_dates(
    account_name: str, attribute: str, app_client: TestClient
) -> object:
    """GET the performance endpoint for a single attribute, no date range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/performance", params=[("attribute", attribute)]
    )


@when(
    parsers.parse(
        'a performance request is made for attributes "ITD", "ITD (Ann.)", "1Y", "3Y", '
        'and "5Y" on the account\'s most recent date'
    ),
    target_fixture="perf_response",
)
def request_all_five_attributes(account_name: str, app_client: TestClient) -> object:
    """GET the performance endpoint for all five measures with no explicit date range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/performance",
        params=[
            ("attribute", "ITD"),
            ("attribute", "ITD (Ann.)"),
            ("attribute", "1Y"),
            ("attribute", "3Y"),
            ("attribute", "5Y"),
        ],
    )


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(perf_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert perf_response.status_code == status_code, (
        f"Expected {status_code}, got {perf_response.status_code}: {perf_response.text}"
    )


@then(parsers.parse('the performance response has account_name "{account_name}"'))
def check_account_name(perf_response: object, account_name: str) -> None:
    """Assert the response's account_name field."""
    assert perf_response.json()["account_name"] == account_name


@then(parsers.parse('the performance response has attributes "{attr1}" and "{attr2}"'))
def check_attributes_list(perf_response: object, attr1: str, attr2: str) -> None:
    """Assert the response's attributes list, in request order."""
    assert perf_response.json()["attributes"] == [attr1, attr2]


@then(parsers.parse("the performance response has from_date {from_date} and to_date {to_date}"))
def check_from_to_date(perf_response: object, from_date: str, to_date: str) -> None:
    """Assert the response's resolved from_date/to_date."""
    body = perf_response.json()
    assert body["from_date"] == from_date
    assert body["to_date"] == to_date


@then(
    parsers.parse(
        "the performance response contains one entry per business day from {start} to {end}"
    )
)
def check_entry_count(perf_response: object, start: str, end: str) -> None:
    """Assert the entry count matches the number of business days in range."""
    expected = len(pd.bdate_range(start=start, end=end))
    entries = perf_response.json()["entries"]
    assert len(entries) == expected, f"Expected {expected} entries, got {len(entries)}"


@then(
    parsers.parse(
        'every performance entry contains a numeric "{attr1}" value and a numeric "{attr2}" value'
    )
)
def check_entries_have_both_attributes(perf_response: object, attr1: str, attr2: str) -> None:
    """Assert every entry carries both requested measure keys, both numeric."""
    for entry in perf_response.json()["entries"]:
        assert attr1 in entry, f"'{attr1}' missing from entry: {entry}"
        assert attr2 in entry, f"'{attr2}' missing from entry: {entry}"
        assert isinstance(entry[attr1], int | float)
        assert isinstance(entry[attr2], int | float)


@then(
    'the performance response body includes "_links.self", "_links.attributes", and '
    '"_links.accounts" URLs'
)
def check_links_present(perf_response: object) -> None:
    """Assert all three HATEOAS links are present on the response."""
    links = perf_response.json()["_links"]
    assert "self" in links
    assert "attributes" in links
    assert "accounts" in links


@then("the performance response's from_date equals the ladder's earliest recorded date")
def check_from_date_defaults_to_earliest(perf_response: object) -> None:
    """Assert from_date defaults to the ladder's earliest recorded date."""
    assert perf_response.json()["from_date"] == LONG_HISTORY_START.isoformat()


@then("the performance response's to_date is the business day before today")
def check_to_date_defaults_to_business_day_before_today(perf_response: object) -> None:
    """Assert to_date defaults to the business day strictly before today."""
    expected = pd.bdate_range(end=date.today(), periods=2)[0].date()
    assert perf_response.json()["to_date"] == expected.isoformat()


@then('every one of "ITD", "ITD (Ann.)", "1Y", "3Y", and "5Y" is present and numeric on that entry')
def check_all_five_measures_present(perf_response: object) -> None:
    """Assert the most recent entry carries all five measures, all numeric."""
    entries = perf_response.json()["entries"]
    last_entry = entries[-1]
    for name in ("ITD", "ITD (Ann.)", "1Y", "3Y", "5Y"):
        assert name in last_entry, f"'{name}' missing from most recent entry: {last_entry}"
        assert isinstance(last_entry[name], int | float)


@given(
    parsers.parse(
        'account "{account_name}" has an ingested position ladder with two sub-accounts '
        "starting 2020-01-02"
    ),
    target_fixture="account_name",
)
def two_sub_account_ladder(account_name: str, app_client: TestClient) -> str:
    """Ingest a ladger with two sub-accounts (Cash, Equity A) starting 2020-01-02."""
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={
            "file": (
                "ledger.xlsx",
                _ladder_bytes(LONG_HISTORY_START),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"
    return account_name


@when(
    parsers.parse(
        'a performance request is made for attribute "{attribute}" for that account\'s first '
        "ingested date"
    ),
    target_fixture="perf_response",
)
def request_attribute_for_first_ingested_date(
    account_name: str, attribute: str, app_client: TestClient
) -> object:
    """GET the performance endpoint for a single date: the account's first ingested date."""
    first_date = LONG_HISTORY_START.isoformat()
    return app_client.get(
        f"/v1/accounts/{account_name}/performance",
        params=[("attribute", attribute), ("start", first_date), ("end", first_date)],
    )


@then(
    "the entry's \"ITD\" value equals the downloaded ladder's summed weighted_position_return "
    "for that date"
)
def check_itd_matches_summed_weighted_return(
    perf_response: object, account_name: str, app_client: TestClient
) -> None:
    """Assert the single entry's ITD equals the ladder's own summed weighted_position_return."""
    ladder_df = _download_ladder(account_name, app_client)
    expected = ladder_df[ladder_df["date"] == LONG_HISTORY_START]["weighted_position_return"].sum()

    entries = perf_response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["ITD"] == pytest.approx(expected)


@when(
    parsers.parse(
        'a performance request is made for attribute "{attribute}" with start {start} and end {end}'
    ),
    target_fixture="perf_response",
)
def request_attribute_with_explicit_range(
    account_name: str,
    attribute: str,
    start: str,
    end: str,
    app_client: TestClient,
    perf_responses: list[object],
) -> object:
    """GET the performance endpoint for one attribute and an explicit date range.

    Also appends the response to the perf_responses accumulator, so scenarios issuing
    this step more than once (via "When ... And ...") can compare all issued responses.
    """
    resp = app_client.get(
        f"/v1/accounts/{account_name}/performance",
        params=[("attribute", attribute), ("start", start), ("end", end)],
    )
    perf_responses.append(resp)
    return resp


@when(
    parsers.parse(
        'a performance request is made for attributes "ITD", "ITD (Ann.)", "1Y", "3Y", and "5Y" '
        "with start {start} and end {end}"
    ),
    target_fixture="perf_response",
)
def request_all_five_attributes_with_range(
    account_name: str, start: str, end: str, app_client: TestClient
) -> object:
    """GET the performance endpoint for all five measures with an explicit date range."""
    return app_client.get(
        f"/v1/accounts/{account_name}/performance",
        params=[
            ("attribute", "ITD"),
            ("attribute", "ITD (Ann.)"),
            ("attribute", "1Y"),
            ("attribute", "3Y"),
            ("attribute", "5Y"),
            ("start", start),
            ("end", end),
        ],
    )


@then(parsers.parse('both requests\' "{attribute}" value for {date_str} are equal'))
def check_both_requests_measure_equal(
    perf_responses: list[object], attribute: str, date_str: str
) -> None:
    """Assert two previously-issued requests agree on a measure's value for a shared date."""
    assert len(perf_responses) == 2, f"Expected 2 requests, got {len(perf_responses)}"
    values = []
    for resp in perf_responses:
        assert resp.status_code == 200, f"Request failed: {resp.text}"
        matching = [e for e in resp.json()["entries"] if e["date"] == date_str]
        assert matching, f"No entry for {date_str} in response: {resp.json()['entries']}"
        values.append(matching[0][attribute])
    assert values[0] == pytest.approx(values[1])


@then(parsers.parse('the single entry has no "{attribute}" key'))
def check_single_entry_missing_key(perf_response: object, attribute: str) -> None:
    """Assert the sole returned entry does not carry the given measure key."""
    entries = perf_response.json()["entries"]
    assert len(entries) == 1
    assert attribute not in entries[0]


@then(parsers.parse('the single entry has numeric "{attr1}", "{attr2}", and "{attr3}" values'))
def check_single_entry_has_three_numeric_measures(
    perf_response: object, attr1: str, attr2: str, attr3: str
) -> None:
    """Assert the sole returned entry carries three named measures, all numeric."""
    entries = perf_response.json()["entries"]
    assert len(entries) == 1
    entry = entries[0]
    for name in (attr1, attr2, attr3):
        assert name in entry, f"'{name}' missing from entry: {entry}"
        assert isinstance(entry[name], int | float)


@then('the single entry has neither a "3Y" nor a "5Y" key')
def check_single_entry_missing_3y_and_5y(perf_response: object) -> None:
    """Assert the sole returned entry omits both 3Y and 5Y keys simultaneously."""
    entries = perf_response.json()["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert "3Y" not in entry
    assert "5Y" not in entry
