from datetime import date


class DataNotFoundError(Exception):
    def __init__(self, ticker: str, message: str | None = None) -> None:
        self.ticker = ticker
        self.message = message or f"No valid price data found for ticker '{ticker}'"
        super().__init__(self.message)


class ProviderUnavailableError(Exception):
    def __init__(
        self,
        message: str = "Upstream data provider is currently unavailable. Please try again later.",
    ) -> None:
        self.message = message
        super().__init__(self.message)


class InvalidTickerError(Exception):
    def __init__(self, ticker: str, message: str | None = None) -> None:
        self.ticker = ticker
        self.message = message or f"Invalid ticker format: '{ticker}'"
        super().__init__(self.message)


class FxAlignmentError(Exception):
    def __init__(self, pair: str, security_date: date, message: str | None = None) -> None:
        self.pair = pair
        self.security_date = security_date
        self.message = message or (
            f"Cannot resolve FX rate for pair '{pair}' on security date {security_date}: "
            "no prior or subsequent FX rate available."
        )
        super().__init__(self.message)


class CurrencyUnavailableError(Exception):
    def __init__(self, ticker: str, message: str | None = None) -> None:
        self.ticker = ticker
        self.message = message or f"Cannot determine native currency for ticker '{ticker}'."
        super().__init__(self.message)


class InvalidCurrencyError(Exception):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or (
            f"Invalid currency code: '{code}'. Must be a 3-letter ISO 4217 code."
        )
        super().__init__(self.message)


class InvalidCurrencyPairError(Exception):
    def __init__(self, pair: str, message: str | None = None) -> None:
        self.pair = pair
        self.message = message or (
            f"Invalid FX pair '{pair}': base and quote currencies must differ."
        )
        super().__init__(self.message)


class IdentifierFormatError(Exception):
    def __init__(self, identifier: str, message: str | None = None) -> None:
        self.identifier = identifier
        self.message = message or (
            f"Identifier '{identifier}' does not match ISIN, CUSIP, or SEDOL format."
        )
        super().__init__(self.message)


class IdentifierNotFoundError(Exception):
    def __init__(self, identifier: str, message: str | None = None) -> None:
        self.identifier = identifier
        self.message = message or f"Identifier '{identifier}' could not be resolved to a ticker."
        super().__init__(self.message)
