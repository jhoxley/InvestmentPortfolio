"""API router for the account performance and performance attribute metadata endpoints."""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import (
    get_capital_repository,
    get_ladder_rebuild_service,
    get_ladder_repository,
    get_rebuild_lock_registry,
)
from app.models.performance import PerformanceAttributeMetadataResponse
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services import performance_attributes
from app.services.accounts_service import AccountsService
from app.services.performance_service import PerformanceService
from app.services.rebuild.ladder_rebuild_service import LadderRebuildService
from app.services.rebuild.rebuild_lock_registry import RebuildLockRegistry
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.validators.account_name import validate_account_name

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["Performance"])


def _get_performance_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
    ladder_rebuild_service: LadderRebuildService = Depends(get_ladder_rebuild_service),
    rebuild_lock_registry: RebuildLockRegistry = Depends(get_rebuild_lock_registry),
) -> PerformanceService:
    """Dependency that returns a wired PerformanceService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).
        ladder_rebuild_service: LadderRebuildService instance (injected by FastAPI).
        rebuild_lock_registry: Shared RebuildLockRegistry (injected by FastAPI).

    Returns:
        PerformanceService instance.
    """
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return PerformanceService(
        ladder_repo=ladder_repo,
        accounts_service=accounts_service,
        date_resolver=TimeseriesDateResolver(),
        ladder_rebuild_service=ladder_rebuild_service,
        rebuild_lock_registry=rebuild_lock_registry,
    )


@router.get(
    "/accounts/{account_name}/performance",
    summary=(
        "Retrieve a per-business-day time series of requested performance measures for an account"
    ),
    description=(
        "If the resolved end date is later than the ladder's last ingested-or-rebuilt "
        "date, this request synchronously rebuilds the missing period before "
        "responding, capped at the prior business day relative to today (014). The "
        "rebuild is persisted and shared with the timeseries, position, and "
        "return-histogram endpoints."
    ),
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        422: {
            "description": (
                "Validation failed — invalid account name, no attribute supplied, an "
                "unsupported attribute name, an invalid date range, a future end date, or "
                "the account has no ingested position ladder"
            )
        },
    },
)
async def get_account_performance(
    account_name: str,
    attribute: list[str] = Query(
        default_factory=list, description="Repeated; at least one required"
    ),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    service: PerformanceService = Depends(_get_performance_service),
) -> JSONResponse:
    """Return a performance time series for the requested account/measures.

    Args:
        account_name: Path parameter identifying the account.
        attribute: Repeated query parameter naming the requested measures.
        start: Optional start date (defaults per FR-004).
        end: Optional end date (defaults per FR-004).
        service: Injected PerformanceService.

    Returns:
        200 with PerformanceResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        NoAttributesRequestedError: No attribute supplied.
        UnsupportedAttributeError: An attribute name isn't supported.
        AccountNotFoundError: No resource of any kind ingested for this account.
        MissingRequiredSourceError: The account has no ingested position ladder.
        FutureEndDateError: end is later than today.
        InvalidDateRangeError: Resolved start is after resolved end.
    """
    validate_account_name(account_name)
    response = service.get_performance(
        account_name=account_name,
        attributes=attribute,
        start=start,
        end=end,
        today=date.today(),
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/performance/attributes",
    summary="Describe the measures that can be requested from the performance endpoint",
)
async def get_performance_attribute_metadata() -> JSONResponse:
    """Return the full set of supported performance measures.

    Returns:
        200 with PerformanceAttributeMetadataResponse JSON body.
    """
    response = PerformanceAttributeMetadataResponse(
        attributes=performance_attributes.ATTRIBUTE_DEFINITIONS,
        _links={"self": "/v1/performance/attributes"},
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )
