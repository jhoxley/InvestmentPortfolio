from datetime import date

from app.providers import PricingProvider


class FxInnerProvider(PricingProvider):
    """Translates pair codes (e.g., USDGBP) to yfinance FX tickers (USDGBP=X)."""

    def __init__(self, inner: PricingProvider) -> None:
        self._inner = inner

    def get_current_price(self, ticker: str) -> dict[str, object]:
        raise NotImplementedError("FxInnerProvider does not support current price")

    def get_price_history(
        self, pair: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        fx_ticker = f"{pair}=X"
        return self._inner.get_price_history(fx_ticker, from_date, to_date)
