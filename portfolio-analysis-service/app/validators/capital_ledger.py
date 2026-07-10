"""Schema validator for incoming capital ledger XLSX files."""

import pandas as pd

from app.exceptions import EmptyCapitalDateRangeError, SchemaValidationError

_REQUIRED_COLUMNS: list[str] = ["date", "capital", "income", "book_value"]
_NUMERIC_COLUMNS: list[str] = ["capital", "income", "book_value"]


class CapitalLedgerValidator:
    """Validates that a parsed capital ledger DataFrame conforms to the expected schema.

    Checks performed (in order):
    1. All required columns are present.
    2. At least one data row exists.
    3. The date column contains parseable dates.
    4. Numeric columns contain numeric values.
    5. The recorded date range (min(date) through max(date)) contains at least one
       business day. Unlike the position ladder, this range is not relative to "today".
    """

    def validate(self, df: pd.DataFrame, account_name: str) -> None:
        """Validate a capital ledger DataFrame against all schema rules.

        Args:
            df: The parsed capital ledger DataFrame to validate.
            account_name: The account being ingested (used in error messages).

        Raises:
            SchemaValidationError: If any column or data-type constraint is violated.
            EmptyCapitalDateRangeError: If the recorded date range contains no business days.
        """
        self._check_required_columns(df)
        self._check_non_empty(df, account_name)
        self._check_date_column(df)
        self._check_numeric_columns(df)
        self._check_date_range(df, account_name)

    def _check_required_columns(self, df: pd.DataFrame) -> None:
        """Raise SchemaValidationError if any required column is missing.

        Args:
            df: DataFrame to check.

        Raises:
            SchemaValidationError: Lists all missing column names.
        """
        missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise SchemaValidationError(
                fields=missing,
                message=f"Missing required columns: {', '.join(missing)}.",
            )

    def _check_non_empty(self, df: pd.DataFrame, account_name: str) -> None:
        """Raise SchemaValidationError if the DataFrame contains no data rows.

        Args:
            df: DataFrame to check.
            account_name: Used in the error message.

        Raises:
            SchemaValidationError: When the DataFrame is empty.
        """
        if df.empty:
            raise SchemaValidationError(
                fields=[],
                message=f"The capital ledger for account '{account_name}' contains no data rows.",
            )

    def _check_date_column(self, df: pd.DataFrame) -> None:
        """Raise SchemaValidationError if any value in the date column is not parseable.

        Args:
            df: DataFrame to check.

        Raises:
            SchemaValidationError: If pd.to_datetime conversion fails for any row.
        """
        try:
            pd.to_datetime(df["date"], errors="raise")
        except (ValueError, TypeError) as exc:
            raise SchemaValidationError(
                fields=["date"],
                message=f"Column 'date' contains values that cannot be parsed as dates: {exc}",
            ) from exc

    def _check_numeric_columns(self, df: pd.DataFrame) -> None:
        """Raise SchemaValidationError if any numeric column contains non-numeric values.

        Args:
            df: DataFrame to check.

        Raises:
            SchemaValidationError: Lists all columns that failed numeric coercion.
        """
        invalid: list[str] = []
        for col in _NUMERIC_COLUMNS:
            if col in df.columns:
                coerced = pd.to_numeric(df[col], errors="coerce")
                if coerced.isna().any():
                    invalid.append(col)
        if invalid:
            raise SchemaValidationError(
                fields=invalid,
                message=f"Non-numeric values found in columns: {', '.join(invalid)}.",
            )

    def _check_date_range(self, df: pd.DataFrame, account_name: str) -> None:
        """Raise EmptyCapitalDateRangeError if the recorded range contains no business days.

        Args:
            df: DataFrame with a parseable date column.
            account_name: Used in the error message.

        Raises:
            EmptyCapitalDateRangeError: If no business days fall within
                [min(date), max(date)].
        """
        parsed_dates = pd.to_datetime(df["date"], errors="coerce")
        earliest_date = parsed_dates.min().date()
        latest_date = parsed_dates.max().date()
        if pd.bdate_range(start=earliest_date, end=latest_date).empty:
            raise EmptyCapitalDateRangeError(
                account_name=account_name,
                earliest_date=earliest_date,
                latest_date=latest_date,
            )
