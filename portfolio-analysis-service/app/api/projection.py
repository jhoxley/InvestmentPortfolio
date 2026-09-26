"""API router for the account projection endpoint."""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_capital_repository, get_ladder_repository
from app.models.periodicity import SUPPORTED_PERIODICITY_VALUES
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services.accounts_service import AccountsService
from app.services.projection_service import ProjectionService
from app.validators.account_name import validate_account_name
from app.validators.periodicity import resolve_periodicity

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["Projection"])


def _get_projection_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
) -> ProjectionService:
    """Dependency that returns a wired ProjectionService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).

    Returns:
        ProjectionService instance.
    """
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return ProjectionService(ladder_repo=ladder_repo, accounts_service=accounts_service)


@router.get(
    "/accounts/{account_name}/projection",
    summary=(
        "Retrieve an account's historical market value plus one projected series per "
        "requested return, from a start date out to a projection target date"
    ),
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        422: {
            "description": (
                "Validation failed — invalid account name, account known but no position "
                "ladder ingested, an unsupported return name, an unsupported periodicity "
                "value, a projection_date not strictly later than the resolved start date, "
                "or a resolved start date before the position ladder's earliest recorded date"
            )
        },
    },
)
async def get_account_projection(
    account_name: str,
    projection_date: date = Query(...),
    return_: list[str] = Query(
        default_factory=list,
        alias="return",
        description=(
            "Repeated; zero or more of 'ITD (Ann.)', '1Y', '3Y', '5Y'. Zero returns still "
            "succeeds, returning the historical series alone."
        ),
    ),
    start: date | None = Query(
        default=None,
        description=(
            "Historical data ends and every projection begins here. Omitted defaults to the "
            "account's own most recently recorded position-ladder date."
        ),
    ),
    periodicity: str | None = Query(
        default=None,
        description=(
            "Optional aggregation interval: day, week, month, quarter, annual. Applied "
            "independently to the historical series and to each projected series. For a "
            "non-day interval each projected series contains window-start dates only: it "
            "opens at the first window start on or after start (start itself appears only "
            "when it is a window start) and ends at the last window start on or before "
            "projection_date."
        ),
        json_schema_extra={"enum": list(SUPPORTED_PERIODICITY_VALUES)},
    ),
    service: ProjectionService = Depends(_get_projection_service),
) -> JSONResponse:
    """Return the historical-plus-projected market-value series for the requested account.

    Args:
        account_name: Path parameter identifying the account.
        projection_date: The date to project forward to.
        return_: Repeated query parameter (wire name `return`) naming the requested returns.
        start: Optional start date (defaults per FR-002).
        periodicity: Optional calendar aggregation interval (defaults to day).
        service: Injected ProjectionService.

    Returns:
        200 with PositionTimeSeriesResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        UnsupportedAttributeError: A requested return name isn't supported.
        AccountNotFoundError: No resource of any kind ingested for this account.
        PositionLadderNotIngestedError: Account known but has no ingested position ladder.
        MissingRequiredSourceError: Resolved start precedes the ladder's own earliest date.
        InvalidProjectionRangeError: projection_date isn't strictly later than resolved start.
        UnsupportedPeriodicityError: The periodicity value isn't supported.
    """
    validate_account_name(account_name)
    resolved_periodicity = resolve_periodicity(periodicity)
    response = service.get_projection(
        account_name=account_name,
        projection_date=projection_date,
        returns=return_,
        start=start,
        periodicity=resolved_periodicity,
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )
