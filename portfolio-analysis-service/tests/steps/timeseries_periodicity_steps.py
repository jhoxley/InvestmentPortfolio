"""BDD step implementations for timeseries_periodicity.feature (US1, US2)."""

import io
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("timeseries_periodicity.feature")

# Period aliases derived independently of the production code, so these assertions
# cross-check the implementation rather than restating it.
_ALIAS_FOR_PERIODICITY = {"week": "W", "month": "M", "quarter": "Q", "annual": "Y"}

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    """Serialise a DataFrame to in-memory XLSX bytes.

    Args:
        df: The frame to serialise.

    Returns:
        Raw XLSX bytes.
    """
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _ingest_capital_ledger(
    account_name: str, start: date, end: date, app_client: TestClient
) -> None:
    """Ingest a capital ledger with a weekly observation, each week's value distinct.

    Weekly (rather than sparse) observations mean every calendar window in the range has
    its own value, so "the last observation in the window" is a meaningful assertion at
    weekly, monthly, quarterly and annual periodicity alike.

    Args:
        account_name: Target account name.
        start: First recorded date (must be a business day).
        end: Last recorded date.
        app_client: Test client fixture.
    """
    dates: list[date] = []
    current = start
    while current < end:
        dates.append(current)
        current += timedelta(days=7)
    dates.append(end)

    df = pd.DataFrame(
        {
            "date": dates,
            "capital": [1000.0 + (n * 13) for n in range(len(dates))],
            "income": [float(n * 3) for n in range(len(dates))],
            "book_value": [900.0 + (n * 11) for n in range(len(dates))],
        }
    )
    resp = app_client.post(
        f"/v1/accounts/{account_name}/capital",
        files={"file": ("capital.xlsx", _to_xlsx_bytes(df), _XLSX_MEDIA_TYPE)},
    )
    assert resp.status_code == 201, f"Capital setup failed: {resp.text}"


def _post_ladder(account_name: str, rows: list[dict[str, Any]], app_client: TestClient) -> None:
    """POST a raw sub-account ledger to the ladder ingestion endpoint.

    Args:
        account_name: Target account name.
        rows: Raw ledger rows (date, sub_account, book_cost, quantity, total_income).
        app_client: Test client fixture.
    """
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files={"file": ("ledger.xlsx", _to_xlsx_bytes(pd.DataFrame(rows)), _XLSX_MEDIA_TYPE)},
    )
    assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"


