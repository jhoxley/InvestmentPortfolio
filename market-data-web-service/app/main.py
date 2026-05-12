import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api import cache, fx, identifiers, securities
from app.config import load_settings
from app.exceptions import (
    CurrencyUnavailableError,
    DataNotFoundError,
    FxAlignmentError,
    IdentifierFormatError,
    IdentifierNotFoundError,
    InvalidCurrencyError,
    InvalidCurrencyPairError,
    InvalidTickerError,
    ProviderUnavailableError,
)
from app.logging_config import setup_logging
from app.models.pricing import ErrorResponse

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    settings = load_settings()
    settings.cache.directory.mkdir(parents=True, exist_ok=True)
    logger.info("cache_dir_ready", path=str(settings.cache.directory))
    yield


app = FastAPI(
    title="Market Data API",
    description="Locally hosted security pricing API backed by Yahoo Finance (yfinance).",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(securities.router)
app.include_router(cache.router)
app.include_router(fx.router)
app.include_router(identifiers.router)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.exception_handler(DataNotFoundError)
async def data_not_found_handler(request: Request, exc: DataNotFoundError) -> JSONResponse:
    logger.error("data_not_found", ticker=exc.ticker, detail=exc.message)
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(detail=exc.message, code="TICKER_NOT_FOUND").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_handler(
    request: Request, exc: ProviderUnavailableError
) -> JSONResponse:
    logger.error("provider_unavailable", detail=exc.message)
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(detail=exc.message, code="PROVIDER_UNAVAILABLE").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(InvalidTickerError)
async def invalid_ticker_handler(request: Request, exc: InvalidTickerError) -> JSONResponse:
    logger.error("invalid_ticker", ticker=exc.ticker, detail=exc.message)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(detail=exc.message, code="INVALID_TICKER").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(InvalidCurrencyError)
async def invalid_currency_handler(
    request: Request, exc: InvalidCurrencyError
) -> JSONResponse:
    logger.warning("invalid_currency", code=exc.code, detail=exc.message)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(detail=exc.message, code="INVALID_CURRENCY").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(InvalidCurrencyPairError)
async def invalid_currency_pair_handler(
    request: Request, exc: InvalidCurrencyPairError
) -> JSONResponse:
    logger.warning("invalid_currency_pair", pair=exc.pair, detail=exc.message)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(detail=exc.message, code="INVALID_CURRENCY_PAIR").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(FxAlignmentError)
async def fx_alignment_error_handler(
    request: Request, exc: FxAlignmentError
) -> JSONResponse:
    logger.error(
        "fx_alignment_error",
        pair=exc.pair,
        security_date=str(exc.security_date),
        detail=exc.message,
    )
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(detail=exc.message, code="FX_ALIGNMENT_ERROR").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(CurrencyUnavailableError)
async def currency_unavailable_handler(
    request: Request, exc: CurrencyUnavailableError
) -> JSONResponse:
    logger.error("currency_unavailable", ticker=exc.ticker, detail=exc.message)
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(detail=exc.message, code="CURRENCY_UNAVAILABLE").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(IdentifierFormatError)
async def identifier_format_handler(
    request: Request, exc: IdentifierFormatError
) -> JSONResponse:
    logger.warning("identifier_format_error", identifier=exc.identifier, detail=exc.message)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(detail=exc.message, code="IDENTIFIER_FORMAT_ERROR").model_dump(
            exclude_none=True
        ),
    )


@app.exception_handler(IdentifierNotFoundError)
async def identifier_not_found_handler(
    request: Request, exc: IdentifierNotFoundError
) -> JSONResponse:
    logger.error("identifier_not_found", identifier=exc.identifier, detail=exc.message)
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(detail=exc.message, code="IDENTIFIER_NOT_FOUND").model_dump(
            exclude_none=True
        ),
    )
