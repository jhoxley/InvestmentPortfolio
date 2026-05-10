from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers import PricingProvider


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def mock_provider() -> MagicMock:
    mock = MagicMock(spec=PricingProvider)
    return mock


@pytest.fixture()
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d


@pytest.fixture()
def mock_inner_provider() -> MagicMock:
    return MagicMock(spec=PricingProvider)


@pytest.fixture()
def client_with_cache(
    tmp_cache_dir: Path,
    mock_inner_provider: MagicMock,
) -> Generator[TestClient, None, None]:
    from app.api.securities import get_pricing_service
    from app.cache.repository import CacheRepository
    from app.config import CacheSettings, Settings, get_settings
    from app.providers.cached_provider import CachedPricingProvider
    from app.services.pricing_service import PricingService

    def override_settings() -> Settings:
        return Settings(cache=CacheSettings(directory=tmp_cache_dir))

    def override_service() -> PricingService:
        repo = CacheRepository(tmp_cache_dir)
        provider = CachedPricingProvider(mock_inner_provider, repo)
        return PricingService(provider=provider)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_pricing_service] = override_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
