"""API router for VaR calculation runs and status (feature 012)."""

from datetime import date
from typing import Any

import structlog.contextvars
from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.dependencies import (
    get_capital_repository,
    get_ladder_repository,
    get_observed_price_client,
    get_run_scheduler,
    get_var_repository,
)
from app.api.ladder import _get_identifier_mapping_repository
from app.clients.market_data_client import ObservedPriceClient
from app.config import Settings, VarSettings, get_settings
from app.exceptions import InvalidVarQueryError, InvalidVarRunRequestError, VarRunNotFoundError
from app.models.var import VarRun, VarRunList, VarRunRequest, VarStatus
from app.models.var_series import VarBacktestResponse, VarMethodsResponse, VarSeriesResponse
from app.repositories.capital_repository import CapitalRepository
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository
from app.repositories.ladder_repository import LadderRepository
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.run_scheduler import RunScheduler
from app.services.var.var_backtest_service import VarBacktestService
from app.services.var.var_methods_service import build_methods_response
from app.services.var.var_run_service import VarRunService
from app.services.var.var_series_service import VarSeriesService
from app.services.var.var_status_service import VarStatusService
from app.validators.account_name import validate_account_name

router = APIRouter(prefix="/v1", tags=["Risk"])


def _get_var_run_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
    mapping_repo: IdentifierMappingRepository = Depends(_get_identifier_mapping_repository),
    observed_price_client: ObservedPriceClient = Depends(get_observed_price_client),
    var_repo: VarRepository = Depends(get_var_repository),
    scheduler: RunScheduler = Depends(get_run_scheduler),
    settings: Settings = Depends(get_settings),
) -> VarRunService:
    """Dependency that returns a wired VarRunService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).
        mapping_repo: IdentifierMappingRepository instance (injected by FastAPI).
        observed_price_client: ObservedPriceClient instance (injected by FastAPI).
        var_repo: VarRepository instance (injected by FastAPI).
        scheduler: RunScheduler instance (injected by FastAPI).
        settings: Application settings (injected by FastAPI).

    Returns:
        VarRunService instance.
    """
    return VarRunService(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        identifier_mapping_repo=mapping_repo,
        observed_price_client=observed_price_client,
        var_repo=var_repo,
        scheduler=scheduler,
        settings=settings.var,
    )


def _get_var_status_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
    var_repo: VarRepository = Depends(get_var_repository),
) -> VarStatusService:
    """Dependency that returns a wired VarStatusService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).
        var_repo: VarRepository instance (injected by FastAPI).

    Returns:
        VarStatusService instance.
    """
    return VarStatusService(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        var_repo=var_repo,
    )


def _get_var_series_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
    var_repo: VarRepository = Depends(get_var_repository),
    settings: Settings = Depends(get_settings),
) -> VarSeriesService:
    """Dependency that returns a wired VarSeriesService (013-var-series-backtest-api).

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).
        var_repo: VarRepository instance (injected by FastAPI).
        settings: Application settings (injected by FastAPI).

    Returns:
        VarSeriesService instance.
    """
    return VarSeriesService(
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        var_repo=var_repo,
        settings=settings.var,
    )


def _get_var_backtest_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
    var_repo: VarRepository = Depends(get_var_repository),
    settings: Settings = Depends(get_settings),
) -> VarBacktestService:
    """Dependency that returns a wired VarBacktestService (013-var-series-backtest-api).

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).
        var_repo: VarRepository instance (injected by FastAPI).
        settings: Application settings (injected by FastAPI).

    Returns:
        VarBacktestService instance.
    """
    return VarBacktestService(
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        var_repo=var_repo,
        settings=settings.var,
    )


def _resolve_lookback(lookback: str | None, settings: VarSettings) -> str:
    """Resolve and validate the `lookback` query parameter (FR-003, FR-009, FR-021).

    Args:
        lookback: The caller-supplied look-back code, or None for the headline default.
        settings: The application's VaR configuration.

    Returns:
        The resolved look-back code.

    Raises:
        InvalidVarQueryError: lookback is not one of the currently configured codes.
    """
    code = lookback or settings.headline_lookback
    if code not in settings.lookbacks:
        supported = ", ".join(sorted(settings.lookbacks))
        raise InvalidVarQueryError(
            message=f"lookback '{code}' is not one of the configured look-backs: {supported}",
            fields=["lookback"],
        )
    return code


