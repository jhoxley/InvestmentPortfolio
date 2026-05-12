import re

from app.exceptions import IdentifierFormatError

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
CUSIP_PATTERN = re.compile(r"^[A-Z0-9]{9}$")
SEDOL_PATTERN = re.compile(r"^[A-Z0-9]{6,7}$")

_PATTERNS: dict[str, re.Pattern[str]] = {
    "ISIN": ISIN_PATTERN,
    "CUSIP": CUSIP_PATTERN,
    "SEDOL": SEDOL_PATTERN,
}


def detect_identifier_type(identifier: str) -> str:
    normalised = identifier.upper()
    if ISIN_PATTERN.match(normalised):
        return "ISIN"
    if CUSIP_PATTERN.match(normalised):
        return "CUSIP"
    if SEDOL_PATTERN.match(normalised):
        return "SEDOL"
    raise IdentifierFormatError(identifier)


def validate_identifier_format(identifier: str, identifier_type: str) -> None:
    normalised = identifier.upper()
    pattern = _PATTERNS.get(identifier_type.upper())
    if pattern is None or not pattern.match(normalised):
        raise IdentifierFormatError(
            identifier,
            f"Identifier '{identifier}' does not match {identifier_type.upper()} format.",
        )
