from __future__ import annotations

import logging

import pandas as pd

from src.modes.consolidate_journals.constants import JOURNAL_COLUMNS
from src.modes.create_ledger.constants import BUY_SELL_ACTIONS, CASH_SUB_ACCOUNT, SELL_ACTION

_logger = logging.getLogger("pipeline.modes.create_ledger.engine")


class LedgerEngine:
    def run(self, input_df: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in JOURNAL_COLUMNS if c not in input_df.columns]
        if missing:
            raise ValueError(f"Input journal is missing columns: {missing}")

        df = input_df[JOURNAL_COLUMNS].copy()

        if df.empty:
            return df

        # Cash rule: copy value to quantity where sub_account is Cash and quantity is blank
        cash_blank = (df["sub_account"] == CASH_SUB_ACCOUNT) & df["quantity"].isna()
        df.loc[cash_blank, "quantity"] = df.loc[cash_blank, "value"]
        # Ensure float dtype after conditional assignment (column may be object if all-None input)
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

        # Sign-adjust value: negate for buy/sell
        df["adj_value"] = df["value"].where(~df["action"].isin(BUY_SELL_ACTIONS), -df["value"])

        # Sign-adjust quantity: negate for sell
        df["adj_quantity"] = df["quantity"].where(df["action"] != SELL_ACTION, -df["quantity"])

        # Stable sort preserves within-date input order
        df = df.sort_values(["account", "sub_account", "date"], kind="stable").reset_index(
            drop=True
        )

        # Cumulative sums per (account, sub_account) position
        df["value"] = df.groupby(["account", "sub_account"], sort=False)["adj_value"].cumsum()
        df["quantity"] = df.groupby(["account", "sub_account"], sort=False)["adj_quantity"].cumsum()

        df = df.drop(columns=["adj_value", "adj_quantity"])

        _logger.debug("Ledger computation complete", extra={"rows": len(df)})
        return df[JOURNAL_COLUMNS]
