"""BDD step implementations for ladder_returns.feature (US1, US2, US3)."""

import io
from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.models.market_data import PriceHistoryPoint
from tests.conftest import FakeMarketDataService

scenarios("ladder_returns.feature")


def _make_multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart file dict."""
    return {
        "file": (
            "ledger.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def _ledger_bytes(rows: list[dict]) -> bytes:
    """Build a raw sub-account ledger XLSX from explicit rows."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _download_ladder(account_name: str, app_client: TestClient) -> pd.DataFrame:
    """Download and parse the stored ladder XLSX for an account."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    assert dl.status_code == 200, f"Download failed: {dl.text}"
    df = pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _next_business_day(d: date) -> date:
    """Return the next Monday-Friday date after d, used to bound ladder expansion.

    A closure row (quantity=0.0) on this date makes LadderExpander's closure rule truncate
    the sub-account's expansion there, instead of extending all the way to today - 2
    business days.
    """
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


@given(
    parsers.parse(
        'a priced position ladder for account "{account_name}" with sub-account "{sub_account}" '
        "active on consecutive business days {start} through {end}"
    ),
    target_fixture="ladder_ctx",
)
def priced_ladder_setup(account_name: str, sub_account: str, start: str, end: str) -> dict:
    """Initialise the ladder-building context for a multi-date scenario."""
    end_date = date.fromisoformat(end)
    return {
        "account_name": account_name,
        "sub_account": sub_account,
        "start": date.fromisoformat(start),
        "end": end_date,
        "closure_date": _next_business_day(end_date),
        "rows": [],
        "prices": {},
    }


@given(
    parsers.parse(
        '"{sub_account}" has price {p1:f} on {d1}, {p2:f} on {d2}, {p3:f} on {d3}, '
        "and {p4:f} on {d4}"
    )
)
def configure_four_day_prices(
    ladder_ctx: dict,
    sub_account: str,
    p1: float,
    d1: str,
    p2: float,
    d2: str,
    p3: float,
    d3: str,
    p4: float,
    d4: str,
) -> None:
    """Record explicit per-date prices, plus a matching price on the closure date."""
    assert sub_account == ladder_ctx["sub_account"]
    dates = [date.fromisoformat(d) for d in (d1, d2, d3, d4)]
    prices = [p1, p2, p3, p4]
    ladder_ctx["prices"][sub_account] = [
        PriceHistoryPoint(date=d, close=p) for d, p in zip(dates, prices, strict=True)
    ] + [PriceHistoryPoint(date=ladder_ctx["closure_date"], close=prices[-1])]


@given(
    parsers.parse(
        '"{sub_account}" has total_income {income1:f} through {last_flat_date}, then '
        "{income2:f} from {change_date} onward, with quantity {quantity:f} on every date"
    )
)
def configure_income_and_quantity(
    ladder_ctx: dict,
    sub_account: str,
    income1: float,
    last_flat_date: str,
    income2: float,
    change_date: str,
    quantity: float,
) -> None:
    """Build the raw (sparse) ledger rows implementing the described income/quantity profile."""
    assert sub_account == ladder_ctx["sub_account"]
    change = date.fromisoformat(change_date)
    ladder_ctx["rows"] = [
        {
            "date": ladder_ctx["start"],
            "sub_account": sub_account,
            "book_cost": quantity * 100.0,
            "quantity": quantity,
            "total_income": income1,
        },
        {
            "date": change,
            "sub_account": sub_account,
            "book_cost": quantity * 100.0,
            "quantity": quantity,
            "total_income": income2,
        },
        {
            "date": ladder_ctx["closure_date"],
            "sub_account": sub_account,
            "book_cost": 0.0,
            "quantity": 0.0,
            "total_income": income2,
        },
    ]


@given(
    parsers.parse(
        'a priced position ladder for account "{account_name}" with sub-account "{sub_account}" '
        'first appearing on {first_date} (no prior row exists for "{sub_account_confirm}")'
    ),
    target_fixture="ladder_ctx",
)
def first_appearance_ladder_setup(
    account_name: str, sub_account: str, first_date: str, sub_account_confirm: str
) -> dict:
    """Build a minimal one-date-then-closed ladder for a sub-account's first appearance."""
    assert sub_account == sub_account_confirm
    d = date.fromisoformat(first_date)
    closure_date = _next_business_day(d)
    rows = [
        {
            "date": d,
            "sub_account": sub_account,
            "book_cost": 500.0,
            "quantity": 5.0,
            "total_income": 0.0,
        },
        {
            "date": closure_date,
            "sub_account": sub_account,
            "book_cost": 0.0,
            "quantity": 0.0,
            "total_income": 0.0,
        },
    ]
    prices = {
        sub_account: [
            PriceHistoryPoint(date=d, close=50.0),
            PriceHistoryPoint(date=closure_date, close=50.0),
        ]
    }
    return {
        "account_name": account_name,
        "sub_account": sub_account,
        "start": d,
        "end": d,
        "closure_date": closure_date,
        "rows": rows,
        "prices": prices,
    }


@given(
    parsers.parse(
        'a priced position ladder for account "{account_name}" with sub-accounts "{sub_a}" '
        'and "{sub_b}" both present on {d1} and {d2}'
    ),
    target_fixture="ladder_ctx",
)
def two_sub_account_ladder_setup(
    account_name: str, sub_a: str, sub_b: str, d1: str, d2: str
) -> dict:
    """Initialise a two-sub-account, two-date ladder-building context."""
    date1 = date.fromisoformat(d1)
    date2 = date.fromisoformat(d2)
    return {
        "account_name": account_name,
        "sub_accounts": [sub_a, sub_b],
        "d1": date1,
        "d2": date2,
        "closure_date": _next_business_day(date2),
        "rows": [],
        "prices": {sub_a: [], sub_b: []},
    }


@given(
    parsers.parse(
        'on {row_date}, "{sub_a}" has quantity {qty_a:f} and "{sub_b}" has quantity {qty_b:f}, '
        "both priced at {price:f}"
    )
)
def configure_shared_price_date(
    ladder_ctx: dict,
    row_date: str,
    sub_a: str,
    qty_a: float,
    sub_b: str,
    qty_b: float,
    price: float,
) -> None:
    """Append the first date's rows (shared price, differing quantities) for both sub-accounts."""
    d = date.fromisoformat(row_date)
    assert [sub_a, sub_b] == ladder_ctx["sub_accounts"]
    for sub_account, quantity in ((sub_a, qty_a), (sub_b, qty_b)):
        ladder_ctx["rows"].append(
            {
                "date": d,
                "sub_account": sub_account,
                "book_cost": quantity * price,
                "quantity": quantity,
                "total_income": 0.0,
            }
        )
        ladder_ctx["prices"][sub_account].append(PriceHistoryPoint(date=d, close=price))


@given(
    parsers.parse(
        'on {row_date}, "{sub_a}" has price {price_a:f} and quantity {qty_a:f}, and "{sub_b}" '
        "has price {price_b:f} and quantity {qty_b:f}"
    )
)
def configure_divergent_price_date(
    ladder_ctx: dict,
    row_date: str,
    sub_a: str,
    price_a: float,
    qty_a: float,
    sub_b: str,
    price_b: float,
    qty_b: float,
) -> None:
    """Append the second date's rows (own price/quantity per sub-account), plus closure rows."""
    d = date.fromisoformat(row_date)
    closure = ladder_ctx["closure_date"]
    assert [sub_a, sub_b] == ladder_ctx["sub_accounts"]
    for sub_account, price, quantity in ((sub_a, price_a, qty_a), (sub_b, price_b, qty_b)):
        ladder_ctx["rows"].append(
            {
                "date": d,
                "sub_account": sub_account,
                "book_cost": quantity * price,
                "quantity": quantity,
                "total_income": 0.0,
            }
        )
        ladder_ctx["rows"].append(
            {
                "date": closure,
                "sub_account": sub_account,
                "book_cost": 0.0,
                "quantity": 0.0,
                "total_income": 0.0,
            }
        )
        ladder_ctx["prices"][sub_account].append(PriceHistoryPoint(date=d, close=price))
        ladder_ctx["prices"][sub_account].append(PriceHistoryPoint(date=closure, close=price))


