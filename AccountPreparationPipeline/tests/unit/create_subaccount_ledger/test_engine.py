"""Unit tests for SubAccountLedgerEngine — TDD RED phase: all fail before engine exists."""

from __future__ import annotations

import pandas as pd
import pytest

from src.modes.create_subaccount_ledger.engine import SubAccountLedgerEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLS = [
    "Transaction ID",
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    "Account Value",
    "Account Quantity",
    "Transaction Value",
    "Transaction Quantity",
]


def _row(
    date: str,
    sub_account: str,
    action: str,
    tv: float,
    tq: float,
) -> dict:
    """Return a full-schema ledger row dict."""
    return {
        "Transaction ID": "TEST-001",
        "date": date,
        "account": "HL Test",
        "sub_account": sub_account,
        "action": action,
        "reference": "REF",
        "Account Value": tv,
        "Account Quantity": tq,
        "Transaction Value": tv,
        "Transaction Quantity": tq,
    }


def _df(*rows: dict) -> pd.DataFrame:
    """Build a ledger DataFrame from _row() dicts."""
    return pd.DataFrame(list(rows), columns=_COLS)


# ---------------------------------------------------------------------------
# US1 — Consolidated Equity Positions
# ---------------------------------------------------------------------------


class TestEquityPositions:
    def test_single_buy_produces_book_cost_and_quantity(self) -> None:
        df = _df(_row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        row = result[result["sub_account"] == "Barclays plc"].iloc[0]
        assert float(row["book_cost"]) == pytest.approx(200.0)
        assert float(row["quantity"]) == pytest.approx(100.0)

    def test_sell_reduces_book_cost_and_quantity(self) -> None:
        df = _df(
            _row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0),
            _row("2024-03-01", "Barclays plc", "sell", -75.0, -25.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        barcl_mar = result[result["sub_account"] == "Barclays plc"]
        row = barcl_mar[barcl_mar["date"].astype(str) == "2024-03-01"].iloc[0]
        assert float(row["book_cost"]) == pytest.approx(125.0)
        assert float(row["quantity"]) == pytest.approx(75.0)

    def test_lodgement_adds_positive_book_cost(self) -> None:
        df = _df(_row("2024-01-10", "Barclays plc", "lodgement", -500.0, 300.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        row = result[result["sub_account"] == "Barclays plc"].iloc[0]
        assert float(row["book_cost"]) == pytest.approx(500.0)

    def test_lodgement_adds_positive_quantity(self) -> None:
        df = _df(_row("2024-01-10", "Barclays plc", "lodgement", -500.0, 300.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        row = result[result["sub_account"] == "Barclays plc"].iloc[0]
        assert float(row["quantity"]) == pytest.approx(300.0)

    def test_two_buys_same_date_same_subaccount_summed(self) -> None:
        df = _df(
            _row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0),
            _row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        barclays = result[result["sub_account"] == "Barclays plc"]
        assert len(barclays) == 1
        assert float(barclays.iloc[0]["book_cost"]) == pytest.approx(400.0)

    def test_buys_across_two_capital_dfs_merged(self) -> None:
        df1 = _df(_row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0))
        df2 = _df(_row("2024-02-01", "Barclays plc", "buy", 175.0, 50.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df1, df2], income_dfs=[])
        last_row = result[result["sub_account"] == "Barclays plc"].iloc[-1]
        assert float(last_row["book_cost"]) == pytest.approx(375.0)
        assert float(last_row["quantity"]) == pytest.approx(150.0)

    def test_equity_from_income_df_included(self) -> None:
        # Equity buy in income_dfs (sub_account != "Cash") contributes to book_cost
        df = _df(_row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[], income_dfs=[df])
        assert len(result[result["sub_account"] == "Barclays plc"]) == 1
        row = result[result["sub_account"] == "Barclays plc"].iloc[0]
        assert float(row["book_cost"]) == pytest.approx(200.0)

    def test_equity_actions_only_no_dividend_in_book_cost(self) -> None:
        df = _df(
            _row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0),
            _row("2024-04-01", "Barclays plc", "dividend", 25.0, 425.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        buy_date_row = result[
            (result["sub_account"] == "Barclays plc") & (result["date"].astype(str) == "2024-01-10")
        ].iloc[0]
        assert float(buy_date_row["book_cost"]) == pytest.approx(200.0)
        # dividend TV must not inflate book_cost
        all_book_costs = result[result["sub_account"] == "Barclays plc"]["book_cost"].tolist()
        for bc in all_book_costs:
            assert float(bc) == pytest.approx(200.0), f"book_cost should be 200.0, got {bc}"


# ---------------------------------------------------------------------------
# US2 — Accumulated Dividend Income
# ---------------------------------------------------------------------------


class TestDividendIncome:
    def test_dividend_contributes_to_total_income(self) -> None:
        df = _df(_row("2024-04-01", "Barclays plc", "dividend", 25.0, 425.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        row = result[result["sub_account"] == "Barclays plc"].iloc[0]
        assert float(row["total_income"]) == pytest.approx(25.0)

    def test_dividend_tv_used_not_tq(self) -> None:
        df = _df(_row("2024-04-01", "Barclays plc", "dividend", 25.0, 999.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        row = result[result["sub_account"] == "Barclays plc"].iloc[0]
        assert float(row["total_income"]) == pytest.approx(25.0)

    def test_dividend_on_date_with_no_buy_keeps_book_cost_zero(self) -> None:
        df = _df(_row("2024-04-01", "Barclays plc", "dividend", 25.0, 425.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        row = result[result["sub_account"] == "Barclays plc"].iloc[0]
        assert float(row["book_cost"]) == pytest.approx(0.0)
        assert float(row["quantity"]) == pytest.approx(0.0)
        assert float(row["total_income"]) == pytest.approx(25.0)

    def test_two_dividends_cumulative(self) -> None:
        df = _df(
            _row("2024-04-01", "Barclays plc", "dividend", 25.0, 425.0),
            _row("2024-07-01", "Barclays plc", "dividend", 30.0, 425.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        barcl = result[result["sub_account"] == "Barclays plc"]
        dates = barcl["date"].astype(str)
        r1 = barcl[dates == "2024-04-01"].iloc[0]
        r2 = barcl[dates == "2024-07-01"].iloc[0]
        assert float(r1["total_income"]) == pytest.approx(25.0)
        assert float(r2["total_income"]) == pytest.approx(55.0)


# ---------------------------------------------------------------------------
# US3 — Cash Balance
# ---------------------------------------------------------------------------


class TestCashHandling:
    def test_cash_from_capital_df_present(self) -> None:
        df = _df(_row("2024-01-10", "Cash", "deposit", 5000.0, 0.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        assert len(result[result["sub_account"] == "Cash"]) >= 1

    def test_cash_from_income_df_excluded(self) -> None:
        income_df = _df(_row("2024-04-01", "Cash", "income", 50.0, 0.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[], income_dfs=[income_df])
        assert len(result[result["sub_account"] == "Cash"]) == 0

    def test_cash_quantity_equals_book_cost(self) -> None:
        df = _df(
            _row("2024-01-10", "Cash", "deposit", 5000.0, 0.0),
            _row("2024-01-10", "Cash", "trading", -200.0, 0.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        cash_row = result[result["sub_account"] == "Cash"].iloc[-1]
        assert float(cash_row["quantity"]) == pytest.approx(float(cash_row["book_cost"]))
        assert float(cash_row["book_cost"]) == pytest.approx(4800.0)

    def test_cash_total_income_is_zero(self) -> None:
        df = _df(
            _row("2024-01-10", "Cash", "deposit", 5000.0, 0.0),
            _row("2024-01-10", "Cash", "trading", -200.0, 0.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        for _, row in result[result["sub_account"] == "Cash"].iterrows():
            assert float(row["total_income"]) == pytest.approx(0.0)

    def test_cash_all_action_types_contribute_to_balance(self) -> None:
        df = _df(
            _row("2024-01-10", "Cash", "deposit", 1000.0, 0.0),
            _row("2024-01-10", "Cash", "trading", -200.0, 0.0),
            _row("2024-01-10", "Cash", "income", 50.0, 0.0),
            _row("2024-01-10", "Cash", "fee", -10.0, 0.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        cash_row = result[result["sub_account"] == "Cash"].iloc[0]
        assert float(cash_row["book_cost"]) == pytest.approx(840.0)


# ---------------------------------------------------------------------------
# US3 — Output Schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_output_columns_correct(self) -> None:
        df = _df(_row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        assert list(result.columns) == [
            "date",
            "sub_account",
            "book_cost",
            "quantity",
            "total_income",
        ]

    def test_output_sorted_by_date_then_sub_account(self) -> None:
        df = _df(
            _row("2024-03-01", "HSBC Fund", "buy", 300.0, 200.0),
            _row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0),
            _row("2024-01-10", "HSBC Fund", "buy", 100.0, 50.0),
        )
        result = SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        date_sub = list(
            zip(result["date"].astype(str).tolist(), result["sub_account"].tolist(), strict=True)
        )
        assert date_sub == sorted(date_sub)

    def test_one_row_per_date_sub_account(self) -> None:
        df1 = _df(_row("2024-01-10", "Barclays plc", "buy", 200.0, 100.0))
        df2 = _df(_row("2024-01-10", "Barclays plc", "buy", 150.0, 50.0))
        result = SubAccountLedgerEngine().run(capital_dfs=[df1, df2], income_dfs=[])
        barclays_jan = result[
            (result["sub_account"] == "Barclays plc") & (result["date"].astype(str) == "2024-01-10")
        ]
        assert len(barclays_jan) == 1

    def test_empty_inputs_returns_empty_df(self) -> None:
        result = SubAccountLedgerEngine().run(capital_dfs=[], income_dfs=[])
        assert list(result.columns) == [
            "date",
            "sub_account",
            "book_cost",
            "quantity",
            "total_income",
        ]
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_performance_1000_rows_under_10_seconds(self) -> None:
        import time

        import numpy as np

        rng = np.random.default_rng(42)
        sub_accounts = [f"Fund {i}" for i in range(20)]
        dates = pd.date_range("2020-01-01", periods=50, freq="ME").strftime("%Y-%m-%d").tolist()
        actions = ["buy", "sell", "dividend", "buy", "buy"]  # weighted towards buy

        rows = []
        for i in range(1000):
            action = actions[i % len(actions)]
            if action != "sell":
                tv = float(rng.uniform(-500, 1000))
            else:
                tv = float(rng.uniform(-500, -10))
            tq = float(rng.integers(1, 500)) if action != "sell" else float(rng.integers(-500, -1))
            rows.append(
                _row(
                    dates[i % len(dates)],
                    sub_accounts[i % len(sub_accounts)],
                    action,
                    tv,
                    tq,
                )
            )
        df = pd.DataFrame(rows, columns=_COLS)

        start = time.perf_counter()
        SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"Engine took {elapsed:.2f}s for 1,000 rows — must be < 10s"