def _ingest_position_ladder(
    account_name: str, start: date, end: date, app_client: TestClient, positions: list[str]
) -> None:
    """Ingest a ladder holding the given positions, with quantities that change mid-range.

    Two dated observations per position (the second with a different quantity) so that
    market_value varies across calendar windows rather than being constant.

    Args:
        account_name: Target account name.
        start: First recorded date (must be a business day).
        end: Last recorded date of interest.
        app_client: Test client fixture.
        positions: Sub-account names to record.
    """
    midpoint = start + ((end - start) // 2)
    rows: list[dict[str, Any]] = []
    for index, position in enumerate(positions):
        rows.append(
            {
                "date": start,
                "sub_account": position,
                "book_cost": 500.0 + (index * 100),
                "quantity": 10.0 + index,
                "total_income": 0.0,
            }
        )
        rows.append(
            {
                "date": midpoint,
                "sub_account": position,
                "book_cost": 700.0 + (index * 100),
                "quantity": 14.0 + index,
                "total_income": 5.0 + index,
            }
        )
    _post_ladder(account_name, rows, app_client)


def _get_series(
    context: dict[str, Any], app_client: TestClient, periodicity: str | None
) -> httpx.Response:
    """Re-issue the stored request, optionally overriding the periodicity parameter.

    Args:
        context: Stored request context (path, attributes, positions, start, end).
        app_client: Test client fixture.
        periodicity: Periodicity to send, or None to omit the parameter entirely.

    Returns:
        The httpx Response.
    """
    params: list[tuple[str, str]] = [("attribute", a) for a in context["attributes"]]
    params += [("position", p) for p in context.get("positions", [])]
    if context["start"] is not None:
        params.append(("start", context["start"]))
    if context["end"] is not None:
        params.append(("end", context["end"]))
    if periodicity is not None:
        params.append(("periodicity", periodicity))
    return app_client.get(f"/v1/accounts/{context['account']}{context['path']}", params=params)


def _request_context(
    account_name: str,
    path: str,
    attributes: list[str],
    start: str | None,
    end: str | None,
    periodicity: str | None,
    app_client: TestClient,
    positions: list[str] | None = None,
) -> dict[str, Any]:
    """Build a request context and issue the request it describes.

    Args:
        account_name: Account to query.
        path: Endpoint suffix ("/timeseries" or "/position").
        attributes: Requested attribute names.
        start: Start date (ISO string), or None to omit the parameter.
        end: End date (ISO string), or None to omit the parameter.
        periodicity: Periodicity to send, or None to omit.
        app_client: Test client fixture.
        positions: Requested position names, if any.

    Returns:
        The context dict, with the response stored under "response".
    """
    context: dict[str, Any] = {
        "account": account_name,
        "path": path,
        "attributes": attributes,
        "positions": positions or [],
        "start": start,
        "end": end,
        "periodicity": periodicity,
    }
    context["response"] = _get_series(context, app_client, periodicity)
    return context


def _last_business_day_per_window(daily_dates: list[date], periodicity: str) -> list[date]:
    """Return each calendar window's last date, derived from the daily series itself.

    Args:
        daily_dates: Every date present in the equivalent daily response, ascending.
        periodicity: The requested periodicity.

    Returns:
        One date per window — the latest daily date falling inside it — in window order.
    """
    alias = _ALIAS_FOR_PERIODICITY[periodicity]
    frame = pd.DataFrame({"date": daily_dates})
    periods = pd.to_datetime(frame["date"]).dt.to_period(alias)
    return [group["date"].max() for _, group in frame.groupby(periods, sort=True)]


@given(
    parsers.parse('account "{account_name}" has a capital ledger recorded from {start} to {end}'),
    target_fixture="account_name",
)
def capital_ledger_account(account_name: str, start: str, end: str, app_client: TestClient) -> str:
    """Ingest a weekly-observation capital ledger spanning the given range."""
    _ingest_capital_ledger(
        account_name, date.fromisoformat(start), date.fromisoformat(end), app_client
    )
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has a capital ledger and position ladder recorded '
        "from {start} to {end}"
    ),
    target_fixture="account_name",
)
def dual_resource_account(account_name: str, start: str, end: str, app_client: TestClient) -> str:
    """Ingest both a capital ledger and a two-position ladder spanning the given range."""
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    _ingest_position_ladder(account_name, start_date, end_date, app_client, ["Cash", "Equity A"])
    _ingest_capital_ledger(account_name, start_date, end_date, app_client)
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has a position ladder holding positions "{pos1}" and '
        '"{pos2}" recorded from {start} to {end}'
    ),
    target_fixture="account_name",
)
def two_position_ladder_account(
    account_name: str, pos1: str, pos2: str, start: str, end: str, app_client: TestClient
) -> str:
    """Ingest a ladder holding two positions across the given range."""
    _ingest_position_ladder(
        account_name,
        date.fromisoformat(start),
        date.fromisoformat(end),
        app_client,
        [pos1, pos2],
    )
    return account_name


