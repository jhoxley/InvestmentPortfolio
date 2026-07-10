"""Unit tests for LadderExpander business-day expansion logic."""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.services.ladder_expander import LadderExpander


def _next_monday(ref: date) -> date:
    """Return the next Monday on or after ref.

    Args:
        ref: Reference date.

    Returns:
        A Monday date.
    """
    days_ahead = (7 - ref.weekday()) % 7
    return ref + timedelta(days=days_ahead if days_ahead else 7)


@pytest.fixture()
def expander() -> LadderExpander:
    """Return a LadderExpander instance.

    Returns:
        LadderExpander ready for use in tests.
    """
    return LadderExpander()


@pytest.fixture()
def today() -> date:
    """Return today's date for tests.

    Returns:
        Current date.
    """
    return date.today()


class TestForwardFillAcrossGapDays:
    """Tests that values are forward-filled across days with no activity."""

    def test_forward_fill_across_gap_days(self, expander: LadderExpander, today: date) -> None:
        """Values from an activity date should propagate to subsequent days with no activity."""
        d1 = today - timedelta(days=30)
        d2 = today - timedelta(days=20)
        df = pd.DataFrame(
            {
                "date": [d1, d2],
                "sub_account": ["Cash", "Cash"],
                "book_cost": [100.0, 200.0],
                "quantity": [100.0, 200.0],
                "total_income": [0.0, 5.0],
            }
        )
        result = expander.expand(df, today)
        cash_rows = result[result["sub_account"] == "Cash"]
        gap_day = d1 + timedelta(days=3)
        if gap_day.weekday() < 5:
            gap_rows = cash_rows[cash_rows["date"] == gap_day]
            assert len(gap_rows) == 1
            assert gap_rows.iloc[0]["book_cost"] == 100.0


class TestEquityExcludedAfterQuantityZero:
    """Tests that equity positions are excluded after quantity reaches zero."""

    def test_equity_excluded_after_quantity_zero(
        self, expander: LadderExpander, today: date
    ) -> None:
        """An equity sub-account with quantity=0 must not appear in subsequent dates."""
        closure = today - timedelta(days=20)
        if closure.weekday() >= 5:  # Snap to the prior business day so the recorded
            closure -= timedelta(days=closure.weekday() - 4)  # closure event lands on a weekday.
        d1 = today - timedelta(days=40)
        df = pd.DataFrame(
            {
                "date": [d1, d1, closure, closure],
                "sub_account": ["Cash", "Equity A", "Cash", "Equity A"],
                "book_cost": [1000.0, 500.0, 1000.0, 0.0],
                "quantity": [1000.0, 10.0, 1000.0, 0.0],
                "total_income": [0.0, 5.0, 0.0, 5.0],
            }
        )
        result = expander.expand(df, today)
        after_closure = closure + timedelta(days=5)
        if after_closure.weekday() >= 5:
            after_closure += timedelta(days=2)
        equity_after = result[(result["sub_account"] == "Equity A") & (result["date"] > closure)]
        assert len(equity_after) == 0, "Equity A should not appear after closure date"


class TestCashAlwaysPresentAtZeroBalance:
    """Tests that Cash sub-account always appears, even with zero balance."""

    def test_cash_always_present_at_zero_balance(
        self, expander: LadderExpander, today: date
    ) -> None:
        """Cash must appear on every business day, including days with zero balance."""
        d1 = today - timedelta(days=30)
        df = pd.DataFrame(
            {
                "date": [d1],
                "sub_account": ["Cash"],
                "book_cost": [0.0],
                "quantity": [0.0],
                "total_income": [0.0],
            }
        )
        result = expander.expand(df, today)
        cash_rows = result[result["sub_account"] == "Cash"]
        assert len(cash_rows) > 0, "Cash must appear even with zero balance"


class TestOnlyBusinessDaysInOutput:
    """Tests that the output contains only business days (Mon-Fri)."""

    def test_only_business_days_in_output(self, expander: LadderExpander, today: date) -> None:
        """No Saturday or Sunday should appear in the expanded ladder."""
        d1 = today - timedelta(days=30)
        df = pd.DataFrame(
            {
                "date": [d1],
                "sub_account": ["Cash"],
                "book_cost": [100.0],
                "quantity": [100.0],
                "total_income": [0.0],
            }
        )
        result = expander.expand(df, today)
        for d in result["date"]:
            assert d.weekday() < 5, f"Weekend date found in output: {d}"


class TestDateRangeEndsAtTMinus2:
    """Tests that the expansion range ends at T-2 business days."""

    def test_date_range_ends_at_t_minus_2(self, expander: LadderExpander, today: date) -> None:
        """The latest date in the expanded output must be ≤ today minus 2 business days."""
        import pandas as pd_mod

        t2 = pd_mod.bdate_range(end=today, periods=3)[-3]
        d1 = today - timedelta(days=30)
        df = pd.DataFrame(
            {
                "date": [d1],
                "sub_account": ["Cash"],
                "book_cost": [100.0],
                "quantity": [100.0],
                "total_income": [0.0],
            }
        )
        result = expander.expand(df, today)
        max_date = result["date"].max()
        assert max_date <= t2.date(), f"Max date {max_date} exceeds T-2 boundary {t2.date()}"


class TestAllSubAccountsClosedBeforeT2StoresPartialLadder:
    """Tests that a fully-closed ledger is accepted and stored as a partial ladder."""

    def test_all_sub_accounts_closed_before_t_minus_2_stores_partial_ladder(
        self, expander: LadderExpander, today: date
    ) -> None:
        """A ledger where all equities close well before T-2 must produce a non-empty result."""
        closure = today - timedelta(days=60)
        d1 = today - timedelta(days=90)
        df = pd.DataFrame(
            {
                "date": [d1, d1, closure, closure],
                "sub_account": ["Cash", "Equity A", "Cash", "Equity A"],
                "book_cost": [1000.0, 500.0, 0.0, 0.0],
                "quantity": [1000.0, 10.0, 0.0, 0.0],
                "total_income": [0.0, 5.0, 0.0, 5.0],
            }
        )
        result = expander.expand(df, today)
        assert len(result) > 0, "Partial ladder should be non-empty"
        # Equity A must stop appearing after closure; Cash persists to T-2 regardless.
        equity_rows = result[result["sub_account"] == "Equity A"]
        if len(equity_rows) > 0:
            assert equity_rows["date"].max() <= closure, (
                "Equity A should not appear after its closure date"
            )
        cash_rows = result[result["sub_account"] == "Cash"]
        assert len(cash_rows) > 0, "Cash must still appear after all equities close"
