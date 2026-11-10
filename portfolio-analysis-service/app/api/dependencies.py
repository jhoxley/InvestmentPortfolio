"""Shared FastAPI dependency providers used across multiple API routers."""

from fastapi import Depends

from app.clients.market_data_client import (
    HttpMarketDataClient,
    MarketDataClient,
    ObservedPriceClient,
)
from app.config import Settings, get_settings
from app.repositories.capital_repository import CapitalRepository
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository
from app.repositories.ladder_repository import LadderRepository
from app.repositories.var_repository import VarRepository
from app.services.pricing_enrichment_service import PricingEnrichmentService
from app.services.rebuild.capital_rebuild_service import CapitalRebuildService
from app.services.rebuild.ladder_rebuild_service import LadderRebuildService
from app.services.rebuild.rebuild_lock_registry import (
    RebuildLockRegistry,
    get_default_rebuild_lock_registry,
)
from app.services.returns_enrichment_service import ReturnsEnrichmentService
from app.services.var.run_scheduler import RunScheduler, get_default_scheduler


def get_ladder_repository(settings: Settings = Depends(get_settings)) -> LadderRepository:
    """Dependency that returns a LadderRepository bound to the configured data directory.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        LadderRepository instance.
    """
    return LadderRepository(data_dir=settings.data.directory)


def get_capital_repository(settings: Settings = Depends(get_settings)) -> CapitalRepository:
    """Dependency that returns a CapitalRepository bound to the configured data directory.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        CapitalRepository instance.
    """
    return CapitalRepository(data_dir=settings.data.directory)


def get_var_repository(settings: Settings = Depends(get_settings)) -> VarRepository:
    """Dependency that returns a VarRepository bound to the configured data directory.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        VarRepository instance.
    """
    return VarRepository(data_dir=settings.data.directory)


def get_run_scheduler() -> RunScheduler:
    """Dependency that returns the process-wide VaR run scheduler.

    Returns:
        The shared RunScheduler singleton, so every request serialises against the same
        single-worker queue.
    """
    return get_default_scheduler()


def get_identifier_mapping_repository(
    settings: Settings = Depends(get_settings),
) -> IdentifierMappingRepository:
    """Dependency that returns an IdentifierMappingRepository bound to the configured path.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        IdentifierMappingRepository instance.
    """
    return IdentifierMappingRepository(mapping_path=settings.identifier_mapping.path)


def get_market_data_client(settings: Settings = Depends(get_settings)) -> MarketDataClient:
    """Dependency that returns a MarketDataClient bound to the configured service location.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        MarketDataClient instance.
    """
    return HttpMarketDataClient(
        base_url=settings.market_data_service.base_url,
        timeout_seconds=settings.market_data_service.timeout_seconds,
    )


def get_rebuild_lock_registry() -> RebuildLockRegistry:
    """Dependency that returns the process-wide rebuild lock registry (014).

    Returns:
        The shared RebuildLockRegistry singleton, so every request serialises against
        the same per-(account, resource) locks.
    """
    return get_default_rebuild_lock_registry()


def get_ladder_rebuild_service(
    ladder_repo: LadderRepository = Depends(get_ladder_repository),
    mapping_repo: IdentifierMappingRepository = Depends(get_identifier_mapping_repository),
    market_data_client: MarketDataClient = Depends(get_market_data_client),
) -> LadderRebuildService:
    """Dependency that returns a wired LadderRebuildService (014).

    Args:
        ladder_repo: LadderRepository instance (injected by FastAPI).
        mapping_repo: IdentifierMappingRepository instance (injected by FastAPI).
        market_data_client: MarketDataClient instance (injected by FastAPI).

    Returns:
        LadderRebuildService instance.
    """
    return LadderRebuildService(
        repository=ladder_repo,
        mapping_repo=mapping_repo,
        market_data_client=market_data_client,
        enrichment_service=PricingEnrichmentService(
            mapping_repo=mapping_repo, market_data_client=market_data_client
        ),
        returns_service=ReturnsEnrichmentService(),
    )


def get_capital_rebuild_service(
    capital_repo: CapitalRepository = Depends(get_capital_repository),
) -> CapitalRebuildService:
    """Dependency that returns a wired CapitalRebuildService (014).

    Args:
        capital_repo: CapitalRepository instance (injected by FastAPI).

    Returns:
        CapitalRebuildService instance.
    """
    return CapitalRebuildService(capital_repo)


def get_observed_price_client(settings: Settings = Depends(get_settings)) -> ObservedPriceClient:
    """Dependency that returns an ObservedPriceClient bound to the configured service location.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        ObservedPriceClient instance (an HttpMarketDataClient, which implements both the
        MarketDataClient and ObservedPriceClient protocols).
    """
    return HttpMarketDataClient(
        base_url=settings.market_data_service.base_url,
        timeout_seconds=settings.market_data_service.timeout_seconds,
    )
