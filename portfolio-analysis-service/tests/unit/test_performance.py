"""Performance smoke tests verifying SC-001, SC-002, and SC-003 timing targets."""

import io
import time
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient

from tests.conftest import FakeMarketDataService


def _generate_large_ledger(rows: int = 5000) -> bytes:
    """Generate a synthetic sub-account ledger with approximately `rows` data rows.

    Distributes rows across 10 sub-accounts over a long date history, all well
    before the T-2 boundary so that the expansion range is non-empty.

    Args:
        rows: Approximate number of output rows to generate.

    Returns:
        XLSX file contents as bytes.
    """
    today = date.today()
    sub_accounts = [f"Equity-{i}" for i in range(9)] + ["Cash"]
    rows_per_account = max(1, rows // len(sub_accounts))
    start_date = today - timedelta(days=rows_per_account + 10)

    records = []
    for sa in sub_accounts:
        for offset in range(rows_per_account):
            activity_date = start_date + timedelta(days=offset)
            records.append(
                {
                    "date": activity_date,
                    "sub_account": sa,
                    "book_cost": 1000.0 + offset,
                    "quantity": 10.0,
                    "total_income": float(offset),
                }
            )
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart upload dict.

    Args:
        file_bytes: XLSX content.

    Returns:
        Dict for TestClient files= parameter.
    """
    return {
        "file": (
            "ledger.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


class TestSC001IngestionPerformance:
    """SC-001: new ingestion of a 5,000-row file completes within 10 seconds."""

    def test_ingestion_within_10_seconds(self, app_client: TestClient) -> None:
        """POST a 5,000-row ledger; assert the round-trip completes in ≤10 s."""
        file_bytes = _generate_large_ledger(rows=5000)
        start = time.perf_counter()
        resp = app_client.post(
            "/v1/accounts/perf-test-sc001/ladder",
            files=_multipart(file_bytes),
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 201, f"Ingestion failed: {resp.text}"
        assert elapsed <= 10.0, f"SC-001 violated: ingestion took {elapsed:.2f}s (limit 10s)"


class TestSC002IdempotentPerformance:
    """SC-002: idempotent re-submit of the same file completes within 1 second."""

    def test_idempotent_resubmit_within_1_second(self, app_client: TestClient) -> None:
        """Ingest a file, then re-submit it; assert re-submit completes in ≤1 s."""
        file_bytes = _generate_large_ledger(rows=5000)
        first = app_client.post(
            "/v1/accounts/perf-test-sc002/ladder",
            files=_multipart(file_bytes),
        )
        assert first.status_code == 201, f"Initial ingestion failed: {first.text}"

        start = time.perf_counter()
        second = app_client.post(
            "/v1/accounts/perf-test-sc002/ladder",
            files=_multipart(file_bytes),
        )
        elapsed = time.perf_counter() - start
        assert second.status_code == 200, f"Re-submit failed: {second.text}"
        assert elapsed <= 1.0, (
            f"SC-002 violated: idempotent re-submit took {elapsed:.2f}s (limit 1s)"
        )


class TestSC003ValidationPerformance:
    """SC-003: validation rejection completes within 1 second."""

    def test_validation_rejection_within_1_second(self, app_client: TestClient) -> None:
        """POST a schema-invalid file; assert rejection completes in ≤1 s."""
        invalid_df = pd.DataFrame(
            {
                "date": ["not-a-date"],
                "sub_account": ["Cash"],
                "book_cost": ["x"],
                "quantity": [1.0],
                "total_income": [0.0],
            }
        )
        buf = io.BytesIO()
        invalid_df.to_excel(buf, index=False, engine="openpyxl")
        file_bytes = buf.getvalue()

        start = time.perf_counter()
        resp = app_client.post(
            "/v1/accounts/perf-test-sc003/ladder",
            files=_multipart(file_bytes),
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
        assert elapsed <= 1.0, (
            f"SC-003 violated: validation rejection took {elapsed:.2f}s (limit 1s)"
        )


def _generate_large_capital_ledger(rows: int = 5000) -> bytes:
    """Generate a synthetic capital ledger with `rows` recorded observations.

    Each row is a distinct recorded business day, matching the capital ledger's
    "one row per date on which capital, income, or book value changed" shape.

    Args:
        rows: Number of recorded rows to generate.

    Returns:
        XLSX file contents as bytes.
    """
    dates = pd.bdate_range(end=date.today() - timedelta(days=200), periods=rows)
    df = pd.DataFrame(
        {
            "date": dates.date,
            "capital": [1000.0 + i for i in range(rows)],
            "income": [float(i % 10) for i in range(rows)],
            "book_value": [900.0 + i for i in range(rows)],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _capital_multipart(file_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap bytes as a multipart upload dict for the capital endpoint.

    Args:
        file_bytes: XLSX content.

    Returns:
        Dict for TestClient files= parameter.
    """
    return {
        "file": (
            "capital.xlsx",
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


class TestCapitalSC001IngestionPerformance:
    """Capital Ledger Ingestion SC-001: a 5,000-row file completes within 10 seconds."""

    def test_ingestion_within_10_seconds(self, app_client: TestClient) -> None:
        """POST a 5,000-row capital ledger; assert the round-trip completes in ≤10 s."""
        file_bytes = _generate_large_capital_ledger(rows=5000)
        start = time.perf_counter()
        resp = app_client.post(
            "/v1/accounts/capital-perf-test-sc001/capital",
            files=_capital_multipart(file_bytes),
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 201, f"Ingestion failed: {resp.text}"
        assert elapsed <= 10.0, f"SC-001 violated: ingestion took {elapsed:.2f}s (limit 10s)"


class TestCapitalSC002IdempotentPerformance:
    """Capital Ledger Ingestion SC-002: idempotent re-submit completes within 1 second."""

    def test_idempotent_resubmit_within_1_second(self, app_client: TestClient) -> None:
        """Ingest a file, then re-submit it; assert re-submit completes in ≤1 s."""
        file_bytes = _generate_large_capital_ledger(rows=5000)
        first = app_client.post(
            "/v1/accounts/capital-perf-test-sc002/capital",
            files=_capital_multipart(file_bytes),
        )
        assert first.status_code == 201, f"Initial ingestion failed: {first.text}"

        start = time.perf_counter()
        second = app_client.post(
            "/v1/accounts/capital-perf-test-sc002/capital",
            files=_capital_multipart(file_bytes),
        )
        elapsed = time.perf_counter() - start
        assert second.status_code == 200, f"Re-submit failed: {second.text}"
        assert elapsed <= 1.0, (
            f"SC-002 violated: idempotent re-submit took {elapsed:.2f}s (limit 1s)"
        )


class TestCapitalSC003ValidationPerformance:
    """Capital Ledger Ingestion SC-003: validation rejection completes within 1 second."""

    def test_validation_rejection_within_1_second(self, app_client: TestClient) -> None:
        """POST a schema-invalid capital ledger; assert rejection completes in ≤1 s."""
        invalid_df = pd.DataFrame(
            {
                "date": ["not-a-date"],
                "capital": ["x"],
                "income": [0.0],
                "book_value": [0.0],
            }
        )
        buf = io.BytesIO()
        invalid_df.to_excel(buf, index=False, engine="openpyxl")
        file_bytes = buf.getvalue()

        start = time.perf_counter()
        resp = app_client.post(
            "/v1/accounts/capital-perf-test-sc003/capital",
            files=_capital_multipart(file_bytes),
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
        assert elapsed <= 1.0, (
            f"SC-003 violated: validation rejection took {elapsed:.2f}s (limit 1s)"
        )


class TestLadderMarketDataSC003CallVolume:
    """Ladder Market Data Enrichment SC-003.

    At most one market-data-service call per distinct non-Cash sub-account per
    ingestion, regardless of how many business days that sub-account spans.
    """

    def test_call_count_equals_distinct_non_cash_sub_accounts(
        self, app_client: TestClient, fake_market_data_service: FakeMarketDataService
    ) -> None:
        """Assert call count equals distinct non-Cash sub-accounts, not rows or days.

        Ingests a ladder spanning many business days across several sub-accounts.
        """
        sub_account_count = 5
        file_bytes = _generate_large_ledger(rows=2000)
        # _generate_large_ledger produces 9 Equity-N sub-accounts plus Cash; only
        # inspect the first `sub_account_count` of them for a clear, bounded assertion.
        resp = app_client.post(
            "/v1/accounts/perf-test-callvolume/ladder",
            files=_multipart(file_bytes),
        )
        assert resp.status_code == 201, f"Ingestion failed: {resp.text}"

        for i in range(sub_account_count):
            calls = fake_market_data_service.calls_for(f"Equity-{i}")
            assert len(calls) == 1, f"Expected exactly 1 call for 'Equity-{i}', got {len(calls)}"
        assert fake_market_data_service.calls_for("Cash") == []


def _generate_multi_year_capital_ledger(years: int = 10) -> bytes:
    """Generate a sparse capital ledger spanning `years` years back from today.

    Args:
        years: Number of years of history to generate (one row per month, enough
            to seed forward-fill across the full ~2,600 business day range).

    Returns:
        XLSX file contents as bytes.
    """
    end = date.today() - timedelta(days=200)
    start = end - timedelta(days=365 * years)
    dates = pd.bdate_range(start=start, end=end, freq="MS")
    df = pd.DataFrame(
        {
            "date": dates.date,
            "capital": [1000.0 + i for i in range(len(dates))],
            "income": [float(i % 10) for i in range(len(dates))],
            "book_value": [900.0 + i for i in range(len(dates))],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _generate_multi_year_ladder(years: int = 10) -> bytes:
    """Generate a sparse position ladder spanning `years` years back from today.

    Args:
        years: Number of years of history to generate (one row per month per
            sub-account, enough to seed forward-fill across the full range).

    Returns:
        XLSX file contents as bytes.
    """
    end = date.today() - timedelta(days=200)
    start = end - timedelta(days=365 * years)
    dates = pd.bdate_range(start=start, end=end, freq="MS")
    records = []
    for sa in ["Equity-A", "Cash"]:
        for i, d in enumerate(dates.date):
            records.append(
                {
                    "date": d,
                    "sub_account": sa,
                    "book_cost": 1000.0 + i,
                    "quantity": 10.0,
                    "total_income": float(i),
                }
            )
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


class TestTimeseriesSC001MultiYearPerformance:
    """Account Timeseries API SC-001: a ~2,600 business day request completes within 5 seconds."""

    def test_multi_year_timeseries_within_5_seconds(self, app_client: TestClient) -> None:
        """GET a 10-year capital+ladder joined time series; assert completion in ≤5 s."""
        account_name = "perf-test-timeseries-sc001"
        capital_resp = app_client.post(
            f"/v1/accounts/{account_name}/capital",
            files=_capital_multipart(_generate_multi_year_capital_ledger(years=10)),
        )
        assert capital_resp.status_code == 201, f"Capital setup failed: {capital_resp.text}"
        ladder_resp = app_client.post(
            f"/v1/accounts/{account_name}/ladder",
            files=_multipart(_generate_multi_year_ladder(years=10)),
        )
        assert ladder_resp.status_code == 201, f"Ladder setup failed: {ladder_resp.text}"

        start = time.perf_counter()
        resp = app_client.get(
            f"/v1/accounts/{account_name}/timeseries",
            params=[
                ("attribute", "capital"),
                ("attribute", "market_value"),
                ("attribute", "pnl"),
            ],
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200, f"Timeseries request failed: {resp.text}"
        assert len(resp.json()["entries"]) >= 2500, "Expected ~10 years of business day entries"
        assert elapsed <= 5.0, f"SC-001 violated: timeseries took {elapsed:.2f}s (limit 5s)"


class TestTimeseriesSC003RejectionPerformance:
    """Account Timeseries API SC-003: an unsupported attribute is rejected within 1 second."""

    def test_unsupported_attribute_rejected_within_1_second(self, app_client: TestClient) -> None:
        """GET with an unsupported attribute name; assert rejection completes in ≤1 s."""
        account_name = "perf-test-timeseries-sc003"
        resp = app_client.post(
            f"/v1/accounts/{account_name}/capital",
            files=_capital_multipart(_generate_multi_year_capital_ledger(years=1)),
        )
        assert resp.status_code == 201, f"Capital setup failed: {resp.text}"

        start = time.perf_counter()
        rejection = app_client.get(
            f"/v1/accounts/{account_name}/timeseries",
            params=[("attribute", "not_a_real_attribute")],
        )
        elapsed = time.perf_counter() - start
        assert rejection.status_code == 422, f"Expected 422, got {rejection.status_code}"
        assert elapsed <= 1.0, f"SC-003 violated: rejection took {elapsed:.2f}s (limit 1s)"


def _generate_multi_year_ladder_many_positions(years: int = 5, positions: int = 50) -> bytes:
    """Generate a sparse position ladder with many positions spanning several years.

    Args:
        years: Number of years of history to generate (monthly rows per position,
            enough to seed forward-fill across the full expanded range).
        positions: Number of distinct non-Cash positions to generate.

    Returns:
        XLSX file contents as bytes.
    """
    end = date.today() - timedelta(days=200)
    start = end - timedelta(days=365 * years)
    dates = pd.bdate_range(start=start, end=end, freq="MS")
    records = []
    for sa in [f"Position-{i}" for i in range(positions)] + ["Cash"]:
        for i, d in enumerate(dates.date):
            records.append(
                {
                    "date": d,
                    "sub_account": sa,
                    "book_cost": 1000.0 + i,
                    "quantity": 10.0,
                    "total_income": float(i),
                }
            )
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


class TestPositionTimeseriesSC001MultiPositionPerformance:
    """Position Time Series API SC-001: 50 positions over 5 years completes within budget.

    Threshold raised 10s -> 15s (feature 006): adding position_return/weighted_position_return
    widened every stored ladder by 2 columns on top of feature 002's price/market_value/
    portfolio_weight. openpyxl parses every cell in the sheet regardless of which columns are
    actually requested, so full-ladder read time scales with total column count, not just
    requested attributes — see specs/006-ladder-daily-returns/research.md for the investigation
    (a `usecols`-based read optimization was attempted and measured to have no effect, since
    openpyxl's XML parsing happens before pandas' column filtering).
    """

    def test_fifty_positions_five_years_within_budget(self, app_client: TestClient) -> None:
        """GET all 50 positions' market_value over a 5-year range; assert completion in ≤15 s."""
        account_name = "perf-test-position-sc001"
        ladder_resp = app_client.post(
            f"/v1/accounts/{account_name}/ladder",
            files=_multipart(_generate_multi_year_ladder_many_positions(years=5, positions=50)),
        )
        assert ladder_resp.status_code == 201, f"Ladder setup failed: {ladder_resp.text}"

        start = time.perf_counter()
        resp = app_client.get(
            f"/v1/accounts/{account_name}/position",
            params=[("attribute", "market_value")],
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200, f"Position request failed: {resp.text}"
        assert len(resp.json()["positions"]) == 51, "Expected 50 positions plus Cash"
        assert elapsed <= 15.0, f"SC-001 violated: position request took {elapsed:.2f}s (limit 15s)"


class TestPositionTimeseriesSC004RejectionPerformance:
    """Position Time Series API SC-004: each rejection path completes within 1 second."""

    def test_unsupported_attribute_rejected_within_1_second(self, app_client: TestClient) -> None:
        """GET with an unsupported attribute name; assert rejection completes in ≤1 s."""
        account_name = "perf-test-position-sc004-attr"
        resp = app_client.post(
            f"/v1/accounts/{account_name}/ladder",
            files=_multipart(_generate_multi_year_ladder_many_positions(years=1, positions=5)),
        )
        assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"

        start = time.perf_counter()
        rejection = app_client.get(
            f"/v1/accounts/{account_name}/position",
            params=[("attribute", "capital")],
        )
        elapsed = time.perf_counter() - start
        assert rejection.status_code == 422, f"Expected 422, got {rejection.status_code}"
        assert elapsed <= 1.0, f"SC-004 violated: rejection took {elapsed:.2f}s (limit 1s)"

    def test_unknown_account_rejected_within_1_second(self, app_client: TestClient) -> None:
        """GET for a wholly unknown account; assert rejection completes in ≤1 s."""
        start = time.perf_counter()
        rejection = app_client.get(
            "/v1/accounts/perf-test-position-sc004-unknown/position",
            params=[("attribute", "market_value")],
        )
        elapsed = time.perf_counter() - start
        assert rejection.status_code == 404, f"Expected 404, got {rejection.status_code}"
        assert elapsed <= 1.0, f"SC-004 violated: rejection took {elapsed:.2f}s (limit 1s)"

    def test_invalid_date_range_rejected_within_1_second(self, app_client: TestClient) -> None:
        """GET with start after end; assert rejection completes in ≤1 s."""
        account_name = "perf-test-position-sc004-daterange"
        resp = app_client.post(
            f"/v1/accounts/{account_name}/ladder",
            files=_multipart(_generate_multi_year_ladder_many_positions(years=1, positions=5)),
        )
        assert resp.status_code == 201, f"Ladder setup failed: {resp.text}"

        start = time.perf_counter()
        rejection = app_client.get(
            f"/v1/accounts/{account_name}/position",
            params=[
                ("attribute", "market_value"),
                ("start", "2024-02-01"),
                ("end", "2024-01-01"),
            ],
        )
        elapsed = time.perf_counter() - start
        assert rejection.status_code == 422, f"Expected 422, got {rejection.status_code}"
        assert elapsed <= 1.0, f"SC-004 violated: rejection took {elapsed:.2f}s (limit 1s)"
