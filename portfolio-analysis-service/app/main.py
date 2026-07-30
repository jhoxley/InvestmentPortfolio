"""FastAPI application entry point for the portfolio analysis service."""

import time
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
import structlog.contextvars
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api import (
    accounts,
    capital,
    health,
    ladder,
    performance,
    position_timeseries,
    timeseries,
)
from app.config import get_settings
from app.exceptions import (
    AccountNotFoundError,
    EmptyCapitalDateRangeError,
    EmptyDateRangeError,
    FutureEndDateError,
    IdentifierMappingError,
    InvalidAccountNameError,
    InvalidDateRangeError,
    MarketDataServiceError,
    MergeNotSupportedError,
    MissingRequiredSourceError,
    NoAttributesRequestedError,
    PositionLadderNotIngestedError,
    PriceCoverageError,
    SchemaValidationError,
    UnsupportedAttributeError,
)
from app.logging_config import setup_logging
from app.models.ladder import ProblemDetail

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Configure logging, load settings, and ensure the data directory exists.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the running application.
    """
    setup_logging()
    settings = get_settings()
    settings.data.directory.mkdir(parents=True, exist_ok=True)
    logger.info("startup_complete", data_dir=str(settings.data.directory))
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Portfolio Analysis API",
    description="Locally hosted API for portfolio analysis features.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ladder.router)
app.include_router(capital.router)
app.include_router(timeseries.router)
app.include_router(accounts.router)
app.include_router(position_timeseries.router)
app.include_router(performance.router)
app.include_router(health.router)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log every HTTP request/response with a per-request correlation ID.

    Generates a UUID correlation_id, binds it to the structlog context so that
    all log calls within the same request automatically carry it. Logs method,
    path, status code, duration, and correlation_id on completion.

    Args:
        request: Incoming HTTP request.
        call_next: Next middleware or route handler.

    Returns:
        The HTTP response, unmodified.
    """
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)

    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
        correlation_id=correlation_id,
    )
    return response


def _problem(
    request: Request, status: int, type_slug: str, title: str, detail: str
) -> JSONResponse:
    """Build an RFC 7807 ProblemDetail JSON response.

    Args:
        request: The originating request (used for the instance field).
        status: HTTP status code.
        type_slug: Slug appended to the base error URI.
        title: Short human-readable summary.
        detail: Full explanation of the error.

    Returns:
        JSONResponse with application/problem+json content type.
    """
    problem = ProblemDetail(
        type=f"https://portfolio-analysis/errors/{type_slug}",
        title=title,
        status=status,
        detail=detail,
        instance=str(request.url.path),
    )
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


@app.exception_handler(InvalidAccountNameError)
async def invalid_account_name_handler(
    request: Request, exc: InvalidAccountNameError
) -> JSONResponse:
    """Handle InvalidAccountNameError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning("invalid_account_name", account_name=exc.account_name, detail=exc.message)
    return _problem(request, 422, "invalid-account-name", "Invalid Account Name", exc.message)


@app.exception_handler(SchemaValidationError)
async def schema_validation_handler(request: Request, exc: SchemaValidationError) -> JSONResponse:
    """Handle SchemaValidationError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning("schema_validation_error", fields=exc.fields, detail=exc.message)
    return _problem(
        request, 422, "schema-validation-failed", "Schema Validation Failed", exc.message
    )


@app.exception_handler(EmptyDateRangeError)
async def empty_date_range_handler(request: Request, exc: EmptyDateRangeError) -> JSONResponse:
    """Handle EmptyDateRangeError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning(
        "empty_date_range",
        account_name=exc.account_name,
        earliest_date=str(exc.earliest_date),
        detail=exc.message,
    )
    return _problem(request, 422, "empty-date-range", "Empty Date Range", exc.message)


@app.exception_handler(EmptyCapitalDateRangeError)
async def empty_capital_date_range_handler(
    request: Request, exc: EmptyCapitalDateRangeError
) -> JSONResponse:
    """Handle EmptyCapitalDateRangeError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning(
        "empty_capital_date_range",
        account_name=exc.account_name,
        earliest_date=str(exc.earliest_date),
        latest_date=str(exc.latest_date),
        detail=exc.message,
    )
    return _problem(
        request, 422, "empty-capital-date-range", "Empty Capital Date Range", exc.message
    )


