from datetime import UTC, date, datetime, timedelta

from app.exceptions import InvalidTickerError
from app.models.pricing import PriceHistoryResponse, PricePoint, PriceResponse
from app.providers import PricingProvider


class PricingService:
    def __init__(self, provider: PricingProvider) -> None:
        self._provider = provider

    def get_current_price(self, ticker: str) -> PriceResponse:
        raw = self._provider.get_current_price(ticker)
        market_state = raw.get("market_state")
        market_status = "open" if str(market_state).upper() in ("OPEN", "REGULAR") else "closed"
        return PriceResponse(
            ticker=ticker,
            price=float(raw["price"]),  # type: ignore[arg-type]
            currency=str(raw["currency"]),
            timestamp=datetime.now(tz=UTC),
            market_status=market_status,  # type: ignore[arg-type]
            as_of_date=raw["as_of_date"],  # type: ignore[arg-type]
        )

    def get_price_history(
        self,
        ticker: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> PriceHistoryResponse:
        today = datetime.now(tz=UTC).date()
        resolved_to = to_date or today
        resolved_from = from_date or (today - timedelta(days=30))

        if resolved_from > resolved_to:
            raise InvalidTickerError(
                ticker,
                f"'from' date ({resolved_from}) must not be after 'to' date ({resolved_to})",
            )

        raw = self._provider.get_price_history(ticker, resolved_from, resolved_to)

        currency = "USD"
        try:
            price_data = self._provider.get_current_price(ticker)
            c = price_data.get("currency")
            if isinstance(c, str) and c:
                currency = c
        except Exception:
            pass

        prices = [PricePoint(date=d, close=v) for d, v in raw]
        return PriceHistoryResponse(ticker=ticker, currency=currency, prices=prices)
