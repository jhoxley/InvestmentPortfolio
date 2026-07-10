"""Unit tests for CapitalLedgerValidator schema validation."""

from datetime import date

import pandas as pd
import pytest

from app.exceptions import EmptyCapitalDateRangeError, SchemaValidationError
from app.validators.capital_ledger import CapitalLedgerValidator


def _valid_df() -> pd.DataFrame:
    """Build a minimal valid capital ledger DataFrame.

    Returns:
        DataFrame with all required columns and valid data, spanning two weekdays.
    """
    return pd.DataFrame(
        {
            "date": [date(2024, 1, 2), date(2024, 1, 10)],
            "capital": [1000.0, 1200.0],
            "income": [0.0, 5.0],
            "book_value": [0.0, 900.0],
        }
    )


@pytest.fixture()
def validator() -> CapitalLedgerValidator:
    """Return a CapitalLedgerValidator instance.

    Returns:
        CapitalLedgerValidator ready for use in tests.
    """
    return CapitalLedgerValidator()


class TestValidFilePasses:
    """Tests that confirm valid input does not raise."""

    def test_valid_file_passes(self, validator: CapitalLedgerValidator) -> None:
        """A well-formed capital ledger DataFrame should raise no exceptions."""
        df = _valid_df()
        validator.validate(df, "test-account")  # must not raise


class TestMissingColumnRaises:
    """Tests for missing required columns."""

    @pytest.mark.parametrize("column", ["date", "capital", "income", "book_value"])
    def test_missing_column_raises(self, validator: CapitalLedgerValidator, column: str) -> None:
        """Removing any required column should raise SchemaValidationError."""
        df = _valid_df().drop(columns=[column])
        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate(df, "test-account")
        assert column in exc_info.value.fields


class TestNonNumericRaises:
    """Tests for non-numeric values in numeric columns."""

    def test_non_numeric_capital_raises(self, validator: CapitalLedgerValidator) -> None:
        """A non-numeric value in capital should raise SchemaValidationError."""
        df = _valid_df()
        df["capital"] = "not-a-number"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account")

    def test_non_numeric_income_raises(self, validator: CapitalLedgerValidator) -> None:
        """A non-numeric value in income should raise SchemaValidationError."""
        df = _valid_df()
        df["income"] = "abc"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account")

    def test_non_numeric_book_value_raises(self, validator: CapitalLedgerValidator) -> None:
        """A non-numeric value in book_value should raise SchemaValidationError."""
        df = _valid_df()
        df["book_value"] = "abc"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account")


class TestUnparseableDateRaises:
    """Tests for unparseable date values."""

    def test_unparseable_date_raises(self, validator: CapitalLedgerValidator) -> None:
        """An unparseable date string should raise SchemaValidationError."""
        df = _valid_df()
        df["date"] = "not-a-date"
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account")


class TestEmptyDataframeRaises:
    """Tests for empty input."""

    def test_empty_dataframe_raises(self, validator: CapitalLedgerValidator) -> None:
        """An empty DataFrame should raise SchemaValidationError."""
        df = pd.DataFrame(columns=["date", "capital", "income", "book_value"])
        with pytest.raises(SchemaValidationError):
            validator.validate(df, "test-account")


class TestRecordedRangeWithNoBusinessDaysRaises:
    """Tests for a recorded date range that yields zero business days."""

    def test_recorded_range_with_no_business_days_raises_empty_capital_date_range_error(
        self, validator: CapitalLedgerValidator
    ) -> None:
        """A file whose only date is a Saturday should raise EmptyCapitalDateRangeError."""
        saturday = date(2024, 1, 6)
        df = pd.DataFrame(
            {
                "date": [saturday],
                "capital": [1000.0],
                "income": [0.0],
                "book_value": [0.0],
            }
        )
        with pytest.raises(EmptyCapitalDateRangeError):
            validator.validate(df, "test-account")