def _format_pct(confidence_bp: int) -> str:
    """Format a basis-point confidence level as a plain percentage string (e.g. 9750 -> '97.5')."""
    return f"{confidence_bp / 100:g}"


def _resolve_confidence_levels(confidence: list[str] | None, settings: VarSettings) -> list[int]:
    """Resolve and validate the repeatable `confidence` query parameter (FR-004, FR-009, FR-021).

    Args:
        confidence: Caller-supplied confidence levels as percentage strings (e.g. "95",
            "97.5", "90%"), or None for every configured level.
        settings: The application's VaR configuration.

    Returns:
        Confidence levels in basis points.

    Raises:
        InvalidVarQueryError: A value is not one of the currently configured levels.
    """
    if confidence is None:
        return list(settings.confidence_levels_bp)

    supported = ", ".join(_format_pct(bp) for bp in sorted(settings.confidence_levels_bp))
    levels_bp: list[int] = []
    for raw in confidence:
        try:
            bp = round(float(raw.rstrip("%")) * 100)
        except ValueError as exc:
            raise InvalidVarQueryError(
                message=f"confidence '{raw}' is not one of the configured levels: {supported}",
                fields=["confidence"],
            ) from exc
        if bp not in settings.confidence_levels_bp:
            raise InvalidVarQueryError(
                message=f"confidence '{raw}' is not one of the configured levels: {supported}",
                fields=["confidence"],
            )
        levels_bp.append(bp)
    return levels_bp


def _resolve_pnl_basis(pnl_basis: str | None) -> str:
    """Resolve and validate the `pnl_basis` query parameter (FR-017, FR-021).

    Args:
        pnl_basis: The caller-supplied value, or None for the "hypothetical" default.

    Returns:
        "hypothetical" or "ladder".

    Raises:
        InvalidVarQueryError: pnl_basis is neither "hypothetical" nor "ladder".
    """
    value = pnl_basis or "hypothetical"
    if value not in ("hypothetical", "ladder"):
        raise InvalidVarQueryError(
            message=f"pnl_basis '{value}' is not one of the supported values: hypothetical, ladder",
            fields=["pnl_basis"],
        )
    return value


def _resolve_min_quality(min_quality: str | None) -> str:
    """Resolve and validate the `min_quality` query parameter (FR-018, FR-021).

    Args:
        min_quality: The caller-supplied value, or None for the "degraded" default.

    Returns:
        "ok" or "degraded".

    Raises:
        InvalidVarQueryError: min_quality is neither "ok" nor "degraded".
    """
    value = min_quality or "degraded"
    if value not in ("ok", "degraded"):
        raise InvalidVarQueryError(
            message=f"min_quality '{value}' is not one of the supported values: ok, degraded",
            fields=["min_quality"],
        )
    return value


def _correlation_id() -> str:
    """Return the correlation ID bound by the request-logging middleware.

    Returns:
        The current request's correlation ID, or "" if none is bound.
    """
    return str(structlog.contextvars.get_contextvars().get("correlation_id", ""))


@router.post(
    "/accounts/{account_name}/risk/var/runs",
    response_model=VarRun,
    status_code=202,
    summary="Queue a historical-simulation VaR calculation run for an account",
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        409: {"description": "The account already has a queued or running VaR calculation run"},
        422: {
            "description": (
                "Validation failed — invalid account name, no ingested position ladder, "
                "or an invalid run request (unknown mode, start after end)"
            )
        },
    },
)
async def create_var_run(
    account_name: str,
    body: dict[str, Any] | None = Body(default=None),
    service: VarRunService = Depends(_get_var_run_service),
) -> JSONResponse:
    """Queue a VaR calculation run and return immediately.

    Args:
        account_name: Path parameter identifying the account.
        body: Optional run request body (mode, start, end); validated here rather than
            by FastAPI's native body parsing so a malformed body produces the same RFC
            7807 shape as every other validation failure in this feature (not FastAPI's
            default 422 envelope).
        service: Injected VarRunService.

    Returns:
        202 with the created VarRun JSON body and a Location header.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        InvalidVarRunRequestError: The body fails validation, or start is after end.
        AccountNotFoundError: No resource of any kind ingested for this account.
        MissingRequiredSourceError: The account has no ingested position ladder.
        VarRunInProgressError: The account already has an active run.
    """
    validate_account_name(account_name)
    try:
        request = VarRunRequest.model_validate(body or {})
    except ValidationError as exc:
        raise InvalidVarRunRequestError(message=f"Invalid run request: {exc}") from exc

    run = service.create_run(
        account_name=account_name,
        request=request,
        today=date.today(),
        correlation_id=_correlation_id(),
    )
    return JSONResponse(
        status_code=202,
        content=run.model_dump(by_alias=True, mode="json"),
        headers={"Location": run.links["self"]},
    )


