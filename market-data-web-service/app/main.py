import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api import securities
from app.exceptions import DataNotFoundError, InvalidTickerError, ProviderUnavailableError
from app.logging_config import setup_logging
from app.models.pricing import ErrorResponse

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    yield


app = FastAPI(
    title="Market Data API",
    description="Locally hosted security pricing API backed by Yahoo Finance (yfinance).",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(securities.router)


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
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
        content=ErrorResponse(detail=exc.message, code="TICKER_NOT_FOUND").model_dump(exclude_none=True),
    )


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_handler(request: Request, exc: ProviderUnavailableError) -> JSONResponse:
    logger.error("provider_unavailable", detail=exc.message)
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(detail=exc.message, code="PROVIDER_UNAVAILABLE").model_dump(exclude_none=True),
    )


@app.exception_handler(InvalidTickerError)
async def invalid_ticker_handler(request: Request, exc: InvalidTickerError) -> JSONResponse:
    logger.error("invalid_ticker", ticker=exc.ticker, detail=exc.message)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(detail=exc.message, code="INVALID_TICKER").model_dump(exclude_none=True),
    )
