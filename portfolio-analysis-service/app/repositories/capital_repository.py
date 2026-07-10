"""Filesystem repository for storing and retrieving capital ledgers."""

import contextlib
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel


class CapitalMeta(BaseModel):
    """Metadata persisted alongside each account's capital.xlsx as capital_meta.json."""

    account_name: str
    checksum: str
    row_count: int
    from_date: date
    to_date: date
    ingested_at: datetime


class CapitalRepository:
    """Read/write capital ledgers to the local filesystem.

    Each account occupies a dedicated subdirectory under data_dir:
        data_dir/{account_name}/capital.xlsx
        data_dir/{account_name}/capital_meta.json

    These files are independent of the same account's ladder.xlsx/meta.json pair.
    Writes are atomic: capital.xlsx is written to a .tmp file then renamed.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialise the repository with the base data directory.

        Args:
            data_dir: Root directory under which per-account subdirectories are created.
        """
        self._data_dir = data_dir

    def _account_dir(self, account_name: str) -> Path:
        """Return the directory path for a given account.

        Args:
            account_name: The account identifier.

        Returns:
            Path to the account-specific subdirectory.
        """
        return self._data_dir / account_name

    def _meta_path(self, account_name: str) -> Path:
        """Return the path to the account's capital_meta.json file.

        Args:
            account_name: The account identifier.

        Returns:
            Path to capital_meta.json.
        """
        return self._account_dir(account_name) / "capital_meta.json"

    def _xlsx_path(self, account_name: str) -> Path:
        """Return the path to the account's capital.xlsx file.

        Args:
            account_name: The account identifier.

        Returns:
            Path to capital.xlsx.
        """
        return self._account_dir(account_name) / "capital.xlsx"

    def exists(self, account_name: str) -> bool:
        """Return True if a capital ledger has been stored for this account.

        Args:
            account_name: The account identifier to check.

        Returns:
            True if both capital.xlsx and capital_meta.json exist.
        """
        return self._meta_path(account_name).exists()

    def read_meta(self, account_name: str) -> CapitalMeta:
        """Load and return the CapitalMeta for a stored account.

        Args:
            account_name: The account identifier.

        Returns:
            Populated CapitalMeta instance.

        Raises:
            FileNotFoundError: If no capital_meta.json exists for the account.
        """
        path = self._meta_path(account_name)
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return CapitalMeta.model_validate(data)

    def write(self, account_name: str, df: pd.DataFrame, meta: CapitalMeta) -> None:
        """Persist the capital ledger DataFrame and metadata for an account.

        Writes capital.xlsx atomically (via a temporary file + os.replace) then writes
        capital_meta.json. Creates the account directory if it does not exist.

        Args:
            account_name: The account identifier.
            df: The expanded daily capital ledger DataFrame.
            meta: The CapitalMeta to serialise as capital_meta.json.
        """
        account_dir = self._account_dir(account_name)
        account_dir.mkdir(parents=True, exist_ok=True)

        xlsx_path = self._xlsx_path(account_name)
        fd, tmp_path = tempfile.mkstemp(dir=account_dir, suffix=".xlsx")
        try:
            os.close(fd)
            df.to_excel(tmp_path, index=False, engine="openpyxl")
            os.replace(tmp_path, xlsx_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise

        self.write_meta(account_name, meta)

    def write_meta(self, account_name: str, meta: CapitalMeta) -> None:
        """Persist only the capital_meta.json for an account, without touching capital.xlsx.

        Used by the checksum-match refresh path, where the stored XLSX is provably
        unchanged and only the ingestion timestamp needs updating.

        Args:
            account_name: The account identifier.
            meta: The CapitalMeta to serialise as capital_meta.json.
        """
        account_dir = self._account_dir(account_name)
        account_dir.mkdir(parents=True, exist_ok=True)
        meta_path = self._meta_path(account_name)
        meta_json = meta.model_dump(mode="json")
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta_json, f, indent=2, default=str)

    def read_xlsx(self, account_name: str) -> Path:
        """Return the path to the stored capital.xlsx for an account.

        Args:
            account_name: The account identifier.

        Returns:
            Absolute path to capital.xlsx.

        Raises:
            FileNotFoundError: If the capital ledger file does not exist.
        """
        path = self._xlsx_path(account_name)
        if not path.exists():
            raise FileNotFoundError(f"No capital ledger file found for account '{account_name}'")
        return path
