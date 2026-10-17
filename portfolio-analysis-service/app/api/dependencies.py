"""Shared FastAPI dependency providers used across multiple API routers."""

from fastapi import Depends

from app.clients.market_data_client import HttpMarketDataClient, ObservedPriceClient
from app.config import Settings, get_settings
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository
from app.repositories.var_repository import VarRepository
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
