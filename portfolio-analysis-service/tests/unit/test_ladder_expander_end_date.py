"""Unit tests for LadderExpander's explicit end_date parameter (014)."""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.services.ladder_expander import LadderExpander


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


class TestExplicitEndDateOverridesTMinus2Default:
    """An explicit end_date expands through that date, not the T-2 default."""

    def test_explicit_end_date_overrides_t_minus_2_default(
        self, expander: LadderExpander, today: date
    ) -> None:
        """Supplying end_date expands all the way through it, past the T-2 default."""
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
        t_minus_2 = pd.bdate_range(end=today, periods=3)[-3].date()
        explicit_end = pd.bdate_range(end=today, periods=1)[0].date()  # T-0 or T-1 business day

        result = expander.expand(df, today, end_date=explicit_end)

        assert result["date"].max() == explicit_end
        assert explicit_end >= t_minus_2


class TestOmittedEndDateKeepsTMinus2Default:
    """Omitting end_date preserves the original ingestion T-2 behaviour exactly."""

    def test_omitted_end_date_keeps_t_minus_2_default(
        self, expander: LadderExpander, today: date
    ) -> None:
        """Without end_date, the expansion still ends at today minus 2 business days."""
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
        t_minus_2 = pd.bdate_range(end=today, periods=3)[-3].date()

        result = expander.expand(df, today)

        assert result["date"].max() == t_minus_2
