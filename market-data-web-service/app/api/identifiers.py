from fastapi import APIRouter, Depends, Path, Query

from app.config import Settings, get_settings
from app.models.pricing import TickerResolutionResponse
from app.providers.identifier_provider import (
    FallbackIdentifierProvider,
    YFinanceIdentifierProvider,
)
from app.repositories.fallback_config import FallbackConfigRepository
from app.services.identifier_service import IdentifierService

router = APIRouter(prefix="/identifiers", tags=["Identifiers"])


def get_identifier_service(
    settings: Settings = Depends(get_settings),
) -> IdentifierService:
    fallback_repo = FallbackConfigRepository(settings.fallback.config_path)
    provider = FallbackIdentifierProvider(
        inner=YFinanceIdentifierProvider(), fallback_repo=fallback_repo
    )
    return IdentifierService(provider=provider)


@router.get("/{identifier}", response_model=TickerResolutionResponse)
async def resolve_identifier(
    identifier: str = Path(..., min_length=1),
    identifier_type_hint: str | None = Query(default=None, alias="type"),
    service: IdentifierService = Depends(get_identifier_service),
) -> TickerResolutionResponse:
    return service.resolve(identifier, identifier_type_hint)