@app.exception_handler(AccountNotFoundError)
async def account_not_found_handler(request: Request, exc: AccountNotFoundError) -> JSONResponse:
    """Handle AccountNotFoundError with a 404 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 404 Not Found response.
    """
    logger.info("account_not_found", account_name=exc.account_name, detail=exc.message)
    return _problem(request, 404, "account-not-found", "Account Not Found", exc.message)


@app.exception_handler(MergeNotSupportedError)
async def merge_not_supported_handler(
    request: Request, exc: MergeNotSupportedError
) -> JSONResponse:
    """Handle MergeNotSupportedError with a 409 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 409 Conflict response.
    """
    logger.warning("merge_not_supported", account_name=exc.account_name, detail=exc.message)
    return _problem(request, 409, "merge-not-supported", "Merge Not Supported", exc.message)


@app.exception_handler(IdentifierMappingError)
async def identifier_mapping_error_handler(
    request: Request, exc: IdentifierMappingError
) -> JSONResponse:
    """Handle IdentifierMappingError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning("identifier_mapping_error", sub_accounts=exc.sub_accounts, detail=exc.message)
    return _problem(
        request, 422, "identifier-mapping-failed", "Identifier Mapping Failed", exc.message
    )


@app.exception_handler(PriceCoverageError)
async def price_coverage_error_handler(request: Request, exc: PriceCoverageError) -> JSONResponse:
    """Handle PriceCoverageError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning(
        "price_coverage_error",
        sub_accounts=list(exc.problems.keys()),
        detail=exc.message,
    )
    return _problem(request, 422, "price-coverage-failed", "Price Coverage Failed", exc.message)


@app.exception_handler(NoAttributesRequestedError)
async def no_attributes_requested_handler(
    request: Request, exc: NoAttributesRequestedError
) -> JSONResponse:
    """Handle NoAttributesRequestedError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning("no_attributes_requested", detail=exc.message)
    return _problem(request, 422, "no-attributes-requested", "No Attributes Requested", exc.message)


@app.exception_handler(UnsupportedAttributeError)
async def unsupported_attribute_handler(
    request: Request, exc: UnsupportedAttributeError
) -> JSONResponse:
    """Handle UnsupportedAttributeError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning("unsupported_attribute", requested=exc.requested, detail=exc.message)
    return _problem(request, 422, "unsupported-attribute", "Unsupported Attribute", exc.message)


@app.exception_handler(FutureEndDateError)
async def future_end_date_handler(request: Request, exc: FutureEndDateError) -> JSONResponse:
    """Handle FutureEndDateError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning("future_end_date", end=str(exc.end), today=str(exc.today), detail=exc.message)
    return _problem(request, 422, "future-end-date", "Future End Date", exc.message)


@app.exception_handler(InvalidDateRangeError)
async def invalid_date_range_handler(request: Request, exc: InvalidDateRangeError) -> JSONResponse:
    """Handle InvalidDateRangeError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning("invalid_date_range", start=str(exc.start), end=str(exc.end), detail=exc.message)
    return _problem(request, 422, "invalid-date-range", "Invalid Date Range", exc.message)


@app.exception_handler(MissingRequiredSourceError)
async def missing_required_source_handler(
    request: Request, exc: MissingRequiredSourceError
) -> JSONResponse:
    """Handle MissingRequiredSourceError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning(
        "missing_required_source",
        account_name=exc.account_name,
        attribute=exc.attribute,
        source=exc.source,
        detail=exc.message,
    )
    return _problem(request, 422, "missing-required-source", "Missing Required Source", exc.message)


@app.exception_handler(PositionLadderNotIngestedError)
async def position_ladder_not_ingested_handler(
    request: Request, exc: PositionLadderNotIngestedError
) -> JSONResponse:
    """Handle PositionLadderNotIngestedError with a 422 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 422 Unprocessable Entity response.
    """
    logger.warning(
        "position_ladder_not_ingested", account_name=exc.account_name, detail=exc.message
    )
    return _problem(
        request, 422, "position-ladder-not-ingested", "Position Ladder Not Ingested", exc.message
    )


@app.exception_handler(MarketDataServiceError)
async def market_data_service_error_handler(
    request: Request, exc: MarketDataServiceError
) -> JSONResponse:
    """Handle MarketDataServiceError with a 502 response.

    Args:
        request: The originating HTTP request.
        exc: The raised exception.

    Returns:
        RFC 7807 502 Bad Gateway response.
    """
    logger.error("market_data_service_error", sub_account=exc.sub_account, detail=exc.message)
    return _problem(
        request,
        502,
        "market-data-service-unavailable",
        "Market Data Service Unavailable",
        exc.message,
    )
