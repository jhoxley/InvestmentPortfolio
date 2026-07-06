"""Unit tests for LedgerValidator schema validation."""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.exceptions import EmptyDateRangeError, SchemaValidationError
from app.validators.ledger import LedgerValidator


def _valid_df(today: date | None = None) -> pd.DataFrame:
    """Build a minimal valid ledger DataFrame.

    Args:
        today: Reference date for computing activity dates. Defaults to date.today().

    Returns:
        DataFrame with all required columns and valid data.
    """
    ref = today or date.today()
    d1 = ref - timedelta(days=30)
    return pd.DataFrame(
        {
            "date": [d1],
            "sub_account": ["Cash"],
            "book_cost": [1000.0],
            "quantity": [1000.0],
            "total_income": [0.0],
        }
    )


@pytest.fixture()
def validator() -> LedgerValidator:
    """Return a LedgerValidator instance.

    Returns:
        LedgerValidator ready for use in tests.
    """
    return LedgerValidator()


@pytest.fixture()
def today() -> date:
    """Return today's date for tests.

    Returns:
        Current date.
    """
    return date.today()


class TestValidFilePasses:
    """Tests that confirm valid input does not raise."""

    def test_valid_file_passes(self, validator: LedgerValidator, today: date) -> None:
        """A well-formed ledger DataFrame should raise no exceptions."""
        df = _valid_df(today)
        validator.validate(df, "test-account", today)  # must not raise


class TestMissingColumnRaises:
    """Tests for missing required columns."""

    @pytest.mark.parametrize(
        "column", ["date", "sub_account", "book_cost", "quantity", "total_income"]
    )
    def test_missing_column_raises(
        self, validator: LedgerValidator, today: date, column: str
    ) -> None:
        """Removing any required column should raise SchemaValidationError."""
        df = _valid_df(today).drop(columns=[column])
        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate(df, "test-account", today)
        assert column in exc_info.value.fields


class TestNonNumericRaises:
    """Tests for non-numeric values in numeric columns."""

    def test_non_numeric_book_cost_raises(self, validator: LedgerValidator, today: date) -> None:
        """A non-numeric value in book_cost should raise SchemaValidationError."""
        df = _valid_df(today)
        df["book_cost"] = "not-a-number"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account", today)

    def test_non_numeric_quantity_raises(self, validator: LedgerValidator, today: date) -> None:
        """A non-numeric value in quantity should raise SchemaValidationError."""
        df = _valid_df(today)
        df["quantity"] = "abc"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account", today)

    def test_non_numeric_total_income_raises(self, validator: LedgerValidator, today: date) -> None:
        """A non-numeric value in total_income should raise SchemaValidationError."""
        df = _valid_df(today)
        df["total_income"] = "abc"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account", today)


class TestUnparseableDateRaises:
    """Tests for unparseable date values."""

    def test_unparseable_date_raises(self, validator: LedgerValidator, today: date) -> None:
        """An unparseable date string should raise SchemaValidationError."""
        df = _valid_df(today)
        df["date"] = "not-a-date"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account", today)


class TestEmptyDataframeRaises:
    """Tests for empty input."""

    def test_empty_dataframe_raises(self, validator: LedgerValidator, today: date) -> None:
        """An empty DataFrame should raise SchemaValidationError."""
        df = pd.DataFrame(columns=["date", "sub_account", "book_cost", "quantity", "total_income"])
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account", today)


class TestEarliestDateWithinT2Raises:
    """Tests for the T-2 date range check."""

    def test_earliest_date_within_t2_raises(self, validator: LedgerValidator) -> None:
        """A ledger whose earliest date is within 2 business days of today should raise."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        df = pd.DataFrame(
            {
                "date": [yesterday],
                "sub_account": ["Cash"],
                "book_cost": [100.0],
                "quantity": [100.0],
                "total_income": [0.0],
            }
        )
        with pytest.raises(EmptyDateRangeError):
            validator.validate(df, "test-account", today)
