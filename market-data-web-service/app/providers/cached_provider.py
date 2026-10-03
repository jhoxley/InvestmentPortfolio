from datetime import date, timedelta

import structlog

from app.cache.repository import CacheRepository
from app.exceptions import DataNotFoundError, ProviderUnavailableError
from app.providers import PricingProvider
from app.providers.observation_window import ObservationWindow

logger = structlog.get_logger(__name__)


class CachedPricingProvider(PricingProvider):
    def __init__(self, inner: PricingProvider, repo: CacheRepository) -> None:
        self._inner = inner
        self._repo = repo

    def get_current_price(self, ticker: str) -> dict[str, object]:
        return self._inner.get_current_price(ticker)

    def observation_window(self, ticker: str) -> ObservationWindow | None:
        """Satisfies ObservationWindowSource from the cache file's extremes.

        The cache holds raw observations only — gap-fill runs downstream in PricingService —
        so these extremes are always over real observations (FR-014).
        """
        cached = self._repo.read(ticker)
        if not cached:
            return None
        return ObservationWindow(
            first_observed_date=cached[0][0], last_observed_date=cached[-1][0]
        )

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
            if self._earlier_segment_known_empty(ticker, cached_min):
                logger.info(
                    "cache_no_earlier_data_skip",
                    ticker=ticker,
                    no_data_before=cached_min.isoformat(),
                    requested_from=from_date.isoformat(),
                )
            else:
                before = self._fetch_segment(ticker, from_date, cached_min - timedelta(days=1))
                self._record_earlier_outcome(ticker, before, cached_min)

        if to_date > cached_max:
            # The segment after the latest observation is never suppressed: new data
            # legitimately arrives there every day (FR-020).
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

    def _earlier_segment_known_empty(self, ticker: str, cached_min: date) -> bool:
        """True when a recorded boundary says nothing exists before the cached start.

        If the cache has since grown earlier than the boundary, the boundary is contradicted by
        real data and is discarded rather than trusted (FR-022).
        """
        boundary = self._repo.read_no_data_before(ticker)
        if boundary is None:
            return False
        if cached_min < boundary:
            logger.info(
                "cache_no_earlier_data_invalidated",
                ticker=ticker,
                previous_no_data_before=boundary.isoformat(),
                reason="cache_holds_earlier_observation",
                earliest_cached=cached_min.isoformat(),
            )
            self._repo.clear_no_data_before(ticker)
            return False
        return boundary <= cached_min

    def _record_earlier_outcome(
        self, ticker: str, before: list[tuple[date, float]], cached_min: date
    ) -> None:
        """Record what the earlier-segment fetch proved about the absence of earlier data.

        Only ever called after a *successful* fetch — `_fetch_segment` re-raises
        ProviderUnavailableError, so an outage never reaches here and can never be misrecorded
        as absence of data (FR-028).
        """
        if not before:
            self._repo.write_no_data_before(ticker, cached_min)
            logger.info(
                "cache_no_earlier_data_recorded",
                ticker=ticker,
                no_data_before=cached_min.isoformat(),
            )
            return

        new_earliest = min(d for d, _ in before)
        had_boundary = self._repo.read_no_data_before(ticker)
        self._repo.write_no_data_before(ticker, new_earliest)
        logger.info(
            "cache_no_earlier_data_invalidated",
            ticker=ticker,
            previous_no_data_before=had_boundary.isoformat() if had_boundary else None,
            no_data_before=new_earliest.isoformat(),
            reason="earlier_observations_found",
        )

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

        # FR-027: the source was asked for the whole range and returned nothing before its first
        # row, so record that. This is the request that pays the full cost of a long lookback —
        # without recording here, the saving would not arrive until a third request.
        if result:
            first = min(d for d, _ in result)
            if first > from_date:
                self._repo.write_no_data_before(ticker, first)
                logger.info(
                    "cache_no_earlier_data_recorded",
                    ticker=ticker,
                    no_data_before=first.isoformat(),
                    requested_from=from_date.isoformat(),
                )
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