@given(
    parsers.parse(
        'a priced and return-enriched position ladder already ingested for account "{account_name}"'
    ),
    target_fixture="us3_ctx",
)
def priced_and_enriched_ladder_already_ingested(
    account_name: str,
    fake_market_data_service: FakeMarketDataService,
    app_client: TestClient,
) -> dict:
    """Ingest a small multi-date, return-enriched ladder ready for repeated retrieval."""
    d1, d2 = date(2024, 4, 1), date(2024, 4, 2)
    closure = _next_business_day(d2)
    rows = [
        {
            "date": d1,
            "sub_account": "Equities A",
            "book_cost": 1000.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
        {
            "date": d2,
            "sub_account": "Equities A",
            "book_cost": 1000.0,
            "quantity": 10.0,
            "total_income": 0.0,
        },
        {
            "date": closure,
            "sub_account": "Equities A",
            "book_cost": 0.0,
            "quantity": 0.0,
            "total_income": 0.0,
        },
    ]
    prices = [
        PriceHistoryPoint(date=d1, close=100.0),
        PriceHistoryPoint(date=d2, close=101.0),
        PriceHistoryPoint(date=closure, close=101.0),
    ]
    fake_market_data_service.configure_prices("Equities A", prices)
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(_ledger_bytes(rows)),
    )
    assert resp.status_code == 201, f"Setup ingestion failed: {resp.text}"
    return {"account_name": account_name, "start": d1, "end": d2}


@when(
    "the position time series is retrieved twice in a row for the same account, positions, "
    "attributes, and date range",
    target_fixture="repeated_reads",
)
def retrieve_position_time_series_twice(us3_ctx: dict, app_client: TestClient) -> dict:
    """Issue two identical GET requests for position_return/weighted_position_return."""
    url = (
        f"/v1/accounts/{us3_ctx['account_name']}/position"
        "?attribute=position_return&attribute=weighted_position_return"
        f"&start={us3_ctx['start'].isoformat()}&end={us3_ctx['end'].isoformat()}"
    )
    first = app_client.get(url)
    second = app_client.get(url)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    return {"first": first.json(), "second": second.json()}


@then(
    "both responses report identical position_return and weighted_position_return values for "
    "every matching row"
)
def check_identical_across_repeated_reads(repeated_reads: dict) -> None:
    """Assert both GET responses report identical values, with no re-ingestion in between."""

    def _by_key(payload: dict) -> dict[tuple[str, str], tuple[float, float]]:
        return {
            (e["date"], e["position"]): (e["position_return"], e["weighted_position_return"])
            for e in payload["entries"]
        }

    first_entries = _by_key(repeated_reads["first"])
    second_entries = _by_key(repeated_reads["second"])
    assert len(first_entries) > 0
    assert first_entries == second_entries


@when("the ladder is ingested", target_fixture="ingest_result")
def ingest_the_ladder(
    ladder_ctx: dict,
    fake_market_data_service: FakeMarketDataService,
    app_client: TestClient,
) -> dict:
    """POST the built ledger and download the resulting return-enriched ladder."""
    for identifier, price_points in ladder_ctx.get("prices", {}).items():
        fake_market_data_service.configure_prices(identifier, price_points)
    resp = app_client.post(
        f"/v1/accounts/{ladder_ctx['account_name']}/ladder",
        files=_make_multipart(_ledger_bytes(ladder_ctx["rows"])),
    )
    assert resp.status_code in (200, 201), f"Ingestion failed: {resp.text}"
    df = _download_ladder(ladder_ctx["account_name"], app_client)
    return {"account_name": ladder_ctx["account_name"], "df": df}


def _row_for(ingest_result: dict, sub_account: str, row_date: date) -> pd.Series:
    """Fetch the single row matching (sub_account, date) from the downloaded ladder."""
    df = ingest_result["df"]
    match = df[(df["sub_account"] == sub_account) & (df["date"] == row_date)]
    assert len(match) == 1, (
        f"Expected exactly one row for {sub_account}/{row_date}, got {len(match)}"
    )
    return match.iloc[0]


@then(
    parsers.parse(
        "the row for {row_date} has position_return equal to "
        "({p_curr:f} - {p_prev:f} + {income:f}) / {p_prev2:f}"
    )
)
def check_position_return_formula(
    ladder_ctx: dict,
    ingest_result: dict,
    row_date: str,
    p_curr: float,
    p_prev: float,
    income: float,
    p_prev2: float,
) -> None:
    """Assert a row's position_return matches the literal formula from the scenario."""
    expected = (p_curr - p_prev + income) / p_prev2
    row = _row_for(ingest_result, ladder_ctx["sub_account"], date.fromisoformat(row_date))
    assert row["position_return"] == pytest.approx(expected)


@then("every row in the stored ladder has a non-null position_return and weighted_position_return")
def check_every_row_has_returns(ingest_result: dict) -> None:
    """Assert both new columns are non-null across the entire downloaded ladder (SC-001)."""
    df = ingest_result["df"]
    assert "position_return" in df.columns
    assert "weighted_position_return" in df.columns
    assert df["position_return"].notna().all()
    assert df["weighted_position_return"].notna().all()


@then(
    parsers.parse(
        'the row for "{sub_account}" on {row_date} has position_return equal to {expected:f}'
    )
)
def check_named_row_position_return(
    ingest_result: dict, sub_account: str, row_date: str, expected: float
) -> None:
    """Assert a named sub-account's row has the expected position_return value."""
    row = _row_for(ingest_result, sub_account, date.fromisoformat(row_date))
    assert row["position_return"] == pytest.approx(expected)


@then(
    parsers.parse(
        'the row for "{sub_account}" on {row_date} has weighted_position_return equal to {expected:f}'
    )
)
def check_named_row_weighted_position_return(
    ingest_result: dict, sub_account: str, row_date: str, expected: float
) -> None:
    """Assert a named sub-account's row has the expected weighted_position_return value."""
    row = _row_for(ingest_result, sub_account, date.fromisoformat(row_date))
    assert row["weighted_position_return"] == pytest.approx(expected)


@then(parsers.parse('the portfolio_weight for "{sub_account}" differs between {d1} and {d2}'))
def check_portfolio_weight_differs(ingest_result: dict, sub_account: str, d1: str, d2: str) -> None:
    """Guard that the scenario's fixture actually produces a weight change (not a vacuous test)."""
    row1 = _row_for(ingest_result, sub_account, date.fromisoformat(d1))
    row2 = _row_for(ingest_result, sub_account, date.fromisoformat(d2))
    assert row1["portfolio_weight"] != pytest.approx(row2["portfolio_weight"])


@then(
    parsers.parse(
        'the "{sub_account}" row for {row_date} has weighted_position_return equal to its '
        "position_return multiplied by its {prev_date} portfolio_weight, not its {row_date2} "
        "portfolio_weight"
    )
)
def check_weighted_return_uses_previous_weight(
    ingest_result: dict,
    sub_account: str,
    row_date: str,
    prev_date: str,
    row_date2: str,
) -> None:
    """Assert weighted_position_return uses the T-1 portfolio_weight, not the same-date weight.

    The expected value is computed from the downloaded ladder's own previous-row
    portfolio_weight (the test oracle), not a hand-derived literal, per research.md/tasks.md's
    documented design decision — this directly encodes "T-1 weight, not same-date weight" and
    also positively rules out the original (bugged) same-date formula regressing.
    """
    assert row_date == row_date2
    row = _row_for(ingest_result, sub_account, date.fromisoformat(row_date))
    prev_row = _row_for(ingest_result, sub_account, date.fromisoformat(prev_date))
    expected = row["position_return"] * prev_row["portfolio_weight"]
    same_date_formula = row["position_return"] * row["portfolio_weight"]
    assert row["weighted_position_return"] == pytest.approx(expected)
    assert row["weighted_position_return"] != pytest.approx(same_date_formula)
