from datetime import date
from typing import TYPE_CHECKING

import structlog

from app.exceptions import DataNotFoundError
from app.models.fallback import FallbackEntry
from app.providers import PricingProvider
from app.providers.observation_window import ObservationWindow, ObservationWindowSource
from app.repositories.fallback_config import FallbackConfigRepository

if TYPE_CHECKING:
    from app.providers.local_provider import LocalPricingProvider

logger = structlog.get_logger(__name__)


class FallbackPricingProvider(PricingProvider):
    def __init__(
        self, inner: PricingProvider, fallback_repo: FallbackConfigRepository
    ) -> None:
        self._inner = inner
        self._fallback_repo = fallback_repo

    def observation_window(self, ticker: str) -> ObservationWindow | None:
        """Satisfies ObservationWindowSource, following whichever source served the prices.

        Keyed on the data source, not on the `use_local_only` flag: for a fallback-triggered
        entry the CSV supplied the prices but the inner provider has no cache file to read a
        window from, so a flag-keyed implementation would return None and break FR-017.
        """
        entry = self._fallback_repo.lookup(ticker)

        if entry is None:
            return self._inner_window(ticker)

        if entry.use_local_only:
            return self._local_provider(entry).observation_window(ticker)

        # Not local-only: the inner provider is tried first for prices, so its window wins when
        # it has one. No inner window means the local file is what served the request.
        inner_window = self._inner_window(ticker)
        if inner_window is not None:
            return inner_window
        return self._local_provider(entry).observation_window(ticker)

    def _inner_window(self, ticker: str) -> ObservationWindow | None:
        if isinstance(self._inner, ObservationWindowSource):
            return self._inner.observation_window(ticker)
        return None

    def _local_provider(self, entry: FallbackEntry) -> "LocalPricingProvider":
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
