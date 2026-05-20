from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import requests
import structlog
import yfinance as yf

from app.exceptions import IdentifierNotFoundError, ProviderUnavailableError

if TYPE_CHECKING:
    from app.repositories.fallback_config import FallbackConfigRepository

_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.RequestException,
)

logger = structlog.get_logger(__name__)


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


class FallbackIdentifierProvider(IdentifierProvider):
    def __init__(
        self, inner: IdentifierProvider, fallback_repo: FallbackConfigRepository
    ) -> None:
        self._inner = inner
        self._fallback_repo = fallback_repo

    def lookup_ticker(
        self, identifier: str, identifier_type: str
    ) -> dict[str, object]:
        try:
            return self._inner.lookup_ticker(identifier, identifier_type)
        except IdentifierNotFoundError:
            entry = self._fallback_repo.lookup(identifier)
            if entry is None:
                raise
            logger.info(
                "identifier_fallback_resolved",
                identifier=identifier,
                ticker=identifier,
            )
            return {"ticker": identifier, "security_name": "", "exchange": ""}
