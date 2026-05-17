from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from app.cache.repository import CacheRepository
from app.config import Settings, get_settings
from app.models.pricing import PriceHistoryResponse, PriceResponse
from app.providers.cached_provider import CachedPricingProvider
from app.providers.fx_provider import FxInnerProvider
from app.providers.yfinance_provider import YFinanceProvider
from app.services.currency_service import CurrencyService
from app.services.fx_aligner import FxAligner
from app.services.gap_fill import GapFillService
from app.services.pricing_service import PricingService
from app.validators.currency import validate_currency_code

router = APIRouter(prefix="/securities", tags=["Securities"])

_TICKER_PATTERN = r"^[A-Za-z0-9.\-\^=]+$"


def get_pricing_service(settings: Settings = Depends(get_settings)) -> PricingService:
    repo = CacheRepository(settings.cache.directory)
    provider = CachedPricingProvider(YFinanceProvider(), repo)
    return PricingService(provider=provider, gap_fill=GapFillService())


def get_currency_service(settings: Settings = Depends(get_settings)) -> CurrencyService:
    repo = CacheRepository(settings.cache.directory)
    fx_provider = CachedPricingProvider(FxInnerProvider(YFinanceProvider()), repo)
    return CurrencyService(fx_provider=fx_provider, aligner=FxAligner(), gap_fill=GapFillService())


@router.get("/{ticker}/price", response_model=PriceResponse)
async def get_current_price(
    ticker: str = Path(..., min_length=1, pattern=_TICKER_PATTERN),
    currency: str | None = Query(default=None),
    service: PricingService = Depends(get_pricing_service),
    currency_svc: CurrencyService = Depends(get_currency_service),
) -> PriceResponse:
    if currency is not None:
        validate_currency_code(currency)
    response = service.get_current_price(ticker)
    if currency is not None and currency != response.currency:
        return currency_svc.translate_current(ticker, response, currency)
    return response


@router.get("/{ticker}/history", response_model=PriceHistoryResponse)
async def get_price_history(
    ticker: str = Path(..., min_length=1, pattern=_TICKER_PATTERN),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    currency: str | None = Query(default=None),
    service: PricingService = Depends(get_pricing_service),
    currency_svc: CurrencyService = Depends(get_currency_service),
) -> PriceHistoryResponse:
    if currency is not None:
        validate_currency_code(currency)
    response = service.get_price_history(ticker, from_date, to_date)
    if currency is not None and currency != response.currency:
        from datetime import UTC, datetime, timedelta

        today = datetime.now(tz=UTC).date()
        resolved_to = to_date or today
        resolved_from = from_date or (today - timedelta(days=30))
        return currency_svc.build_translated_history(
            ticker, response, currency, resolved_from, resolved_to
        )
    return response
