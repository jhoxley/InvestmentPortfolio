import structlog
from fastapi import APIRouter, Depends, Path

from app.cache.repository import CacheRepository
from app.config import Settings, get_settings
from app.models.pricing import CacheClearResponse, CacheDeleteResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/cache", tags=["Cache Management"])

_TICKER_PATTERN = r"^[A-Za-z0-9.\-\^=]+$"


@router.delete("/{ticker}", response_model=CacheDeleteResponse)
async def delete_ticker_cache(
    ticker: str = Path(..., min_length=1, pattern=_TICKER_PATTERN),
    settings: Settings = Depends(get_settings),
) -> CacheDeleteResponse:
    repo = CacheRepository(settings.cache.directory)
    deleted = repo.delete(ticker)
    logger.info("cache_delete_ticker", ticker=ticker, deleted=deleted)
    return CacheDeleteResponse(ticker=ticker, deleted=deleted)


@router.delete("", response_model=CacheClearResponse)
async def clear_all_cache(
    settings: Settings = Depends(get_settings),
) -> CacheClearResponse:
    repo = CacheRepository(settings.cache.directory)
    count = repo.delete_all()
    logger.info("cache_delete_all", deleted_count=count)
    return CacheClearResponse(deleted_count=count)
