from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from app.models.pricing import PriceHistoryResponse, PriceResponse
from app.providers.yfinance_provider import YFinanceProvider
from app.services.pricing_service import PricingService

router = APIRouter(prefix="/securities", tags=["Securities"])

_TICKER_PATTERN = r"^[A-Za-z0-9.\-\^=]+$"


def get_pricing_service() -> PricingService:
    return PricingService(provider=YFinanceProvider())


@router.get("/{ticker}/price", response_model=PriceResponse)
async def get_current_price(
    ticker: str = Path(..., min_length=1, pattern=_TICKER_PATTERN),
    service: PricingService = Depends(get_pricing_service),
) -> PriceResponse:
    return service.get_current_price(ticker)


@router.get("/{ticker}/history", response_model=PriceHistoryResponse)
async def get_price_history(
    ticker: str = Path(..., min_length=1, pattern=_TICKER_PATTERN),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    service: PricingService = Depends(get_pricing_service),
) -> PriceHistoryResponse:
    return service.get_price_history(ticker, from_date, to_date)
