from fastapi import APIRouter, Depends, Path, Query

from app.models.pricing import TickerResolutionResponse
from app.providers.identifier_provider import IdentifierProvider, YFinanceIdentifierProvider
from app.services.identifier_service import IdentifierService

router = APIRouter(prefix="/identifiers", tags=["Identifiers"])


def get_identifier_provider() -> YFinanceIdentifierProvider:
    return YFinanceIdentifierProvider()


def get_identifier_service(
    provider: IdentifierProvider = Depends(get_identifier_provider),
) -> IdentifierService:
    return IdentifierService(provider=provider)


@router.get("/{identifier}", response_model=TickerResolutionResponse)
async def resolve_identifier(
    identifier: str = Path(..., min_length=1),
    identifier_type_hint: str | None = Query(default=None, alias="type"),
    service: IdentifierService = Depends(get_identifier_service),
) -> TickerResolutionResponse:
    return service.resolve(identifier, identifier_type_hint)
