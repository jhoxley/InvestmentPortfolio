"""API router for the account time series and attribute metadata endpoints."""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_capital_repository, get_ladder_repository
from app.models.periodicity import SUPPORTED_PERIODICITY_VALUES
from app.models.timeseries import AttributeMetadataResponse, TimeSeriesResponse
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services import timeseries_attributes
from app.services.accounts_service import AccountsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.services.timeseries_service import TimeSeriesService
from app.validators.account_name import validate_account_name
from app.validators.periodicity import resolve_periodicity

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["Timeseries"])


def _get_timeseries_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
) -> TimeSeriesService:
    """Dependency that returns a wired TimeSeriesService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).

    Returns:
        TimeSeriesService instance.
    """
    accounts_service = AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)
    return TimeSeriesService(
        ladder_repo=ladder_repo,
        capital_repo=capital_repo,
        accounts_service=accounts_service,
        date_resolver=TimeseriesDateResolver(),
    )


@router.get(
    "/accounts/{account_name}/timeseries",
    summary="Retrieve a per-business-day time series of requested attributes for an account",
    response_model=TimeSeriesResponse,
    responses={
        404: {"description": "No capital ledger or position ladder found for this account"},
        422: {
            "description": (
                "Validation failed — invalid account name, no attribute supplied, an "
                "unsupported attribute name, an unsupported periodicity value, an invalid "
                "date range, a future end date, or a required source missing/insufficient "
                "for a requested attribute"
            )
        },
    },
)
async def get_account_timeseries(
    account_name: str,
    attribute: list[str] = Query(
        default_factory=list, description="Repeated; at least one required"
    ),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    periodicity: str | None = Query(
        default=None,
        description=(
            "Optional aggregation interval: day, week, month, quarter, annual. Omitted or "
            "'day' returns one entry per business day. Any other value returns one entry "
            "per calendar-aligned window, valued at the last observation in that window."
        ),
        json_schema_extra={"enum": list(SUPPORTED_PERIODICITY_VALUES)},
    ),
    service: TimeSeriesService = Depends(_get_timeseries_service),
) -> JSONResponse:
    """Return a joined, forward-filled time series for the requested account/attributes.

    Args:
        account_name: Path parameter identifying the account.
        attribute: Repeated query parameter naming the requested attributes.
        start: Optional start date (defaults per FR-006).
        end: Optional end date (defaults per FR-007).
        periodicity: Optional calendar aggregation interval (defaults to day).
        service: Injected TimeSeriesService.

    Returns:
        200 with TimeSeriesResponse JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        NoAttributesRequestedError: No attribute supplied.
        UnsupportedAttributeError: An attribute name isn't supported.
        AccountNotFoundError: No resource of any kind ingested for this account.
        MissingRequiredSourceError: A required source is missing/insufficient.
        FutureEndDateError: end is later than today.
        InvalidDateRangeError: Resolved start is after resolved end.
        UnsupportedPeriodicityError: The periodicity value isn't supported.
    """
    validate_account_name(account_name)
    resolved_periodicity = resolve_periodicity(periodicity)
    response = service.get_series(
        account_name=account_name,
        attributes=attribute,
        start=start,
        end=end,
        today=date.today(),
        periodicity=resolved_periodicity,
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/timeseries/attributes",
    summary="Describe the attributes that can be requested from the time series endpoint",
    response_model=AttributeMetadataResponse,
)
async def get_timeseries_attribute_metadata() -> JSONResponse:
    """Return the full set of supported time series attributes.

    Returns:
        200 with AttributeMetadataResponse JSON body.
    """
    response = AttributeMetadataResponse(
        attributes=timeseries_attributes.ATTRIBUTE_DEFINITIONS,
        _links={"self": "/v1/timeseries/attributes"},
    )
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )
