"""Unit tests for CapitalRebuildService (014)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.services.rebuild.capital_rebuild_service import CapitalRebuildService

_LAST_KNOWN = date(2026, 9, 23)  # a Wednesday


@pytest.fixture()
def capital_repo(tmp_path: Path) -> CapitalRepository:
    """Return a tmp_path-backed CapitalRepository.

    Returns:
        CapitalRepository ready for use in tests.
    """
    return CapitalRepository(data_dir=tmp_path)


def _seed_capital(repo: CapitalRepository, account_name: str) -> None:
    """Write a minimal 'ingested' capital ledger ending at _LAST_KNOWN.

    Args:
        repo: CapitalRepository to write through.
        account_name: Target account name.
    """
    df = pd.DataFrame(
        {
            "date": [_LAST_KNOWN],
            "capital": [1000.0],
            "income": [10.0],
            "book_value": [800.0],
            "provenance": ["ingested"],
        }
    )
    meta = CapitalMeta(
        account_name=account_name,
        checksum="deadbeef",
        row_count=1,
        from_date=_LAST_KNOWN,
        to_date=_LAST_KNOWN,
        ingested_at=datetime.now(UTC),
    )
    repo.write(account_name, df, meta)


def _read_normalised(repo: CapitalRepository, account_name: str) -> pd.DataFrame:
    """Read a capital ledger back with its date column normalised to python date objects.

    Returns:
        The full stored capital ledger with `date` as python date objects.
    """
    df = repo.read_df(account_name)
    return df.assign(date=pd.to_datetime(df["date"]).dt.date)


class TestExtensionCarriesValuesForward:
    """The rebuild extends through the target end, carrying the last known values forward."""

    def test_extension_carries_values_forward(self, capital_repo: CapitalRepository) -> None:
        """New rows repeat the last known capital/income/book_value exactly."""
        account_name = "acct-capital"
        _seed_capital(capital_repo, account_name)
        target_end = date(2026, 9, 25)

        CapitalRebuildService(capital_repo).rebuild(account_name, target_end)

        result = _read_normalised(capital_repo, account_name)
        new_rows = result[result["date"] > _LAST_KNOWN]
        assert not new_rows.empty
        assert (new_rows["capital"] == 1000.0).all()
        assert (new_rows["income"] == 10.0).all()
        assert (new_rows["book_value"] == 800.0).all()
        assert (new_rows["provenance"] == "projected").all()
        assert result["date"].max() == target_end


class TestMetaIsAdvanced:
    """CapitalMeta.to_date and rebuilt_at are updated after a rebuild."""

    def test_meta_is_advanced(self, capital_repo: CapitalRepository) -> None:
        """to_date advances to the target end and rebuilt_at is set."""
        account_name = "acct-capital-meta"
        _seed_capital(capital_repo, account_name)
        target_end = date(2026, 9, 25)

        CapitalRebuildService(capital_repo).rebuild(account_name, target_end)

        meta = capital_repo.read_meta(account_name)
        assert meta.to_date == target_end
        assert meta.rebuilt_at is not None


class TestNoOpWhenAlreadyCovered:
    """Nothing changes when the target end is already covered."""

    def test_noop_when_target_end_not_after_last_known_date(
        self, capital_repo: CapitalRepository
    ) -> None:
        """A target end equal to the last known date leaves the ledger unchanged."""
        account_name = "acct-capital-noop"
        _seed_capital(capital_repo, account_name)

        CapitalRebuildService(capital_repo).rebuild(account_name, _LAST_KNOWN)

        meta = capital_repo.read_meta(account_name)
        assert meta.rebuilt_at is None
        assert meta.to_date == _LAST_KNOWN