@given(
    parsers.parse(
        'account "{account_name}" has a position ladder where position "{position}" holds '
        "data only from {start} to {end}"
    ),
    target_fixture="account_name",
)
def partial_coverage_position_account(
    account_name: str, position: str, start: str, end: str, app_client: TestClient
) -> str:
    """Ingest a ladder where Cash spans the year but `position` lives for one quarter only.

    The position's quantity is driven to zero on its final date, which is the ladder's
    closure rule for excluding a non-Cash sub-account from every subsequent date.
    """
    position_start = date.fromisoformat(start)
    position_end = date.fromisoformat(end)
    rows: list[dict[str, Any]] = [
        {
            "date": date(2025, 1, 1),
            "sub_account": "Cash",
            "book_cost": 1000.0,
            "quantity": 1000.0,
            "total_income": 0.0,
        },
        {
            "date": position_start,
            "sub_account": position,
            "book_cost": 500.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
        {
            "date": position_end,
            "sub_account": position,
            "book_cost": 0.0,
            "quantity": 0.0,
            "total_income": 5.0,
        },
    ]
    _post_ladder(account_name, rows, app_client)
    return account_name


@when(
    parsers.parse(
        'a request is made for attribute "{attribute}" from {start} to {end} '
        'with periodicity "{periodicity}"'
    ),
    target_fixture="ts_request",
)
def request_single_attribute_with_periodicity(
    account_name: str,
    attribute: str,
    start: str,
    end: str,
    periodicity: str,
    app_client: TestClient,
) -> dict[str, Any]:
    """GET the account timeseries for one attribute at an explicit periodicity."""
    return _request_context(
        account_name, "/timeseries", [attribute], start, end, periodicity, app_client
    )


@when(
    parsers.parse(
        'a request is made for attribute "{attribute}" from {start} to {end} '
        "with no periodicity parameter"
    ),
    target_fixture="ts_request",
)
def request_single_attribute_without_periodicity(
    account_name: str, attribute: str, start: str, end: str, app_client: TestClient
) -> dict[str, Any]:
    """GET the account timeseries for one attribute, omitting the periodicity parameter."""
    return _request_context(account_name, "/timeseries", [attribute], start, end, None, app_client)


@when(
    parsers.parse(
        'a request is made for attributes "{attr1}" and "{attr2}" from {start} to {end} '
        'with periodicity "{periodicity}"'
    ),
    target_fixture="ts_request",
)
def request_two_attributes_with_periodicity(
    account_name: str,
    attr1: str,
    attr2: str,
    start: str,
    end: str,
    periodicity: str,
    app_client: TestClient,
) -> dict[str, Any]:
    """GET the account timeseries for two attributes at an explicit periodicity."""
    return _request_context(
        account_name, "/timeseries", [attr1, attr2], start, end, periodicity, app_client
    )


@when(
    parsers.parse(
        'a position request is made for attribute "{attribute}" from {start} to {end} '
        'with periodicity "{periodicity}"'
    ),
    target_fixture="ts_request",
)
def position_request_with_periodicity(
    account_name: str,
    attribute: str,
    start: str,
    end: str,
    periodicity: str,
    app_client: TestClient,
) -> dict[str, Any]:
    """GET the position timeseries for one attribute at an explicit periodicity."""
    return _request_context(
        account_name, "/position", [attribute], start, end, periodicity, app_client
    )


@when(
    parsers.parse(
        'a position request is made for attribute "{attribute}" from {start} to {end} '
        "with no periodicity parameter"
    ),
    target_fixture="ts_request",
)
def position_request_without_periodicity(
    account_name: str, attribute: str, start: str, end: str, app_client: TestClient
) -> dict[str, Any]:
    """GET the position timeseries for one attribute, omitting the periodicity parameter."""
    return _request_context(account_name, "/position", [attribute], start, end, None, app_client)


@when(
    parsers.parse(
        'a position request is made for position "{position}" and attribute "{attribute}" '
        'from {start} to {end} with periodicity "{periodicity}"'
    ),
    target_fixture="ts_request",
)
def position_request_for_one_position(
    account_name: str,
    position: str,
    attribute: str,
    start: str,
    end: str,
    periodicity: str,
    app_client: TestClient,
) -> dict[str, Any]:
    """GET the position timeseries for a single named position."""
    return _request_context(
        account_name,
        "/position",
        [attribute],
        start,
        end,
        periodicity,
        app_client,
        positions=[position],
    )


@then(parsers.parse("the response status is {status:d}"))
def response_status_is(ts_request: dict[str, Any], status: int) -> None:
    """Assert the HTTP status code."""
    response = ts_request["response"]
    assert response.status_code == status, response.text


@then(parsers.parse("the response contains exactly {count:d} entries"))
@then(parsers.parse("the response contains exactly {count:d} entry"))
def response_entry_count(ts_request: dict[str, Any], count: int) -> None:
    """Assert the exact number of returned entries."""
    entries = ts_request["response"].json()["entries"]
    assert len(entries) == count, f"Expected {count} entries, got {len(entries)}"


@then(parsers.parse('the response reports its periodicity as "{periodicity}"'))
def response_reports_periodicity(ts_request: dict[str, Any], periodicity: str) -> None:
    """Assert the applied periodicity is echoed in the response body."""
    body = ts_request["response"].json()
    assert body["periodicity"] == periodicity


@then("every entry date is the first business day on or after 01 January of its calendar year")
def entries_align_to_january(ts_request: dict[str, Any]) -> None:
    """Assert annual windows are dated at 01-Jan, rolled forward, or the clamped start."""
    body = ts_request["response"].json()
    resolved_start = date.fromisoformat(body["from_date"])
    for entry in body["entries"]:
        entry_date = date.fromisoformat(entry["date"])
        anchor = max(date(entry_date.year, 1, 1), resolved_start)
        expected = pd.bdate_range(start=anchor, periods=1)[0].date()
        assert entry_date == expected, f"{entry_date} is not an annual window start"


@then("every entry date is the first business day on or after the 1st of its calendar month")
def entries_align_to_month_start(ts_request: dict[str, Any]) -> None:
    """Assert monthly windows are dated at the 1st, rolled forward, or the clamped start."""
    body = ts_request["response"].json()
    resolved_start = date.fromisoformat(body["from_date"])
    for entry in body["entries"]:
        entry_date = date.fromisoformat(entry["date"])
        anchor = max(entry_date.replace(day=1), resolved_start)
        expected = pd.bdate_range(start=anchor, periods=1)[0].date()
        assert entry_date == expected, f"{entry_date} is not a monthly window start"


@then("every entry date falls on a Monday or the first business day of its calendar week")
def entries_align_to_monday(ts_request: dict[str, Any]) -> None:
    """Assert weekly windows begin on Monday (or the clamped resolved start)."""
    body = ts_request["response"].json()
    resolved_start = date.fromisoformat(body["from_date"])
    for entry in body["entries"]:
        entry_date = date.fromisoformat(entry["date"])
        monday = entry_date - timedelta(days=entry_date.weekday())
        anchor = max(monday, resolved_start)
        expected = pd.bdate_range(start=anchor, periods=1)[0].date()
        assert entry_date == expected, f"{entry_date} is not a weekly window start"


@then(
    "every entry date is the first business day on or after the 1st of January, April, July or October"
)
def entries_align_to_quarter_start(ts_request: dict[str, Any]) -> None:
    """Assert quarterly windows begin in the four calendar quarter-start months."""
    body = ts_request["response"].json()
    resolved_start = date.fromisoformat(body["from_date"])
    for entry in body["entries"]:
        entry_date = date.fromisoformat(entry["date"])
        quarter_month = (((entry_date.month - 1) // 3) * 3) + 1
        anchor = max(date(entry_date.year, quarter_month, 1), resolved_start)
        expected = pd.bdate_range(start=anchor, periods=1)[0].date()
        assert entry_date == expected, f"{entry_date} is not a quarterly window start"


@then(parsers.parse("every entry date is exactly {expected_date}"))
def every_entry_date_is(ts_request: dict[str, Any], expected_date: str) -> None:
    """Assert every entry carries one specific date."""
    entries = ts_request["response"].json()["entries"]
    assert entries, "No entries returned"
    for entry in entries:
        assert entry["date"] == expected_date


@then("every position sharing a window carries the same entry date")
def positions_share_window_dates(ts_request: dict[str, Any]) -> None:
    """Assert window dates are uniform across positions, so series can be aligned."""
    entries = ts_request["response"].json()["entries"]
    dates_by_position: dict[str, set[str]] = {}
    for entry in entries:
        dates_by_position.setdefault(entry["position"], set()).add(entry["date"])

    assert len(dates_by_position) > 1, "Scenario needs more than one position"
    date_sets = list(dates_by_position.values())
    assert all(s == date_sets[0] for s in date_sets), (
        f"Positions returned differing window dates: {dates_by_position}"
    )


@then(
    parsers.parse(
        'each entry value for "{attribute}" equals the daily series value on the last '
        "business day of its window"
    )
)
def values_match_daily_series_window_close(
    ts_request: dict[str, Any], attribute: str, app_client: TestClient
) -> None:
    """Cross-check every aggregated value against the equivalent daily response."""
    aggregated = ts_request["response"].json()["entries"]
    daily = _get_series(ts_request, app_client, None).json()["entries"]
    daily_by_date = {date.fromisoformat(e["date"]): e for e in daily}
    window_closes = _last_business_day_per_window(sorted(daily_by_date), ts_request["periodicity"])

    assert len(aggregated) == len(window_closes), (
        f"Aggregated entries ({len(aggregated)}) do not match the number of windows "
        f"present in the daily series ({len(window_closes)})"
    )
    for entry, close_date in zip(aggregated, window_closes, strict=True):
        expected = daily_by_date[close_date][attribute]
        assert entry[attribute] == expected, (
            f"Entry dated {entry['date']} carries {attribute}={entry[attribute]}, "
            f"expected the {close_date} value {expected}"
        )


@then(
    parsers.parse(
        'each entry value for "{attribute}" equals that position\'s daily value on the '
        "last business day of its window"
    )
)
def position_values_match_daily_series(
    ts_request: dict[str, Any], attribute: str, app_client: TestClient
) -> None:
    """Cross-check every aggregated per-position value against the daily response."""
    aggregated = ts_request["response"].json()["entries"]
    daily = _get_series(ts_request, app_client, None).json()["entries"]

    daily_by_position: dict[str, dict[date, dict[str, Any]]] = {}
    for entry in daily:
        daily_by_position.setdefault(entry["position"], {})[date.fromisoformat(entry["date"])] = (
            entry
        )

    aggregated_by_position: dict[str, list[dict[str, Any]]] = {}
    for entry in aggregated:
        aggregated_by_position.setdefault(entry["position"], []).append(entry)

    assert set(aggregated_by_position) == set(daily_by_position)

    for position, rows in aggregated_by_position.items():
        by_date = daily_by_position[position]
        window_closes = _last_business_day_per_window(sorted(by_date), ts_request["periodicity"])
        assert len(rows) == len(window_closes), (
            f"Position {position} returned {len(rows)} entries for {len(window_closes)} windows"
        )
        for entry, close_date in zip(rows, window_closes, strict=True):
            expected = by_date[close_date][attribute]
            assert entry[attribute] == expected, (
                f"{position} entry dated {entry['date']} carries "
                f"{attribute}={entry[attribute]}, expected the {close_date} value {expected}"
            )


@then(parsers.parse('every entry contains a "{attr1}" value and a "{attr2}" value'))
def entries_contain_both_attributes(ts_request: dict[str, Any], attr1: str, attr2: str) -> None:
    """Assert both requested attributes are present on every entry."""
    for entry in ts_request["response"].json()["entries"]:
        assert attr1 in entry, f"{attr1} missing from entry {entry}"
        assert attr2 in entry, f"{attr2} missing from entry {entry}"


@then("all values on each entry come from the same source date in the daily series")
def entry_values_share_a_source_date(ts_request: dict[str, Any], app_client: TestClient) -> None:
    """Assert each aggregated entry matches one daily row across every attribute at once."""
    aggregated = ts_request["response"].json()["entries"]
    daily = _get_series(ts_request, app_client, None).json()["entries"]
    daily_by_date = {date.fromisoformat(e["date"]): e for e in daily}
    window_closes = _last_business_day_per_window(sorted(daily_by_date), ts_request["periodicity"])
    attributes = ts_request["attributes"]

    for entry, close_date in zip(aggregated, window_closes, strict=True):
        source_row = daily_by_date[close_date]
        for attribute in attributes:
            assert entry[attribute] == source_row[attribute], (
                f"Entry dated {entry['date']} drew {attribute} from a different date "
                f"than {close_date}"
            )


@then("the response contains one entry per business day in the range")
def one_entry_per_business_day(ts_request: dict[str, Any]) -> None:
    """Assert the unaggregated response still has a row per business day."""
    body = ts_request["response"].json()
    expected = len(pd.bdate_range(start=body["from_date"], end=body["to_date"]))
    assert len(body["entries"]) == expected


@then("the response contains one entry per business day and position in the range")
def one_entry_per_business_day_and_position(ts_request: dict[str, Any]) -> None:
    """Assert the unaggregated position response has a row per (business day, position)."""
    body = ts_request["response"].json()
    business_days = len(pd.bdate_range(start=body["from_date"], end=body["to_date"]))
    expected = business_days * len(body["positions"])
    assert len(body["entries"]) == expected, (
        f"Expected {expected} entries ({business_days} business days x "
        f"{len(body['positions'])} positions), got {len(body['entries'])}"
    )


@then(
    'the response body is identical to the same request with periodicity "day" '
    "apart from the periodicity field"
)
def body_matches_explicit_day(ts_request: dict[str, Any], app_client: TestClient) -> None:
    """Assert omitting the parameter and sending `day` produce the same body."""
    omitted = ts_request["response"].json()
    explicit = _get_series(ts_request, app_client, "day").json()

    assert omitted == explicit, "Omitted and explicit 'day' bodies differ"
    assert omitted["periodicity"] == "day"


@when(
    parsers.parse('a request is made for attribute "{attribute}" with periodicity "{periodicity}"'),
    target_fixture="ts_request",
)
def request_attribute_with_periodicity_no_dates(
    account_name: str, attribute: str, periodicity: str, app_client: TestClient
) -> dict[str, Any]:
    """GET the account timeseries with a periodicity but no explicit date range."""
    return _request_context(
        account_name, "/timeseries", [attribute], None, None, periodicity, app_client
    )


@when(
    parsers.parse(
        'a position request is made for attribute "{attribute}" with periodicity "{periodicity}"'
    ),
    target_fixture="ts_request",
)
def position_request_with_periodicity_no_dates(
    account_name: str, attribute: str, periodicity: str, app_client: TestClient
) -> dict[str, Any]:
    """GET the position timeseries with a periodicity but no explicit date range."""
    return _request_context(
        account_name, "/position", [attribute], None, None, periodicity, app_client
    )


@then(parsers.parse('the error is an RFC 7807 problem document of type "{type_slug}"'))
def error_is_rfc7807_problem(ts_request: dict[str, Any], type_slug: str) -> None:
    """Assert the error body is application/problem+json with the expected type slug."""
    response = ts_request["response"]
    assert response.headers["content-type"].startswith("application/problem+json"), (
        f"Expected problem+json, got {response.headers['content-type']}"
    )
    body = response.json()
    assert body["type"].endswith(f"/{type_slug}"), body["type"]
    assert body["title"] == "Unsupported Periodicity"
    assert body["status"] == 422
    assert body["instance"].startswith("/v1/accounts/")


@then("the error names every supported periodicity value")
def error_names_supported_values(ts_request: dict[str, Any]) -> None:
    """Assert the detail message lists all five supported values (SC-007)."""
    detail = ts_request["response"].json()["detail"]
    for value in ("day", "week", "month", "quarter", "annual"):
        assert value in detail, f"Supported value '{value}' missing from detail: {detail}"


@then("the response is identical to the same request made with no periodicity parameter")
def response_identical_to_omitted(ts_request: dict[str, Any], app_client: TestClient) -> None:
    """Assert explicit `day` and an omitted parameter return the same body."""
    explicit = ts_request["response"].json()
    omitted = _get_series(ts_request, app_client, None).json()

    assert explicit == omitted, "Explicit 'day' and omitted bodies differ"
