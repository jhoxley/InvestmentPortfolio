from datetime import UTC, date, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Path, Query

from app.cache.repository import CacheRepository
from app.config import Settings, get_settings
from app.exceptions import InvalidCurrencyPairError, InvalidTickerError
from app.models.pricing import FxHistoryResponse, FxRateEntry
from app.providers.cached_provider import CachedPricingProvider
from app.providers.fx_provider import FxInnerProvider
from app.providers.yfinance_provider import YFinanceProvider
from app.services.gap_fill import GapFillService
from app.validators.currency import validate_currency_code

router = APIRouter(prefix="/fx", tags=["FX"])

_PAIR_PATTERN = r"^[A-Za-z]{6}$"

logger = structlog.get_logger(__name__)


def get_fx_provider(settings: Settings = Depends(get_settings)) -> CachedPricingProvider:
    repo = CacheRepository(settings.cache.directory)
    return CachedPricingProvider(FxInnerProvider(YFinanceProvider()), repo)


def get_fx_gap_fill_service() -> GapFillService:
    return GapFillService()


@router.get("/{pair}/history", response_model=FxHistoryResponse)
async def get_fx_history(
    pair: str = Path(..., min_length=6, max_length=6, pattern=_PAIR_PATTERN),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    fx_provider: CachedPricingProvider = Depends(get_fx_provider),
    gap_fill: GapFillService = Depends(get_fx_gap_fill_service),
) -> FxHistoryResponse:
    base = pair[:3].upper()
    quote = pair[3:].upper()
    validate_currency_code(base)
    validate_currency_code(quote)

    if base == quote:
        raise InvalidCurrencyPairError(pair.upper())

    today = datetime.now(tz=UTC).date()
    resolved_to = to_date or today
    resolved_from = from_date or (today - timedelta(days=30))

    if resolved_from > resolved_to:
        raise InvalidTickerError(
            pair,
            f"'from' date ({resolved_from}) must not be after 'to' date ({resolved_to}).",
        )

    pair_upper = pair.upper()
    logger.info(
        "fx_fetch",
        pair=pair_upper,
        from_date=str(resolved_from),
        to_date=str(resolved_to),
        source="endpoint",
    )

    records = fx_provider.get_price_history(pair_upper, resolved_from, resolved_to)
    filled = gap_fill.fill(records, resolved_from, resolved_to)

    return FxHistoryResponse(
        pair=pair_upper,
        base_currency=base,
        quote_currency=quote,
        rates=[FxRateEntry(date=d, rate=r) for d, r in filled],
    )
