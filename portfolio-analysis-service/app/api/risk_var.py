"""API router for VaR calculation runs and status (feature 012)."""

from datetime import date
from typing import Any

import structlog.contextvars
from fastapi import APIRouter, Body, Depends
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
from app.config import Settings, get_settings
from app.exceptions import InvalidVarRunRequestError, VarRunNotFoundError
from app.models.var import VarRun, VarRunList, VarRunRequest, VarStatus
from app.repositories.capital_repository import CapitalRepository
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository
from app.repositories.ladder_repository import LadderRepository
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.run_scheduler import RunScheduler
from app.services.var.var_run_service import VarRunService
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
