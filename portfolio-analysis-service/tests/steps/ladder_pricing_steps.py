"""BDD step implementations for ladder_pricing.feature (US1)."""

import io
from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("ladder_pricing.feature")


def _make_ledger_bytes(sub_accounts: list[str], days_back: int = 30) -> bytes:
    """Build a minimal valid XLSX ledger as bytes for the given sub-accounts."""
    today = date.today()
    d1 = today - timedelta(days=days_back)
    rows = [
        {
            "date": d1,
            "sub_account": sa,
            "book_cost": 1000.0,
            "quantity": 1000.0 if sa == "Cash" else 10.0,
            "total_income": 0.0,
        }
        for sa in sub_accounts
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _make_multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart file dict."""
    return {
        "file": (
            "ledger.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


@given(
    parsers.parse(
        'a valid sub-account ledger for account "{account_name}" with sub-accounts '
        '"{sub_account_a}" and "{sub_account_b}"'
    ),
    target_fixture="ledger_bytes",
)
def valid_priced_ledger(account_name: str, sub_account_a: str, sub_account_b: str) -> bytes:
    """Provide a valid ledger with two named sub-accounts."""
    return _make_ledger_bytes([sub_account_a, sub_account_b])


@given(
    parsers.parse(
        '"{sub_account}" resolves via the identifier mapping to a ticker '
        "with a complete GBP price history"
    )
)
def identifier_resolves_with_full_history(sub_account: str) -> None:
    """No-op: the shared fake mapping/market-data fixtures already provide this by default."""


@when(
    parsers.parse('the ledger is ingested for account "{account_name}"'),
    target_fixture="post_response",
)
def ingest_ledger(account_name: str, ledger_bytes: bytes, app_client: TestClient) -> object:
    """POST the ledger to the ingestion endpoint."""
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(ledger_bytes),
    )


def _download_ladder(account_name: str, app_client: TestClient) -> pd.DataFrame:
    """Download and parse the stored ladder XLSX for an account."""
    dl = app_client.get(f"/v1/accounts/{account_name}/ladder/download")
    assert dl.status_code == 200, f"Download failed: {dl.text}"
    return pd.read_excel(io.BytesIO(dl.content), engine="openpyxl")


@then("every row in the stored ladder has a non-null price, market value, and portfolio weight")
def check_every_row_priced(post_response: object, app_client: TestClient) -> None:
    """Assert price/market_value/portfolio_weight are all non-null for every row."""
    account_name = post_response.json()["account_name"]
    df = _download_ladder(account_name, app_client)
    for col in ("price", "market_value", "portfolio_weight"):
        assert col in df.columns, f"Missing column: {col}"
        assert df[col].notna().all(), f"Column {col} has null values"


@then("the Cash sub-account's price is 1.0 on every date")
def check_cash_price(post_response: object, app_client: TestClient) -> None:
    """Assert Cash is priced at 1.0 GBP on every row."""
    account_name = post_response.json()["account_name"]
    df = _download_ladder(account_name, app_client)
    cash_rows = df[df["sub_account"] == "Cash"]
    assert len(cash_rows) > 0
    assert (cash_rows["price"] == 1.0).all()


@then("each row's market value equals its price multiplied by its quantity")
def check_market_value(post_response: object, app_client: TestClient) -> None:
    """Assert market_value == price * quantity for every row."""
    account_name = post_response.json()["account_name"]
    df = _download_ladder(account_name, app_client)
    assert (df["market_value"] == df["price"] * df["quantity"]).all()


@given(
    parsers.parse(
        'a successfully enriched position ladder for account "{account_name}" with '
        "multiple sub-accounts"
    ),
    target_fixture="post_response",
)
def enriched_ladder_exists(account_name: str, app_client: TestClient) -> object:
    """Ingest a ledger with multiple sub-accounts to set up a priced ladder."""
    ledger_bytes = _make_ledger_bytes(["Cash", "Equity A"])
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(ledger_bytes),
    )
    assert resp.status_code == 201, resp.text
    return resp


@when("the portfolio weight column is inspected")
def inspect_portfolio_weight() -> None:
    """No-op: the ladder was already enriched by the Given step."""


@then(
    "for every distinct date in the ladder, the sum of portfolio weight across all "
    "sub-accounts on that date is approximately 1.0"
)
def check_weights_sum_to_one(post_response: object, app_client: TestClient) -> None:
    """Assert per-date portfolio_weight sums to 1.0 within tolerance."""
    account_name = post_response.json()["account_name"]
    df = _download_ladder(account_name, app_client)
    sums = df.groupby("date")["portfolio_weight"].sum()
    for total in sums:
        assert total == pytest.approx(1.0, abs=0.0001)


@given(
    parsers.parse(
        'account "{account_name}" already has an enriched position ladder from a prior ingestion'
    ),
    target_fixture="stored_ledger_bytes",
)
def stored_priced_ladder(account_name: str, app_client: TestClient) -> bytes:
    """Ingest an initial ledger for the given account and return its bytes."""
    ledger_bytes = _make_ledger_bytes(["Cash", "Equity A"])
    resp = app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(ledger_bytes),
    )
    assert resp.status_code == 201, resp.text
    return ledger_bytes


@when(
    parsers.parse('the exact same ledger file is submitted again for account "{account_name}"'),
    target_fixture="post_response",
)
def resubmit_same_priced_ledger(
    account_name: str, stored_ledger_bytes: bytes, app_client: TestClient
) -> object:
    """Re-submit the identical ledger file for the same account."""
    return app_client.post(
        f"/v1/accounts/{account_name}/ladder",
        files=_make_multipart(stored_ledger_bytes),
    )


@then(parsers.parse("the response status is {status_code:d}"))
def check_status_code(post_response: object, status_code: int) -> None:
    """Assert the response HTTP status code."""
    assert post_response.status_code == status_code, post_response.text


@then(parsers.parse('the response body contains status "{expected_status}"'))
def check_status_field(post_response: object, expected_status: str) -> None:
    """Assert the status field in the JSON body."""
    body = post_response.json()
    assert body.get("status") == expected_status


@then(
    "the ladder's price, market value, and portfolio weight columns reflect newly recomputed values"
)
def check_refreshed_values(post_response: object, app_client: TestClient) -> None:
    """Assert the refreshed ladder still has fully populated pricing columns."""
    account_name = post_response.json()["account_name"]
    df = _download_ladder(account_name, app_client)
    for col in ("price", "market_value", "portfolio_weight"):
        assert df[col].notna().all(), f"Column {col} has null values after refresh"
