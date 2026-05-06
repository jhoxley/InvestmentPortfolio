class DataNotFoundError(Exception):
    def __init__(self, ticker: str, message: str | None = None) -> None:
        self.ticker = ticker
        self.message = message or f"No valid price data found for ticker '{ticker}'"
        super().__init__(self.message)


class ProviderUnavailableError(Exception):
    def __init__(self, message: str = "Upstream data provider is currently unavailable. Please try again later.") -> None:
        self.message = message
        super().__init__(self.message)


class InvalidTickerError(Exception):
    def __init__(self, ticker: str, message: str | None = None) -> None:
        self.ticker = ticker
        self.message = message or f"Invalid ticker format: '{ticker}'"
        super().__init__(self.message)
