from __future__ import annotations

import logging

import pandas as pd

from src.modes.create_capital_ledger.constants import (
    CAPITAL_ACTION_BUY,
    CAPITAL_ACTION_DEPOSIT,
    CAPITAL_ACTION_INCOME,
    CAPITAL_ACTION_SELL,
    CAPITAL_COL_BOOK_VALUE,
    CAPITAL_COL_CAPITAL,
    CAPITAL_COL_DATE,
    CAPITAL_COL_INCOME,
    CAPITAL_LEDGER_ACTIONS,
    CAPITAL_LEDGER_OUTPUT_COLUMNS,
)
from src.modes.create_ledger.constants import (
    LEDGER_COL_TRANSACTION_ID,
    LEDGER_COL_TRANSACTION_VALUE,
)

_logger = logging.getLogger("pipeline.modes.create_capital_ledger.engine")

_REQUIRED_COLUMNS = {LEDGER_COL_TRANSACTION_ID, "date", "action", LEDGER_COL_TRANSACTION_VALUE}

_CAPITAL_CONTRIB = "capital_contrib"
_INCOME_CONTRIB = "income_contrib"
_BV_CONTRIB = "bv_contrib"


class CapitalLedgerEngine:
    def run(self, ledger_df: pd.DataFrame) -> pd.DataFrame:
        missing = _REQUIRED_COLUMNS - set(ledger_df.columns)
        if missing:
            raise ValueError(f"Input ledger is missing required columns: {sorted(missing)}")

        df = ledger_df.copy()
        df[LEDGER_COL_TRANSACTION_ID] = df[LEDGER_COL_TRANSACTION_ID].astype(str)
        df = df.sort_values(LEDGER_COL_TRANSACTION_ID, kind="stable")

        df = df[df["action"].isin(CAPITAL_LEDGER_ACTIONS)].copy()

        if df.empty:
            return pd.DataFrame(columns=CAPITAL_LEDGER_OUTPUT_COLUMNS)

        _logger.debug("Engine processing %d qualifying rows", len(df))

        tv = df[LEDGER_COL_TRANSACTION_VALUE]
        action = df["action"]

        df[_CAPITAL_CONTRIB] = tv.where(action == CAPITAL_ACTION_DEPOSIT, other=0.0)
        df[_INCOME_CONTRIB] = tv.where(action == CAPITAL_ACTION_INCOME, other=0.0)
        bv_mask = action.isin({CAPITAL_ACTION_BUY, CAPITAL_ACTION_SELL})
        df[_BV_CONTRIB] = tv.where(bv_mask, other=0.0)

        contrib_cols = [_CAPITAL_CONTRIB, _INCOME_CONTRIB, _BV_CONTRIB]
        grouped = df.groupby(CAPITAL_COL_DATE, sort=False)[contrib_cols].sum()

        grouped[CAPITAL_COL_CAPITAL] = grouped[_CAPITAL_CONTRIB].cumsum().fillna(0.0)
        grouped[CAPITAL_COL_INCOME] = grouped[_INCOME_CONTRIB].cumsum().fillna(0.0)
        grouped[CAPITAL_COL_BOOK_VALUE] = grouped[_BV_CONTRIB].cumsum().fillna(0.0)

        out_cols = [CAPITAL_COL_CAPITAL, CAPITAL_COL_INCOME, CAPITAL_COL_BOOK_VALUE]
        result = grouped[out_cols].reset_index()
        result = result.rename(columns={"index": CAPITAL_COL_DATE})

        return result[CAPITAL_LEDGER_OUTPUT_COLUMNS]
