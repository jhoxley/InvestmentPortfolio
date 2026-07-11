"""Filesystem repository for storing and retrieving position ladders."""

import contextlib
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel


class AccountMeta(BaseModel):
    """Metadata persisted alongside each account's ladder.xlsx as meta.json."""

    account_name: str
    checksum: str
    row_count: int
    from_date: date
    to_date: date
    sub_accounts: list[str]
    ingested_at: datetime


class LadderRepository:
    """Read/write position ladders to the local filesystem.

    Each account occupies a dedicated subdirectory under data_dir:
        data_dir/{account_name}/ladder.xlsx
        data_dir/{account_name}/meta.json

    Writes are atomic: ladder.xlsx is written to a .tmp file then renamed.
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
        """Return the path to the account's meta.json file.

        Args:
            account_name: The account identifier.

        Returns:
            Path to meta.json.
        """
        return self._account_dir(account_name) / "meta.json"

    def _ladder_path(self, account_name: str) -> Path:
        """Return the path to the account's ladder.xlsx file.

        Args:
            account_name: The account identifier.

        Returns:
            Path to ladder.xlsx.
        """
        return self._account_dir(account_name) / "ladder.xlsx"

    def exists(self, account_name: str) -> bool:
        """Return True if a ladder has been stored for this account.

        Args:
            account_name: The account identifier to check.

        Returns:
            True if both ladder.xlsx and meta.json exist.
        """
        return self._meta_path(account_name).exists()

    def read_meta(self, account_name: str) -> AccountMeta:
        """Load and return the AccountMeta for a stored account.

        Args:
            account_name: The account identifier.

        Returns:
            Populated AccountMeta instance.

        Raises:
            FileNotFoundError: If no meta.json exists for the account.
        """
        path = self._meta_path(account_name)
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return AccountMeta.model_validate(data)

    def write(self, account_name: str, df: pd.DataFrame, meta: AccountMeta) -> None:
        """Persist the ladder DataFrame and metadata for an account.

        Writes ladder.xlsx atomically (via a temporary file + os.replace) then
        writes meta.json. Creates the account directory if it does not exist.

        Args:
            account_name: The account identifier.
            df: The expanded daily position ladder DataFrame.
            meta: The AccountMeta to serialise as meta.json.
        """
        account_dir = self._account_dir(account_name)
        account_dir.mkdir(parents=True, exist_ok=True)

        ladder_path = self._ladder_path(account_name)
        fd, tmp_path = tempfile.mkstemp(dir=account_dir, suffix=".xlsx")
        try:
            os.close(fd)
            df.to_excel(tmp_path, index=False, engine="openpyxl")
            os.replace(tmp_path, ladder_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise

        meta_path = self._meta_path(account_name)
        meta_json = meta.model_dump(mode="json")
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta_json, f, indent=2, default=str)

    def read_ladder_df(self, account_name: str) -> pd.DataFrame:
        """Read back the stored ladder's base columns for re-enrichment on the refresh path.

        Args:
            account_name: The account identifier.

        Returns:
            DataFrame with columns [date, sub_account, book_cost, quantity, total_income],
            dropping price/market_value/portfolio_weight if already present.

        Raises:
            FileNotFoundError: If no ladder file exists for the account.
        """
        path = self._ladder_path(account_name)
        if not path.exists():
            raise FileNotFoundError(f"No ladder file found for account '{account_name}'")
        df = pd.read_excel(path, engine="openpyxl")
        return df[["date", "sub_account", "book_cost", "quantity", "total_income"]]

    def read_xlsx(self, account_name: str) -> Path:
        """Return the path to the stored ladder.xlsx for an account.

        Args:
            account_name: The account identifier.

        Returns:
            Absolute path to ladder.xlsx.

        Raises:
            FileNotFoundError: If the ladder file does not exist.
        """
        path = self._ladder_path(account_name)
        if not path.exists():
            raise FileNotFoundError(f"No ladder file found for account '{account_name}'")
        return path
