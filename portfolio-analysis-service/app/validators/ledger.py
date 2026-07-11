"""Schema validator for incoming sub-account ledger XLSX files."""

from datetime import date

import pandas as pd

from app.exceptions import EmptyDateRangeError, SchemaValidationError

_REQUIRED_COLUMNS: list[str] = ["date", "sub_account", "book_cost", "quantity", "total_income"]
_NUMERIC_COLUMNS: list[str] = ["book_cost", "quantity", "total_income"]


class LedgerValidator:
    """Validates that a parsed ledger DataFrame conforms to the expected schema.

    Checks performed (in order):
    1. All required columns are present.
    2. At least one data row exists.
    3. The date column contains parseable dates.
    4. Numeric columns contain numeric values.
    5. The expansion date range (min_date → today - 2 business days) is non-empty.
    """

    def validate(self, df: pd.DataFrame, account_name: str, today: date) -> None:
        """Validate a ledger DataFrame against all schema rules.

        Args:
            df: The parsed ledger DataFrame to validate.
            account_name: The account being ingested (used in error messages).
            today: Reference date for computing the T-2 expansion boundary.

        Raises:
            SchemaValidationError: If any column or data-type constraint is violated.
            EmptyDateRangeError: If the earliest activity date is within 2 business days of today.
        """
        self._check_required_columns(df)
        self._check_non_empty(df, account_name)
        self._check_date_column(df)
        self._check_numeric_columns(df)
        self._check_date_range(df, account_name, today)

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
                message=f"The ledger for account '{account_name}' contains no data rows.",
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

    def _check_date_range(self, df: pd.DataFrame, account_name: str, today: date) -> None:
        """Raise EmptyDateRangeError if the expansion range contains no business days.

        The expansion end date is today minus 2 business days. If the earliest
        activity date is on or after this boundary, no ladder rows would be produced.

        Args:
            df: DataFrame with a parseable date column.
            account_name: Used in the error message.
            today: Reference date for T-2 computation.

        Raises:
            EmptyDateRangeError: If no business days fall within the expansion range.
        """
        import pandas as pd_mod

        parsed_dates = pd.to_datetime(df["date"], errors="coerce")
        min_date = parsed_dates.min().date()
        end_date = pd_mod.bdate_range(end=today, periods=3)[-3].date()
        if min_date >= end_date:
            raise EmptyDateRangeError(account_name=account_name, earliest_date=min_date)
