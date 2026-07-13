"""Shared FastAPI dependency providers used across multiple API routers."""

from fastapi import Depends

from app.config import Settings, get_settings
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import LadderRepository


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
