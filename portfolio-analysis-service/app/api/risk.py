"""API router for the risk endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import (
    get_capital_repository,
    get_ladder_rebuild_service,
    get_ladder_repository,
    get_rebuild_lock_registry,
)
from app.models.risk import ReturnHistogramResponse
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services.accounts_service import AccountsService
from app.services.daily_return_series_loader import DailyReturnSeriesLoader
from app.services.rebuild.ladder_rebuild_service import LadderRebuildService
from app.services.rebuild.rebuild_lock_registry import RebuildLockRegistry
from app.services.risk_service import RiskService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.validators.account_name import validate_account_name

router = APIRouter(prefix="/v1", tags=["Risk"])


def _get_risk_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
    ladder_rebuild_service: LadderRebuildService = Depends(get_ladder_rebuild_service),
    rebuild_lock_registry: RebuildLockRegistry = Depends(get_rebuild_lock_registry),
) -> RiskService:
    """Dependency that returns a wired RiskService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).
        ladder_rebuild_service: LadderRebuildService instance (injected by FastAPI).
        rebuild_lock_registry: Shared RebuildLockRegistry (injected by FastAPI).

    Returns:
        RiskService instance.
    """
    loader = DailyReturnSeriesLoader(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        date_resolver=TimeseriesDateResolver(),
        ladder_rebuild_service=ladder_rebuild_service,
        rebuild_lock_registry=rebuild_lock_registry,
    )
    return RiskService(loader=loader)


@router.get(
    "/accounts/{account_name}/risk/return-histogram",
    response_model=ReturnHistogramResponse,
    summary=(
        "Retrieve a histogram and statistics of an account's portfolio-level daily returns "
        "in basis points"
    ),
    description=(
        "If the resolved end date is later than the ladder's last ingested-or-rebuilt "
        "date, this request synchronously rebuilds the missing period before "
        "responding, capped at the prior business day relative to today (014). The "
        "rebuild is persisted and shared with the timeseries, position, and "
        "performance endpoints."
    ),
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        422: {
            "description": (
                "Validation failed — invalid account name, no ingested position ladder (or a "
                "start date before it begins), an invalid date range, or a future end date"
            )
        },
    },
)
async def get_account_return_histogram(
    account_name: str,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    service: RiskService = Depends(_get_risk_service),
) -> JSONResponse:
    """Return the daily return histogram for the requested account and window.

    Args:
        account_name: Path parameter identifying the account.
        start: Optional start date (defaults as for the performance endpoints).
        end: Optional end date (defaults as for the performance endpoints).
        service: Injected RiskService.

    Returns:
        200 with ReturnHistogramResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        AccountNotFoundError: No resource of any kind ingested for this account.
        MissingRequiredSourceError: The account has no ingested position ladder.
        FutureEndDateError: end is later than today.
        InvalidDateRangeError: Resolved start is after resolved end.
    """
    validate_account_name(account_name)
    response = service.get_return_histogram(
        account_name=account_name, start=start, end=end, today=date.today()
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )
