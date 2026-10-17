from datetime import UTC, date, datetime, timedelta

from app.exceptions import DataNotFoundError, InvalidTickerError
from app.models.fill import FillMode
from app.models.pricing import PriceHistoryResponse, PricePoint, PriceResponse
from app.providers import PricingProvider
from app.providers.observation_window import ObservationWindow, ObservationWindowSource
from app.services.gap_fill import GapFillService
from app.services.minor_unit import SubUnitNormaliser
from app.services.series_fill import FillStrategyResolver


class PricingService:
    def __init__(
        self,
        provider: PricingProvider,
        gap_fill: GapFillService,
        normaliser: SubUnitNormaliser,
        fill_resolver: FillStrategyResolver,
    ) -> None:
        self._provider = provider
        self._gap_fill = gap_fill
        self._normaliser = normaliser
        self._fill_resolver = fill_resolver

    def get_current_price(self, ticker: str) -> PriceResponse:
        raw = self._provider.get_current_price(ticker)
        market_state = raw.get("market_state")
        market_status = "open" if str(market_state).upper() in ("OPEN", "REGULAR") else "closed"
        currency, price = self._normaliser.normalise(
            str(raw["currency"]), float(raw["price"])  # type: ignore[arg-type]
        )
        return PriceResponse(
            ticker=ticker,
            price=price,
            currency=currency,
            timestamp=datetime.now(tz=UTC),
            market_status=market_status,  # type: ignore[arg-type]
            as_of_date=raw["as_of_date"],  # type: ignore[arg-type]
        )

    def get_price_history(
        self,
        ticker: str,
        from_date: date | None = None,
        to_date: date | None = None,
        fill: FillMode = FillMode.ALL,
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
        filled = self._fill_resolver.resolve(fill).fill(raw, resolved_from, resolved_to)

        # FR-009: an empty series is a not-found response in both fill modes. Previously a
        # cached ticker queried outside its stored range returned 200 with an empty list,
        # contradicting the contract published with feature 006 (its FR-008).
        if not filled:
            raise DataNotFoundError(
                ticker,
                f"No price observations for ticker '{ticker}' between "
                f"{resolved_from} and {resolved_to}.",
            )

        currency = "USD"
        try:
            price_data = self._provider.get_current_price(ticker)
            c = price_data.get("currency")
            if isinstance(c, str) and c:
                currency = c
        except Exception:
            pass

        currency, filled = self._normaliser.normalise_series(currency, list(filled))
        prices = [PricePoint(date=d, close=v) for d, v in filled]

        window = self._observation_window(ticker, raw)
        return PriceHistoryResponse(
            ticker=ticker,
            currency=currency,
            prices=prices,
            first_observed_date=window.first_observed_date if window else None,
            last_observed_date=window.last_observed_date if window else None,
        )

    def _observation_window(
        self, ticker: str, raw: list[tuple[date, float]]
    ) -> ObservationWindow | None:
        """Resolve the instrument's known observation window.

        Queried *after* the history fetch so that any cache write performed while serving this
        request is already reflected, which is what makes a widened window appear with no extra
        bookkeeping (FR-015). Falls back to the extremes of the raw series just returned when the
        provider does not offer the capability — keeping plain PricingProvider doubles working.
        """
        if isinstance(self._provider, ObservationWindowSource):
            window = self._provider.observation_window(ticker)
            if window is not None:
                return window
        if not raw:
            return None
        dates = [d for d, _ in raw]
        return ObservationWindow(
            first_observed_date=min(dates), last_observed_date=max(dates)
        )
