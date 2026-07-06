"""Performance smoke tests verifying SC-001, SC-002, and SC-003 timing targets."""

import io
import time
from datetime import date, timedelta

import pandas as pd
from fastapi.testclient import TestClient


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
