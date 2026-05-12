from abc import ABC, abstractmethod

import requests
import yfinance as yf

from app.exceptions import IdentifierNotFoundError, ProviderUnavailableError

_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.RequestException,
)


class IdentifierProvider(ABC):
    @abstractmethod
    def lookup_ticker(self, identifier: str, identifier_type: str) -> dict[str, object]:
        ...


class YFinanceIdentifierProvider(IdentifierProvider):
    def lookup_ticker(self, identifier: str, identifier_type: str) -> dict[str, object]:
        try:
            results = yf.Search(identifier, max_results=1, news_count=0)
            quotes = results.quotes
        except _NETWORK_ERRORS as exc:
            raise ProviderUnavailableError() from exc
        except Exception as exc:
            raise ProviderUnavailableError() from exc

        if not quotes:
            raise IdentifierNotFoundError(identifier)

        quote = quotes[0]
        return {
            "ticker": str(quote.get("symbol") or ""),
            "security_name": str(quote.get("longname") or quote.get("shortname") or ""),
            "exchange": str(quote.get("exchange") or ""),
        }
