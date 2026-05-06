from datetime import date

import requests
import yfinance as yf

from app.exceptions import DataNotFoundError, ProviderUnavailableError
from app.providers import PricingProvider

_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.RequestException,
)


class YFinanceProvider(PricingProvider):
    def get_current_price(self, ticker: str) -> dict[str, object]:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
        except _NETWORK_ERRORS as exc:
            raise ProviderUnavailableError() from exc
        except Exception as exc:
            raise DataNotFoundError(ticker) from exc

        try:
            price = info.last_price
            currency = getattr(info, "currency", None)
            market_state = getattr(info, "market_state", None)
        except Exception as exc:
            raise DataNotFoundError(ticker) from exc

        if price is None or price <= 0:
            raise DataNotFoundError(ticker)

        return {
            "price": float(price),
            "currency": str(currency) if currency else "USD",
            "market_state": market_state,
        }

    def get_price_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        try:
            t = yf.Ticker(ticker)
            df = t.history(start=from_date.isoformat(), end=to_date.isoformat())
        except _NETWORK_ERRORS as exc:
            raise ProviderUnavailableError() from exc
        except Exception as exc:
            raise DataNotFoundError(ticker) from exc

        if df is None or df.empty:
            raise DataNotFoundError(ticker)

        results: list[tuple[date, float]] = []
        for ts, row in df.iterrows():
            close = float(row["Close"])
            if close <= 0:
                continue
            results.append((ts.date(), close))

        if not results:
            raise DataNotFoundError(ticker)

        return sorted(results, key=lambda x: x[0])
