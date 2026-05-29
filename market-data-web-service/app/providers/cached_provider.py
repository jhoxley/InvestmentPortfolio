from datetime import date, timedelta

import structlog

from app.cache.repository import CacheRepository
from app.exceptions import DataNotFoundError, ProviderUnavailableError
from app.providers import PricingProvider

logger = structlog.get_logger(__name__)


class CachedPricingProvider(PricingProvider):
    def __init__(self, inner: PricingProvider, repo: CacheRepository) -> None:
        self._inner = inner
        self._repo = repo

    def get_current_price(self, ticker: str) -> dict[str, object]:
        return self._inner.get_current_price(ticker)

    def get_price_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        cached = self._repo.read(ticker)

        if cached is None:
            return self._fetch_and_cache(ticker, from_date, to_date)

        cached_min = cached[0][0]
        cached_max = cached[-1][0]

        before: list[tuple[date, float]] = []
        after: list[tuple[date, float]] = []

        if from_date < cached_min:
            before = self._fetch_segment(ticker, from_date, cached_min - timedelta(days=1))

        if to_date > cached_max:
            after = self._fetch_segment(ticker, cached_max + timedelta(days=1), to_date)

        if not before and not after:
            logger.info(
                "cache_hit",
                ticker=ticker,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
                records_returned=len(cached),
            )
            return [(d, c) for d, c in cached if from_date <= d <= to_date]

        merged = self._merge(cached, before, after)
        self._repo.write(ticker, merged)
        logger.info(
            "cache_partial_hit",
            ticker=ticker,
            segments_fetched=int(bool(before)) + int(bool(after)),
            records_added=len(before) + len(after),
        )
        logger.info("cache_write", ticker=ticker, total_records=len(merged))
        return [(d, c) for d, c in sorted(merged, key=lambda x: x[0]) if from_date <= d <= to_date]

    def _fetch_and_cache(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        logger.info(
            "cache_miss",
            ticker=ticker,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )
        result = self._inner.get_price_history(ticker, from_date, to_date)
        self._repo.write(ticker, result)
        logger.info("cache_write", ticker=ticker, total_records=len(result))
        return result

    def _fetch_segment(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[tuple[date, float]]:
        try:
            return self._inner.get_price_history(ticker, from_date, to_date)
        except DataNotFoundError:
            # No trading days in this segment (e.g., a holiday or weekend gap) — treat as empty.
            logger.info(
                "cache_segment_empty",
                ticker=ticker,
                segment=f"{from_date}/{to_date}",
            )
            return []
        except ProviderUnavailableError as exc:
            logger.error(
                "cache_yfinance_error",
                ticker=ticker,
                segment=f"{from_date}/{to_date}",
                error=str(exc),
            )
            raise

    @staticmethod
    def _merge(
        cached: list[tuple[date, float]],
        before: list[tuple[date, float]],
        after: list[tuple[date, float]],
    ) -> list[tuple[date, float]]:
        combined: dict[date, float] = {}
        for d, c in cached:
            combined[d] = c
        for d, c in before:
            combined[d] = c
        for d, c in after:
            combined[d] = c
        return sorted(combined.items(), key=lambda x: x[0])
