from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import pandas as pd

from src.modes.consolidate_journals.constants import (
    JOURNAL_COLUMNS,
    NUMBER_FORMAT_QUANTITY,
    NUMBER_FORMAT_VALUE,
    OFFSET_SUFFIX,
    RE_BUY,
    RE_OFFSET,
    RE_SELL,
)
from src.modes.consolidate_journals.schema import ActionType, JournalEvent

_logger = logging.getLogger("pipeline.modes.consolidate_journals.journal_store")

_NUMERIC_COLUMNS = ("value", "quantity")


def _is_transaction_reference(reference: str) -> bool:
    return bool(RE_BUY.match(reference) or RE_SELL.match(reference) or RE_OFFSET.match(reference))


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
            for col in _NUMERIC_COLUMNS:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            _logger.info("Loaded existing journal", extra={"path": str(path), "rows": len(df)})
        else:
            df = pd.DataFrame(columns=JOURNAL_COLUMNS)
            _logger.info("No existing journal found; starting empty", extra={"path": str(path)})
        return cls(df)

    @property
    def row_count(self) -> int:
        return len(self._df)

    def missing_offset_trades(self) -> pd.DataFrame:
        """Return buy/sell rows that have no corresponding offset row in the journal."""
        if self._df.empty:
            return self._df.iloc[0:0]
        trade_mask = self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value})
        existing_offset_refs: set[str] = set(
            self._df.loc[self._df["action"] == ActionType.TRADING.value, "reference"]
        )
        needs_offset = trade_mask & ~self._df["reference"].apply(
            lambda ref: (str(ref) + OFFSET_SUFFIX) in existing_offset_refs
        )
        return self._df[needs_offset].copy()

    def rectify_offsets(self) -> int:
        """Update any offset rows whose value or quantity differs from the originating trade.

        Returns the count of offset rows corrected in place.
        """
        if self._df.empty:
            return 0

        trade_mask = self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value})
        trades = self._df[trade_mask]
        corrected = 0

        for _, trade in trades.iterrows():
            offset_ref = str(trade["reference"]) + OFFSET_SUFFIX
            offset_mask = self._df["reference"] == offset_ref
            if not offset_mask.any():
                continue
            trade_value = float(trade["value"])
            existing_value = float(self._df.loc[offset_mask, "value"].iloc[0])
            if existing_value != trade_value:
                self._df.loc[offset_mask, "value"] = trade_value
                self._df.loc[offset_mask, "quantity"] = trade_value
                corrected += 1

        if corrected:
            _logger.info(
                "Stale offsets rectified",
                extra={"rectified_offsets": corrected},
            )
        return corrected

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
                    "value": float(e.value),
                    "quantity": float(e.quantity) if e.quantity is not None else None,
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
            os.close(tmp_fd)
            value_col = JOURNAL_COLUMNS.index("value") + 1
            qty_col = JOURNAL_COLUMNS.index("quantity") + 1

            with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
                self._df[JOURNAL_COLUMNS].to_excel(writer, index=False)
                ws = writer.sheets["Sheet1"]
                for row in ws.iter_rows(min_row=2, min_col=value_col, max_col=value_col):
                    for cell in row:
                        cell.number_format = NUMBER_FORMAT_VALUE
                for row in ws.iter_rows(min_row=2, min_col=qty_col, max_col=qty_col):
                    for cell in row:
                        cell.number_format = NUMBER_FORMAT_QUANTITY

            tmp_path.replace(path)
            _logger.info("Journal saved", extra={"path": str(path), "rows": len(self._df)})
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
