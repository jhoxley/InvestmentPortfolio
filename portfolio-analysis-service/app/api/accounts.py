"""API router for the accounts-enumeration endpoint."""

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_capital_repository, get_ladder_repository
from app.models.timeseries import AccountsResponse
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.services.accounts_service import AccountsService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["Accounts"])


def _get_accounts_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    capital_repo: CapitalRepository = Depends(get_capital_repository),
) -> AccountsService:
    """Dependency that returns a wired AccountsService.

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        capital_repo: CapitalRepository instance (injected by FastAPI).

    Returns:
        AccountsService instance.
    """
    return AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)


@router.get(
    "/accounts",
    summary="Enumerate every account with at least one ingested resource",
    response_model=AccountsResponse,
)
async def list_accounts(
    service: AccountsService = Depends(_get_accounts_service),
) -> JSONResponse:
    """Return every known account with each ingested resource's date range.

    Args:
        service: Injected AccountsService.

    Returns:
        200 with AccountsResponse JSON body.
    """
    summaries = service.list_summaries()
    response = AccountsResponse(accounts=summaries, _links={"self": "/v1/accounts"})
    return JSONResponse(
        status_code=200,
        content=response.model_dump(by_alias=True, mode="json"),
    )
