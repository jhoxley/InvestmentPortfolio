"""API router for the position time series, positions, and attribute metadata endpoints."""

from datetime import date

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_capital_repository, get_ladder_repository
from app.exceptions import AccountNotFoundError, PositionLadderNotIngestedError
from app.models.position_timeseries import PositionsResponse, PositionTimeSeriesResponse
from app.models.timeseries import AccountSummary, AttributeMetadataResponse
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services import position_attributes
from app.services.accounts_service import AccountsService
from app.services.position_timeseries_service import PositionTimeSeriesService
from app.services.positions_service import PositionsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.validators.account_name import validate_account_name

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["Position Timeseries"])


def _validate_ladder_ingested(summary: AccountSummary, account_name: str) -> None:
    """Validate that the account is known and has an ingested position ladder.

    Args:
        summary: The account's resource summary.
        account_name: The account identifier (for error messages).

    Raises:
        AccountNotFoundError: If no resource of any kind is ingested for the account.
        PositionLadderNotIngestedError: If the account is known but has no ladder.
    """
    if summary.capital_ledger is None and summary.position_ladder is None:
        raise AccountNotFoundError(
            account_name=account_name,
            message=(
                f"No capital ledger or position ladder has been ingested for "
                f"account '{account_name}'."
            ),
        )
    if summary.position_ladder is None:
        raise PositionLadderNotIngestedError(account_name=account_name)


def _get_positions_endpoint_deps(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
) -> tuple[LadderRepository, AccountsService]:
    """Dependency that returns the ladder repository and a wired AccountsService.

    Lighter-weight than `_get_position_timeseries_service` — the positions-enumeration
    endpoint needs no `PositionTimeSeriesService`/`TimeseriesDateResolver`/attributes at all.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).

    Returns:
        Tuple of (LadderRepository, AccountsService).
    """
    return ladder_repo, AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)


def _get_position_timeseries_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
) -> PositionTimeSeriesService:
    """Dependency that returns a wired PositionTimeSeriesService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).

    Returns:
        PositionTimeSeriesService instance.
    """
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return PositionTimeSeriesService(
        ladder_repo=ladder_repo,
        accounts_service=accounts_service,
        positions_service=PositionsService(),
        date_resolver=TimeseriesDateResolver(),
    )


@router.get(
    "/accounts/{account_name}/position",
    summary=(
        "Retrieve a per-business-day time series of requested attributes for one or more positions"
    ),
    response_model=PositionTimeSeriesResponse,
    responses={
        404: {"description": "No resource of any kind has been ingested for this account"},
        422: {
            "description": (
                "Validation failed — invalid account name, account known but no position "
                "ladder ingested, no attribute supplied, an unsupported attribute name "
                "(including 'capital'), an invalid date range, a future end date, or a "
                "resolved start date before the position ladder's earliest recorded date"
            )
        },
    },
)
async def get_position_timeseries(
    account_name: str,
    position: list[str] = Query(
        default_factory=list,
        description="Repeated; zero or more. Unmatched values are silently dropped",
    ),
    attribute: list[str] = Query(
        default_factory=list, description="Repeated; at least one required"
    ),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    service: PositionTimeSeriesService = Depends(_get_position_timeseries_service),
) -> JSONResponse:
    """Return a per-position, forward-filled time series for the requested account.

    Args:
        account_name: Path parameter identifying the account.
        position: Repeated query parameter naming the requested positions.
        attribute: Repeated query parameter naming the requested attributes.
        start: Optional start date (defaults per FR-009).
        end: Optional end date (defaults per FR-009).
        service: Injected PositionTimeSeriesService.

    Returns:
        200 with PositionTimeSeriesResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        NoAttributesRequestedError: No attribute supplied.
        UnsupportedAttributeError: An attribute name isn't supported.
        AccountNotFoundError: No resource of any kind ingested for this account.
        PositionLadderNotIngestedError: Account known but has no ingested position ladder.
        MissingRequiredSourceError: Resolved start precedes the ladder's own earliest date.
        FutureEndDateError: end is later than today.
        InvalidDateRangeError: Resolved start is after resolved end.
    """
    validate_account_name(account_name)
    response = service.get_series(
        account_name=account_name,
        positions=position,
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
    "/accounts/{account_name}/positions",
    summary="Enumerate every position recorded in an account's position ladder",
    response_model=PositionsResponse,
    responses={
        404: {"description": "No resource of any kind has been ingested for this account"},
        422: {"description": "Account is known but has no ingested position ladder"},
    },
)
async def list_account_positions(
    account_name: str,
    deps: tuple[LadderRepository, AccountsService] = Depends(_get_positions_endpoint_deps),
) -> JSONResponse:
    """Return every distinct position recorded for an account, with first/last dates.

    Args:
        account_name: Path parameter identifying the account.
        deps: Injected (LadderRepository, AccountsService) tuple.

    Returns:
        200 with PositionsResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        AccountNotFoundError: No resource of any kind ingested for this account.
        PositionLadderNotIngestedError: Account known but has no ingested position ladder.
    """
    validate_account_name(account_name)
    ladder_repo, accounts_service = deps
    summary = accounts_service.get_summary(account_name)
    _validate_ladder_ingested(summary, account_name)

    ladder_df = ladder_repo.read_full_df(account_name)
    ladder_df = ladder_df.assign(date=pd.to_datetime(ladder_df["date"]).dt.date)
    response = PositionsResponse(
        account_name=account_name,
        positions=PositionsService().list_positions(ladder_df),
        _links={"self": f"/v1/accounts/{account_name}/positions"},
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/positions/attributes",
    summary="Describe the attributes that can be requested from the position time series endpoint",
    response_model=AttributeMetadataResponse,
)
async def get_position_attribute_metadata() -> JSONResponse:
    """Return the full set of supported position time series attributes.

    Returns:
        200 with AttributeMetadataResponse JSON body.
    """
    response = AttributeMetadataResponse(
        attributes=position_attributes.ATTRIBUTE_DEFINITIONS,
        _links={"self": "/v1/positions/attributes"},
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )
