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


class EmptyCapitalDateRangeError(Exception):
    """Raised when a capital ledger's recorded date range contains no business days."""

    def __init__(
        self,
        account_name: str,
        earliest_date: date,
        latest_date: date,
        message: str | None = None,
    ) -> None:
        """Initialise with the account name and the problematic recorded date range.

        Args:
            account_name: The account being ingested.
            earliest_date: The earliest recorded date in the capital ledger.
            latest_date: The latest recorded date in the capital ledger.
            message: Optional override message.
        """
        self.account_name = account_name
        self.earliest_date = earliest_date
        self.latest_date = latest_date
        self.message = message or (
            f"The recorded date range {earliest_date} to {latest_date} for account "
            f"'{account_name}' contains no business days. The file cannot be processed."
        )
        super().__init__(self.message)


class IdentifierMappingError(Exception):
    """Raised when one or more non-Cash sub-accounts have no usable identifier mapping entry."""

    def __init__(self, sub_accounts: list[str], message: str | None = None) -> None:
        """Initialise with the sub-accounts that could not be resolved.

        Args:
            sub_accounts: Names of sub-accounts with no usable mapping entry.
            message: Optional override message.
        """
        self.sub_accounts = sub_accounts
        joined = ", ".join(f"'{name}'" for name in sub_accounts)
        self.message = message or (
            f"No usable identifier mapping entry (isin or ticker) found for: {joined}."
        )
        super().__init__(self.message)


class PriceCoverageError(Exception):
    """Raised when one or more (sub_account, date) pairs cannot be priced in GBP.

    A sub-account may appear with an empty date list, meaning it has no identifier
    mapping at all (every date is unpriceable) rather than a partial gap. This lets a
    single instance report both missing-mapping and missing-price problems together
    when both occur in the same ingestion (per FR-008/SC-004's "single response"
    requirement), while `IdentifierMappingError` remains the exception raised when
    mapping failures are the *only* problem found.
    """

    def __init__(self, problems: dict[str, list[date]], message: str | None = None) -> None:
        """Initialise with the sub-accounts and dates that could not be priced.

        Args:
            problems: Mapping of sub-account name to the list of dates missing a GBP
                price; an empty list means no identifier mapping was available at all.
            message: Optional override message.
        """
        self.problems = problems
        parts = []
        for name, dates in problems.items():
            if dates:
                parts.append(f"'{name}' missing prices on {', '.join(str(d) for d in dates)}")
            else:
                parts.append(f"'{name}' has no identifier mapping entry")
        details = "; ".join(parts)
        self.message = message or (
            f"Unable to obtain a complete GBP price history for all sub-accounts: {details}."
        )
        super().__init__(self.message)


class NoAttributesRequestedError(Exception):
    """Raised when a time series request specifies zero attributes."""

    def __init__(self, message: str | None = None) -> None:
        """Initialise with a default or overridden message.

        Args:
            message: Optional override message.
        """
        self.message = message or "At least one attribute must be requested."
        super().__init__(self.message)


class UnsupportedAttributeError(Exception):
    """Raised when one or more requested attribute names aren't in the supported set."""

    def __init__(
        self, requested: list[str], supported: list[str], message: str | None = None
    ) -> None:
        """Initialise with the invalid attribute names and the supported set.

        Args:
            requested: The attribute names that aren't supported.
            supported: The full set of supported attribute names.
            message: Optional override message.
        """
        self.requested = requested
        self.supported = supported
        invalid = ", ".join(f"'{name}'" for name in requested)
        valid = ", ".join(f"'{name}'" for name in supported)
        self.message = message or (
            f"Unsupported attribute(s): {invalid}. Supported attributes are: {valid}."
        )
        super().__init__(self.message)


class FutureEndDateError(Exception):
    """Raised when a supplied end date is later than today."""

    def __init__(self, end: date, today: date, message: str | None = None) -> None:
        """Initialise with the supplied end date and today's date.

        Args:
            end: The supplied end date.
            today: The current date.
            message: Optional override message.
        """
        self.end = end
        self.today = today
        self.message = message or (
            f"End date {end} is later than today ({today}). The end date must not be in the future."
        )
        super().__init__(self.message)


class InvalidDateRangeError(Exception):
    """Raised when the resolved start date is after the resolved end date."""

    def __init__(self, start: date, end: date, message: str | None = None) -> None:
        """Initialise with the resolved start and end dates.

        Args:
            start: The resolved start date.
            end: The resolved end date.
            message: Optional override message.
        """
        self.start = start
        self.end = end
        self.message = message or (f"Resolved start date {start} is after resolved end date {end}.")
        super().__init__(self.message)


class MissingRequiredSourceError(Exception):
    """Raised when a requested attribute's required source is missing or insufficient."""

    def __init__(
        self, account_name: str, attribute: str, source: str, message: str | None = None
    ) -> None:
        """Initialise with the account, attribute, and source that could not be satisfied.

        Args:
            account_name: The account being queried.
            attribute: The requested attribute that could not be computed.
            source: The required source ('capital_ledger' or 'position_ladder').
            message: Optional override message.
        """
        self.account_name = account_name
        self.attribute = attribute
        self.source = source
        self.message = message or (
            f"Attribute '{attribute}' requires {source}, which is unavailable or "
            f"insufficient for account '{account_name}'."
        )
        super().__init__(self.message)


class PositionLadderNotIngestedError(Exception):
    """Raised when a known account has no ingested position ladder for this feature's endpoints."""

    def __init__(self, account_name: str, message: str | None = None) -> None:
        """Initialise with the account name that lacks a position ladder.

        Args:
            account_name: The account known to `/v1/accounts` but missing a ladder.
            message: Optional override message.
        """
        self.account_name = account_name
        self.message = message or f"Account '{account_name}' has no ingested position ladder."
        super().__init__(self.message)


class MarketDataServiceError(Exception):
    """Raised when a market-data-service request fails (network error, non-2xx, timeout)."""

    def __init__(self, sub_account: str, detail: str, message: str | None = None) -> None:
        """Initialise with the affected sub-account and the underlying failure detail.

        Args:
            sub_account: The sub-account whose price request could not be completed.
            detail: Description of the underlying failure (e.g. exception message).
            message: Optional override message.
        """
        self.sub_account = sub_account
        self.detail = detail
        self.message = message or (
            f"Market data service request failed for sub-account '{sub_account}': {detail}"
        )
        super().__init__(self.message)
