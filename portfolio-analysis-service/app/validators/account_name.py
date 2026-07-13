"""Shared account-name validation used across all account-scoped API routers."""

import re

from app.exceptions import InvalidAccountNameError

ACCOUNT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_account_name(account_name: str) -> None:
    """Raise InvalidAccountNameError if the account name does not match the allowed pattern.

    Args:
        account_name: The account identifier to validate.

    Raises:
        InvalidAccountNameError: If the name contains illegal characters or exceeds 64 chars.
    """
    if not ACCOUNT_NAME_PATTERN.match(account_name):
        raise InvalidAccountNameError(
            account_name=account_name,
            pattern=ACCOUNT_NAME_PATTERN.pattern,
        )
