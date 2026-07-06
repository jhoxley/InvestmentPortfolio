from __future__ import annotations

import pandas as pd

from src.modes.create_subaccount_ledger.constants import (
    ACTION_DIVIDEND,
    CASH_SUB_ACCOUNT,
    EQUITY_ACTIONS,
    LEDGER_COL_ACTION,
    LEDGER_COL_DATE,
    LEDGER_COL_SUB_ACCOUNT,
    LEDGER_COL_TQ,
    LEDGER_COL_TV,
    OUT_COL_BOOK_COST,
    OUT_COL_DATE,
    OUT_COL_QUANTITY,
    OUT_COL_SUB_ACCOUNT,
    OUT_COL_TOTAL_INCOME,
    OUTPUT_COLUMNS,
)


class SubAccountLedgerEngine:
    def run(
        self,
        capital_dfs: list[pd.DataFrame],
        income_dfs: list[pd.DataFrame],
    ) -> pd.DataFrame:
        all_dfs = capital_dfs + income_dfs
        if not all_dfs:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        pool = pd.concat(all_dfs, ignore_index=True)

        equity_result = self._pass1_equity(pool)
        income_result = self._pass2_dividend(pool)
        cash_result = self._pass3_cash(capital_dfs)

        merged = self._merge(equity_result, income_result, cash_result)
        return merged

    # ------------------------------------------------------------------
    # Pass 1: equity positions — buy / sell / lodgement
    # ------------------------------------------------------------------

    def _pass1_equity(self, pool: pd.DataFrame) -> pd.DataFrame:
        mask = pool[LEDGER_COL_ACTION].isin(EQUITY_ACTIONS) & (
            pool[LEDGER_COL_SUB_ACCOUNT] != CASH_SUB_ACCOUNT
        )
        eq = pool[mask].copy()
        if eq.empty:
            return pd.DataFrame(columns=[OUT_COL_DATE, OUT_COL_SUB_ACCOUNT, "_bv", "_qty"])

        # lodgement TV is negative; negate to get positive book_cost contribution
        def _bv_contrib(r: pd.Series) -> float:
            tv = float(r[LEDGER_COL_TV])
            return -tv if r[LEDGER_COL_ACTION] == "lodgement" else tv

        eq["_bv"] = eq.apply(_bv_contrib, axis=1)
        eq["_qty"] = eq[LEDGER_COL_TQ]

        grouped = (
            eq.groupby([LEDGER_COL_DATE, LEDGER_COL_SUB_ACCOUNT], sort=True)[["_bv", "_qty"]]
            .sum()
            .reset_index()
        )
        grouped = grouped.sort_values([LEDGER_COL_DATE, LEDGER_COL_SUB_ACCOUNT])

        grouped[OUT_COL_BOOK_COST] = grouped.groupby(LEDGER_COL_SUB_ACCOUNT, sort=False)[
            "_bv"
        ].cumsum()
        grouped[OUT_COL_QUANTITY] = grouped.groupby(LEDGER_COL_SUB_ACCOUNT, sort=False)[
            "_qty"
        ].cumsum()

        return grouped[
            [LEDGER_COL_DATE, LEDGER_COL_SUB_ACCOUNT, OUT_COL_BOOK_COST, OUT_COL_QUANTITY]
        ]

    # ------------------------------------------------------------------
    # Pass 2: dividend income
    # ------------------------------------------------------------------

    def _pass2_dividend(self, pool: pd.DataFrame) -> pd.DataFrame:
        mask = (pool[LEDGER_COL_ACTION] == ACTION_DIVIDEND) & (
            pool[LEDGER_COL_SUB_ACCOUNT] != CASH_SUB_ACCOUNT
        )
        div = pool[mask].copy()
        if div.empty:
            return pd.DataFrame(columns=[OUT_COL_DATE, OUT_COL_SUB_ACCOUNT, OUT_COL_TOTAL_INCOME])

        div["_inc"] = div[LEDGER_COL_TV]
        grouped = (
            div.groupby([LEDGER_COL_DATE, LEDGER_COL_SUB_ACCOUNT], sort=True)["_inc"]
            .sum()
            .reset_index()
        )
        grouped = grouped.sort_values([LEDGER_COL_DATE, LEDGER_COL_SUB_ACCOUNT])
        grouped[OUT_COL_TOTAL_INCOME] = grouped.groupby(LEDGER_COL_SUB_ACCOUNT, sort=False)[
            "_inc"
        ].cumsum()
        return grouped[[LEDGER_COL_DATE, LEDGER_COL_SUB_ACCOUNT, OUT_COL_TOTAL_INCOME]]

    # ------------------------------------------------------------------
    # Pass 3: Cash balance (capital_dfs only)
    # ------------------------------------------------------------------

    def _pass3_cash(self, capital_dfs: list[pd.DataFrame]) -> pd.DataFrame:
        if not capital_dfs:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        capital_pool = pd.concat(capital_dfs, ignore_index=True)
        cash = capital_pool[capital_pool[LEDGER_COL_SUB_ACCOUNT] == CASH_SUB_ACCOUNT].copy()
        if cash.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        grouped = cash.groupby(LEDGER_COL_DATE, sort=True)[LEDGER_COL_TV].sum().reset_index()
        grouped = grouped.sort_values(LEDGER_COL_DATE)
        grouped["_cash_balance"] = grouped[LEDGER_COL_TV].cumsum()

        result = pd.DataFrame(
            {
                OUT_COL_DATE: grouped[LEDGER_COL_DATE].values,
                OUT_COL_SUB_ACCOUNT: CASH_SUB_ACCOUNT,
                OUT_COL_BOOK_COST: grouped["_cash_balance"].values,
                OUT_COL_QUANTITY: grouped["_cash_balance"].values,
                OUT_COL_TOTAL_INCOME: 0.0,
            }
        )
        return result

    # ------------------------------------------------------------------
    # Merge all three passes
    # ------------------------------------------------------------------

    def _merge(
        self,
        equity: pd.DataFrame,
        income: pd.DataFrame,
        cash: pd.DataFrame,
    ) -> pd.DataFrame:
        # Combine equity and income via outer join on (date, sub_account).
        # After joining, forward-fill book_cost and quantity within each sub_account
        # so that dividend-only dates carry the last cumulative equity value.
        if equity.empty and income.empty:
            equity_income: pd.DataFrame = pd.DataFrame(columns=OUTPUT_COLUMNS)
        elif equity.empty:
            equity_income = income.copy()
            equity_income[OUT_COL_BOOK_COST] = 0.0
            equity_income[OUT_COL_QUANTITY] = 0.0
        elif income.empty:
            equity_income = equity.copy()
            equity_income[OUT_COL_TOTAL_INCOME] = 0.0
        else:
            merged = pd.merge(
                equity,
                income,
                on=[OUT_COL_DATE, OUT_COL_SUB_ACCOUNT],
                how="outer",
            )
            merged = merged.sort_values([OUT_COL_DATE, OUT_COL_SUB_ACCOUNT])
            # Carry forward cumulative equity values into dividend-only dates
            for col in (OUT_COL_BOOK_COST, OUT_COL_QUANTITY):
                merged[col] = (
                    merged.groupby(OUT_COL_SUB_ACCOUNT, sort=False)[col].ffill().fillna(0.0)
                )
            merged[OUT_COL_TOTAL_INCOME] = merged[OUT_COL_TOTAL_INCOME].fillna(0.0)
            equity_income = merged

        # Add Cash rows
        parts = [df for df in [equity_income, cash] if not df.empty]
        if not parts:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        result = pd.concat(parts, ignore_index=True)
        result = (
            result[OUTPUT_COLUMNS]
            .sort_values(
                [OUT_COL_DATE, OUT_COL_SUB_ACCOUNT],
                ascending=True,
            )
            .reset_index(drop=True)
        )
        return result
