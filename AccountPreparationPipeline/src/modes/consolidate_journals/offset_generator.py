from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd

from src.modes.consolidate_journals.constants import CASH_SUB_ACCOUNT, OFFSET_SUFFIX
from src.modes.consolidate_journals.schema import ActionType, JournalEvent


class OffsetGenerator:
    """Generate synthetic Cash offset entries for buy/sell trade events."""

    def generate(self, events: list[JournalEvent]) -> list[JournalEvent]:
        """Return one Cash offset JournalEvent for each buy/sell event in `events`."""
        return [
            self._make_offset(e) for e in events if e.action in (ActionType.BUY, ActionType.SELL)
        ]

    def generate_from_df(self, trades: pd.DataFrame) -> list[JournalEvent]:
        """Return offset events for all rows in `trades` (a buy/sell DataFrame slice)."""
        return self.generate(self._df_to_events(trades))

    def _df_to_events(self, df: pd.DataFrame) -> list[JournalEvent]:
        result: list[JournalEvent] = []
        for _, row in df.iterrows():
            quantity = row["quantity"]
            result.append(
                JournalEvent(
                    date=datetime.date.fromisoformat(str(row["date"])[:10]),
                    account=str(row["account"]),
                    sub_account=str(row["sub_account"]),
                    action=ActionType(str(row["action"])),
                    reference=str(row["reference"]),
                    value=Decimal(str(row["value"])),
                    quantity=Decimal(str(quantity)) if pd.notna(quantity) else None,
                )
            )
        return result

    def _make_offset(self, event: JournalEvent) -> JournalEvent:
        return JournalEvent(
            date=event.date,
            account=event.account,
            sub_account=CASH_SUB_ACCOUNT,
            action=ActionType.TRADING,
            reference=event.reference + OFFSET_SUFFIX,
            value=-event.value,
            quantity=-event.value,  # Cash quantity always mirrors value
        )
