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
            df = t.history(period="5d")
        except _NETWORK_ERRORS as exc:
            raise ProviderUnavailableError() from exc
        except Exception as exc:
            raise DataNotFoundError(ticker) from exc

        if df is None or df.empty:
            raise DataNotFoundError(ticker)

        df = df[df["Close"] > 0]
        if df.empty:
            raise DataNotFoundError(ticker)

        try:
            last_row = df.iloc[-1]
            price = float(last_row["Close"])
            as_of_date: date = df.index[-1].date()
            currency = getattr(t.fast_info, "currency", None)
            market_state: str | None = t.info.get("marketState")
        except _NETWORK_ERRORS as exc:
            raise ProviderUnavailableError() from exc
        except Exception as exc:
            raise DataNotFoundError(ticker) from exc

        return {
            "price": price,
            "as_of_date": as_of_date,
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
