from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pandas as pd

from src.modes.consolidate_journals.constants import (
    JOURNAL_COLUMNS,
    RE_BUY,
    RE_SELL,
)
from src.modes.consolidate_journals.schema import JournalEvent

_logger = logging.getLogger("pipeline.modes.consolidate_journals.journal_store")


def _is_transaction_reference(reference: str) -> bool:
    return bool(RE_BUY.match(reference) or RE_SELL.match(reference))


class JournalStore:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    @classmethod
    def load(cls, path: Path) -> JournalStore:
        if path.exists():
            df = pd.read_excel(path, engine="openpyxl", dtype=str)
            missing = [c for c in JOURNAL_COLUMNS if c not in df.columns]
            if missing:
                raise ValueError(f"Consolidated journal at {path} is missing columns: {missing}")
            df = df[JOURNAL_COLUMNS]
            _logger.info("Loaded existing journal", extra={"path": str(path), "rows": len(df)})
        else:
            df = pd.DataFrame(columns=JOURNAL_COLUMNS)
            _logger.info("No existing journal found; starting empty", extra={"path": str(path)})
        return cls(df)

    @property
    def row_count(self) -> int:
        return len(self._df)

    def merge(self, events: list[JournalEvent]) -> tuple[int, int]:
        if not events:
            return 0, 0

        new_rows = pd.DataFrame(
            [
                {
                    "date": str(e.date),
                    "account": e.account,
                    "sub_account": e.sub_account,
                    "action": str(e.action),
                    "reference": e.reference,
                    "value": str(e.value),
                    "quantity": str(e.quantity) if e.quantity is not None else "",
                }
                for e in events
            ]
        )

        if self._df.empty:
            self._df = new_rows.copy()
            _logger.info("Merged events into empty store", extra={"inserted": len(new_rows)})
            return len(new_rows), 0

        inserted_count = 0
        merged_count = 0

        to_append: list[pd.Series[str]] = []
        for _, new_row in new_rows.iterrows():
            ref = str(new_row["reference"])
            if _is_transaction_reference(ref):
                mask = (self._df["date"] == new_row["date"]) & (
                    self._df["reference"] == new_row["reference"]
                )
            else:
                mask = (
                    (self._df["date"] == new_row["date"])
                    & (self._df["action"] == new_row["action"])
                    & (self._df["value"] == new_row["value"])
                )

            if mask.any():
                merged_count += 1
            else:
                to_append.append(new_row)
                inserted_count += 1

        if to_append:
            self._df = pd.concat([self._df, pd.DataFrame(to_append)], ignore_index=True)

        _logger.info(
            "Merge complete",
            extra={"inserted": inserted_count, "merged": merged_count},
        )
        return inserted_count, merged_count

    def save(self, path: Path) -> None:
        tmp_fd, tmp_path_str = tempfile.mkstemp(
            suffix=".xlsx", dir=path.parent, prefix=".journal_tmp_"
        )
        tmp_path = Path(tmp_path_str)
        try:
            import os

            os.close(tmp_fd)
            self._df[JOURNAL_COLUMNS].to_excel(tmp_path, index=False, engine="openpyxl")
            tmp_path.replace(path)
            _logger.info("Journal saved", extra={"path": str(path), "rows": len(self._df)})
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
