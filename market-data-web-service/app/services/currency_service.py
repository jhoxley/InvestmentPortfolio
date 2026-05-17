from datetime import date, timedelta

import structlog

from app.exceptions import CurrencyUnavailableError, FxAlignmentError
from app.models.pricing import PriceHistoryResponse, PricePoint, PriceResponse
from app.providers import PricingProvider
from app.services.fx_aligner import FxAligner
from app.services.gap_fill import GapFillService

logger = structlog.get_logger(__name__)


class CurrencyService:
    def __init__(
        self, fx_provider: PricingProvider, aligner: FxAligner, gap_fill: GapFillService
    ) -> None:
        self._fx_provider = fx_provider
        self._aligner = aligner
        self._gap_fill = gap_fill

    def get_native_currency(self, ticker: str, security_provider: PricingProvider) -> str:
        """Return the native currency for a security."""
        try:
            raw = security_provider.get_current_price(ticker)
            currency = raw.get("currency")
            if not currency:
                raise CurrencyUnavailableError(ticker)
            return str(currency)
        except CurrencyUnavailableError:
            raise
        except Exception as exc:
            raise CurrencyUnavailableError(ticker) from exc

    def translate_current(
        self,
        ticker: str,
        response: PriceResponse,
        target_currency: str,
    ) -> PriceResponse:
        """Translate a current price response into the target currency."""
        native_currency = response.currency
        if native_currency == target_currency:
            logger.info(
                "fx_align_no_translation",
                ticker=ticker,
                currency=target_currency,
            )
            return response

        pair = f"{native_currency}{target_currency}"
        as_of = response.as_of_date
        window_start = as_of - timedelta(days=7)

        fx_series = self._fx_provider.get_price_history(pair, window_start, as_of)
        if not fx_series:
            raise CurrencyUnavailableError(
                ticker,
                f"No FX rate available for pair '{pair}' around {as_of}.",
            )

        _, rate = fx_series[-1]
        translated_price = round(response.price * rate, 6)

        logger.info(
            "currency_translation",
            ticker=ticker,
            native_currency=native_currency,
            target_currency=target_currency,
            fx_rate=rate,
        )

        return response.model_copy(
            update={
                "price": translated_price,
                "currency": target_currency,
                "fx_rate": rate,
            }
        )

    def translate_history(
        self,
        ticker: str,
        records: list[PricePoint],
        native_currency: str,
        target_currency: str,
        from_date: date,
        to_date: date,
    ) -> list[PricePoint]:
        """Translate each price record to target_currency using aligned FX rates."""
        pair = f"{native_currency}{target_currency}"

        logger.info(
            "fx_fetch",
            pair=pair,
            from_date=str(from_date),
            to_date=str(to_date),
        )

        fx_series = self._fx_provider.get_price_history(pair, from_date, to_date)
        fx_series = self._gap_fill.fill(fx_series, from_date, to_date)

        security_dates = [p.date for p in records]

        try:
            aligned = self._aligner.align_rates(pair, security_dates, fx_series)
        except FxAlignmentError as exc:
            logger.error(
                "fx_align_error",
                pair=pair,
                security_date=str(exc.security_date),
                error=exc.message,
            )
            raise

        translated: list[PricePoint] = []
        for price_point in records:
            aligned_rate = aligned[price_point.date]

            if aligned_rate.fill_direction != "exact":
                logger.info(
                    "fx_align_fill",
                    pair=pair,
                    security_date=str(price_point.date),
                    fx_date_used=str(aligned_rate.fx_date),
                    fill_direction=aligned_rate.fill_direction,
                )

            rate = aligned_rate.rate
            translated.append(
                PricePoint(
                    date=price_point.date,
                    close=round(price_point.close * rate, 6),
                    fx_rate=rate,
                )
            )

        return translated

    def build_translated_history(
        self,
        ticker: str,
        response: PriceHistoryResponse,
        target_currency: str,
        from_date: date,
        to_date: date,
    ) -> PriceHistoryResponse:
        """Convenience wrapper: translate a full PriceHistoryResponse."""
        native_currency = response.currency
        if native_currency == target_currency:
            logger.info(
                "fx_align_no_translation",
                ticker=ticker,
                currency=target_currency,
            )
            return response

        translated_prices = self.translate_history(
            ticker=ticker,
            records=response.prices,
            native_currency=native_currency,
            target_currency=target_currency,
            from_date=from_date,
            to_date=to_date,
        )
        return PriceHistoryResponse(
            ticker=response.ticker,
            currency=target_currency,
            prices=translated_prices,
        )
