"""Domain exception classes for the portfolio analysis service."""

from datetime import date


class InvalidAccountNameError(Exception):
    """Raised when an account name violates the allowed character or length constraints."""

    def __init__(self, account_name: str, pattern: str, message: str | None = None) -> None:
        """Initialise with the invalid name and the expected pattern.

        Args:
            account_name: The account name that failed validation.
            pattern: The regex pattern the name must satisfy.
            message: Optional override message.
        """
        self.account_name = account_name
        self.pattern = pattern
        self.message = message or (
            f"Account name '{account_name}' is invalid. Must match pattern '{pattern}'."
        )
        super().__init__(self.message)


class SchemaValidationError(Exception):
    """Raised when the uploaded XLSX file fails schema validation."""

    def __init__(self, fields: list[str], message: str) -> None:
        """Initialise with the fields that failed and a descriptive message.

        Args:
            fields: Column names or field identifiers that caused the failure.
            message: Human-readable description of the validation failure.
        """
        self.fields = fields
        self.message = message
        super().__init__(self.message)


class AccountNotFoundError(Exception):
    """Raised when no stored ladder exists for the requested account."""

    def __init__(self, account_name: str, message: str | None = None) -> None:
        """Initialise with the missing account name.

        Args:
            account_name: The account name that was not found.
            message: Optional override message.
        """
        self.account_name = account_name
        self.message = message or f"No ladder found for account '{account_name}'."
        super().__init__(self.message)


class MergeNotSupportedError(Exception):
    """Raised when a different file is submitted for an account that already has a ladder."""

    def __init__(self, account_name: str, message: str | None = None) -> None:
        """Initialise with the conflicting account name.

        Args:
            account_name: The account whose ladder cannot be merged.
            message: Optional override message.
        """
        self.account_name = account_name
        self.message = message or (
            f"A ladder already exists for '{account_name}' with a different checksum. "
            "Merging updated ledgers is not currently supported."
        )
        super().__init__(self.message)


class EmptyDateRangeError(Exception):
    """Raised when the ledger's earliest date is within two business days of today."""

    def __init__(self, account_name: str, earliest_date: date, message: str | None = None) -> None:
        """Initialise with the account name and the problematic earliest date.

        Args:
            account_name: The account being ingested.
            earliest_date: The earliest activity date in the ledger.
            message: Optional override message.
        """
        self.account_name = account_name
        self.earliest_date = earliest_date
        self.message = message or (
            f"Earliest activity date {earliest_date} for account '{account_name}' "
            "is within two business days of today. No business days fall in the "
            "expansion range — the file cannot be processed."
        )
        super().__init__(self.message)