@router.get(
    "/accounts/{account_name}/risk/var/runs/{run_id}",
    response_model=VarRun,
    summary="Read a VaR calculation run's status and outcome",
    responses={404: {"description": "Unknown account or run"}},
)
async def get_var_run(
    account_name: str,
    run_id: str,
    var_repo: VarRepository = Depends(get_var_repository),
) -> JSONResponse:
    """Return one run's current status.

    Args:
        account_name: Path parameter identifying the account.
        run_id: Path parameter identifying the run.
        var_repo: Injected VarRepository.

    Returns:
        200 with the VarRun JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        VarRunNotFoundError: No such run exists for this account.
    """
    validate_account_name(account_name)
    run = var_repo.read_run(account_name, run_id)
    if run is None:
        raise VarRunNotFoundError(account_name=account_name, run_id=run_id)
    return JSONResponse(status_code=200, content=run.model_dump(by_alias=True, mode="json"))


@router.get(
    "/accounts/{account_name}/risk/var/runs",
    response_model=VarRunList,
    summary="List an account's VaR calculation runs, newest first",
    responses={
        422: {"description": "Validation failed — invalid account name or limit out of range"}
    },
)
async def list_var_runs(
    account_name: str,
    limit: int | None = None,
    var_repo: VarRepository = Depends(get_var_repository),
) -> JSONResponse:
    """List every run recorded for an account, newest first.

    Args:
        account_name: Path parameter identifying the account.
        limit: Maximum number of runs to return (1-100, default 20).
        var_repo: Injected VarRepository.

    Returns:
        200 with a VarRunList JSON body (empty list if none exist).

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        InvalidVarRunRequestError: limit is outside 1-100.
    """
    validate_account_name(account_name)
    resolved_limit = 20 if limit is None else limit
    if not 1 <= resolved_limit <= 100:
        raise InvalidVarRunRequestError(
            message=f"limit must be between 1 and 100 (got {resolved_limit}).",
            fields=["limit"],
        )
    runs = var_repo.list_runs(account_name)[:resolved_limit]
    body = VarRunList(
        account_name=account_name,
        runs=runs,
        _links={
            "self": f"/v1/accounts/{account_name}/risk/var/runs",
            "status": f"/v1/accounts/{account_name}/risk/var/status",
        },
    )
    return JSONResponse(status_code=200, content=body.model_dump(by_alias=True, mode="json"))


@router.get(
    "/accounts/{account_name}/risk/var/status",
    response_model=VarStatus,
    summary="Report VaR coverage and freshness for an account",
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        422: {"description": "Validation failed — invalid account name"},
    },
)
async def get_var_status(
    account_name: str,
    service: VarStatusService = Depends(_get_var_status_service),
) -> JSONResponse:
    """Return the account's VaR coverage, freshness and per-instrument treatment.

    Args:
        account_name: Path parameter identifying the account.
        service: Injected VarStatusService.

    Returns:
        200 with the VarStatus JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        AccountNotFoundError: No resource of any kind ingested for this account.
        MissingRequiredSourceError: The account has no ingested position ladder.
    """
    validate_account_name(account_name)
    status = service.get_status(account_name)
    return JSONResponse(status_code=200, content=status.model_dump(by_alias=True, mode="json"))


@router.get(
    "/accounts/{account_name}/risk/var",
    response_model=VarSeriesResponse,
    summary="Read an account's previously computed VaR/ES series and realised outcomes",
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        422: {
            "description": (
                "Validation failed — invalid account name, no ingested position ladder, "
                "an invalid date range, or an unsupported lookback/confidence value"
            )
        },
    },
)
async def get_var_series(
    account_name: str,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    lookback: str | None = Query(default=None),
    confidence: list[str] | None = Query(default=None),
    service: VarSeriesService = Depends(_get_var_series_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Return the previously computed VaR/ES series for the requested account and window.

    Never triggers a calculation (FR-023). If nothing has been computed, returns a
    successful, empty series with links to the status and runs resources (FR-008).

    Args:
        account_name: Path parameter identifying the account.
        start: Optional start date (resolved as for the performance endpoints).
        end: Optional end date (resolved as for the performance endpoints).
        lookback: Optional look-back code; defaults to the configured headline.
        confidence: Optional repeatable confidence levels as percentages; defaults to
            every configured level.
        service: Injected VarSeriesService.
        settings: Application settings (injected by FastAPI).

    Returns:
        200 with the VarSeriesResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        InvalidVarQueryError: lookback or confidence is not a configured value.
        AccountNotFoundError: No resource of any kind ingested for this account.
        MissingRequiredSourceError: The account has no ingested position ladder.
        FutureEndDateError: end is later than today.
        InvalidDateRangeError: Resolved start is after resolved end.
    """
    validate_account_name(account_name)
    lookback_code = _resolve_lookback(lookback, settings.var)
    confidence_levels_bp = _resolve_confidence_levels(confidence, settings.var)

    response = service.get_series(
        account_name=account_name,
        start=start,
        end=end,
        lookback=lookback_code,
        confidence_levels_bp=confidence_levels_bp,
        today=date.today(),
    )
    return JSONResponse(status_code=200, content=response.model_dump(by_alias=True, mode="json"))


@router.get(
    "/accounts/{account_name}/risk/var/backtest",
    response_model=VarBacktestResponse,
    summary="Backtest an account's VaR estimates against realised outcomes",
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        422: {
            "description": (
                "Validation failed — invalid account name, no ingested position ladder, "
                "an invalid date range, or an unsupported lookback/confidence/pnl_basis/"
                "min_quality value"
            )
        },
    },
)
async def get_var_backtest(
    account_name: str,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    lookback: str | None = Query(default=None),
    confidence: list[str] | None = Query(default=None),
    pnl_basis: str | None = Query(default=None),
    min_quality: str | None = Query(default=None),
    rolling: bool = Query(default=False),
    service: VarBacktestService = Depends(_get_var_backtest_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Backtest the account's VaR estimates against realised outcomes.

    Never triggers a calculation (FR-023).

    Args:
        account_name: Path parameter identifying the account.
        start: Optional start date (resolved as for the performance endpoints).
        end: Optional end date (resolved as for the performance endpoints).
        lookback: Optional look-back code; defaults to the configured headline.
        confidence: Optional repeatable confidence levels as percentages; defaults to
            every configured level.
        pnl_basis: "hypothetical" (default) or "ladder".
        min_quality: "ok" or "degraded" (default).
        rolling: Whether to include the 250-day rolling exception count series.
        service: Injected VarBacktestService.
        settings: Application settings (injected by FastAPI).

    Returns:
        200 with the VarBacktestResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        InvalidVarQueryError: lookback, confidence, pnl_basis or min_quality is not a
            configured/supported value.
        AccountNotFoundError: No resource of any kind ingested for this account.
        MissingRequiredSourceError: The account has no ingested position ladder.
        FutureEndDateError: end is later than today.
        InvalidDateRangeError: Resolved start is after resolved end.
    """
    validate_account_name(account_name)
    lookback_code = _resolve_lookback(lookback, settings.var)
    confidence_levels_bp = _resolve_confidence_levels(confidence, settings.var)
    resolved_pnl_basis = _resolve_pnl_basis(pnl_basis)
    resolved_min_quality = _resolve_min_quality(min_quality)

    response = service.get_backtest(
        account_name=account_name,
        start=start,
        end=end,
        lookback=lookback_code,
        confidence_levels_bp=confidence_levels_bp,
        pnl_basis=resolved_pnl_basis,
        min_quality=resolved_min_quality,
        rolling=rolling,
        today=date.today(),
    )
    return JSONResponse(status_code=200, content=response.model_dump(by_alias=True, mode="json"))


@router.get(
    "/risk/var/methods",
    response_model=VarMethodsResponse,
    summary="Describe the supported VaR calculation method, look-backs and measures",
)
async def get_var_methods(settings: Settings = Depends(get_settings)) -> JSONResponse:
    """Return the configured VaR method, look-backs, confidence levels and measures.

    Requires no account and always succeeds (FR-022).

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        200 with the VarMethodsResponse JSON body.
    """
    response = build_methods_response(settings.var)
    return JSONResponse(status_code=200, content=response.model_dump(by_alias=True, mode="json"))
