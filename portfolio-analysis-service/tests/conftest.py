"""Shared pytest fixtures for the portfolio analysis service test suite."""

import io
from collections.abc import Generator
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import DataSettings, Settings, get_settings
from app.main import app


def _make_settings(data_dir: Path) -> Settings:
    """Create a Settings instance pointing at the given data directory.

    Args:
        data_dir: Temporary directory to use as the data store.

    Returns:
        Settings instance with data.directory overridden.
    """
    return Settings(data=DataSettings(directory=data_dir))


@pytest.fixture()
def app_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Provide a TestClient backed by a temporary data directory.

    Overrides the get_settings dependency so that the app writes to tmp_path
    rather than the real data/ directory.

    Args:
        tmp_path: pytest-provided temporary directory.

    Yields:
        Configured FastAPI TestClient.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    settings = _make_settings(data_dir)

    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_ledger_df() -> pd.DataFrame:
    """Return a minimal valid sub-account ledger DataFrame.

    Contains two sub-accounts ('Cash' and 'Equity A') over two dates,
    both well before T-2, so the expansion range is non-empty.

    Returns:
        DataFrame with columns: date, sub_account, book_cost, quantity, total_income.
    """
    today = date.today()
    d1 = today - timedelta(days=30)
    d2 = today - timedelta(days=20)
    return pd.DataFrame(
        {
            "date": [d1, d1, d2, d2],
            "sub_account": ["Cash", "Equity A", "Cash", "Equity A"],
            "book_cost": [1000.0, 500.0, 1000.0, 500.0],
            "quantity": [1000.0, 10.0, 1000.0, 10.0],
            "total_income": [0.0, 5.0, 0.0, 10.0],
        }
    )


@pytest.fixture()
def sample_ledger_bytes(sample_ledger_df: pd.DataFrame) -> bytes:
    """Serialise the sample ledger DataFrame to XLSX bytes.

    Args:
        sample_ledger_df: The sample ledger fixture.

    Returns:
        XLSX file contents as bytes.
    """
    buf = io.BytesIO()
    sample_ledger_df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


@pytest.fixture()
def sample_ledger_file(sample_ledger_bytes: bytes) -> dict[str, tuple[str, bytes, str]]:
    """Wrap XLSX bytes as a multipart file dict for TestClient POSTs.

    Args:
        sample_ledger_bytes: Raw XLSX file bytes.

    Returns:
        Dict suitable for use as the 'files' argument to TestClient.post().
    """
    return {
        "file": (
            "ledger.xlsx",
            sample_ledger_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
