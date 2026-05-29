from datetime import date

import structlog

from app.exceptions import DataNotFoundError
from app.models.fallback import FallbackEntry
from app.providers import PricingProvider
from app.repositories.fallback_config import FallbackConfigRepository

logger = structlog.get_logger(__name__)


class FallbackPricingProvider(PricingProvider):
    def __init__(
        self, inner: PricingProvider, fallback_repo: FallbackConfigRepository
    ) -> None:
        self._inner = inner
        self._fallback_repo = fallback_repo

    def _local_provider(self, entry: FallbackEntry) -> PricingProvider:
        from app.providers.local_provider import LocalPricingProvider

        return LocalPricingProvider(entry)

    def get_price_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        entry = self._fallback_repo.lookup(ticker)

        if entry is None:
            return self._inner.get_price_history(ticker, from_date, to_date)

        if entry.use_local_only:
            logger.info(
                "local_only_bypass",
                ticker=ticker,
                fallback_path=str(entry.csv_path),
            )
            return self._local_provider(entry).get_price_history(
                ticker, from_date, to_date
            )

        try:
            return self._inner.get_price_history(ticker, from_date, to_date)
        except DataNotFoundError:
            logger.info(
                "fallback_triggered",
                ticker=ticker,
                fallback_path=str(entry.csv_path),
            )
            return self._local_provider(entry).get_price_history(
                ticker, from_date, to_date
            )

    def get_current_price(self, ticker: str) -> dict[str, object]:
        entry = self._fallback_repo.lookup(ticker)

        if entry is None:
            return self._inner.get_current_price(ticker)

        if entry.use_local_only:
            logger.info(
                "local_only_bypass",
                ticker=ticker,
                fallback_path=str(entry.csv_path),
            )
            return self._local_provider(entry).get_current_price(ticker)

        try:
            return self._inner.get_current_price(ticker)
        except DataNotFoundError:
            logger.info(
                "fallback_triggered",
                ticker=ticker,
                fallback_path=str(entry.csv_path),
            )
            return self._local_provider(entry).get_current_price(ticker)
