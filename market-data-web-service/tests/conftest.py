from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers import PricingProvider
from app.providers.identifier_provider import IdentifierProvider


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
def mock_fx_provider() -> MagicMock:
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
    from app.services.gap_fill import GapFillService
    from app.services.pricing_service import PricingService

    def override_settings() -> Settings:
        return Settings(cache=CacheSettings(directory=tmp_cache_dir))

    def override_service() -> PricingService:
        repo = CacheRepository(tmp_cache_dir)
        provider = CachedPricingProvider(mock_inner_provider, repo)
        return PricingService(provider=provider, gap_fill=GapFillService())

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_pricing_service] = override_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_fx(
    tmp_cache_dir: Path,
    mock_inner_provider: MagicMock,
    mock_fx_provider: MagicMock,
) -> Generator[TestClient, None, None]:
    from app.api.fx import get_fx_provider
    from app.api.securities import get_currency_service, get_pricing_service
    from app.cache.repository import CacheRepository
    from app.config import CacheSettings, Settings, get_settings
    from app.providers.cached_provider import CachedPricingProvider
    from app.services.currency_service import CurrencyService
    from app.services.fx_aligner import FxAligner
    from app.services.gap_fill import GapFillService
    from app.services.pricing_service import PricingService

    def override_settings() -> Settings:
        return Settings(cache=CacheSettings(directory=tmp_cache_dir))

    def override_service() -> PricingService:
        repo = CacheRepository(tmp_cache_dir)
        provider = CachedPricingProvider(mock_inner_provider, repo)
        return PricingService(provider=provider, gap_fill=GapFillService())

    def override_currency_service() -> CurrencyService:
        repo = CacheRepository(tmp_cache_dir)
        fx_prov = CachedPricingProvider(mock_fx_provider, repo)
        return CurrencyService(fx_provider=fx_prov, aligner=FxAligner(), gap_fill=GapFillService())

    def override_fx_provider() -> CachedPricingProvider:
        repo = CacheRepository(tmp_cache_dir)
        return CachedPricingProvider(mock_fx_provider, repo)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_pricing_service] = override_service
    app.dependency_overrides[get_currency_service] = override_currency_service
    app.dependency_overrides[get_fx_provider] = override_fx_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_gap_fill(
    tmp_cache_dir: Path,
    mock_inner_provider: MagicMock,
    mock_fx_provider: MagicMock,
) -> Generator[TestClient, None, None]:
    from app.api.fx import get_fx_provider
    from app.api.securities import get_currency_service, get_pricing_service
    from app.cache.repository import CacheRepository
    from app.config import CacheSettings, Settings, get_settings
    from app.providers.cached_provider import CachedPricingProvider
    from app.services.currency_service import CurrencyService
    from app.services.fx_aligner import FxAligner
    from app.services.gap_fill import GapFillService
    from app.services.pricing_service import PricingService

    def override_settings() -> Settings:
        return Settings(cache=CacheSettings(directory=tmp_cache_dir))

    def override_service() -> PricingService:
        repo = CacheRepository(tmp_cache_dir)
        provider = CachedPricingProvider(mock_inner_provider, repo)
        return PricingService(provider=provider, gap_fill=GapFillService())

    def override_currency_service() -> CurrencyService:
        repo = CacheRepository(tmp_cache_dir)
        fx_prov = CachedPricingProvider(mock_fx_provider, repo)
        return CurrencyService(fx_provider=fx_prov, aligner=FxAligner(), gap_fill=GapFillService())

    def override_fx_provider() -> CachedPricingProvider:
        repo = CacheRepository(tmp_cache_dir)
        return CachedPricingProvider(mock_fx_provider, repo)

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_pricing_service] = override_service
    app.dependency_overrides[get_currency_service] = override_currency_service
    app.dependency_overrides[get_fx_provider] = override_fx_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_identifier_provider() -> MagicMock:
    return MagicMock(spec=IdentifierProvider)


@pytest.fixture()
def client_with_identifiers(
    mock_identifier_provider: MagicMock,
) -> Generator[TestClient, None, None]:
    from app.api.identifiers import get_identifier_service
    from app.services.identifier_service import IdentifierService

    def override_service() -> IdentifierService:
        return IdentifierService(provider=mock_identifier_provider)

    app.dependency_overrides[get_identifier_service] = override_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_fallback_inner_provider() -> MagicMock:
    from app.exceptions import DataNotFoundError

    mock = MagicMock(spec=PricingProvider)
    mock.get_price_history.side_effect = DataNotFoundError("PRIV01")
    mock.get_current_price.side_effect = DataNotFoundError("PRIV01")
    return mock


@pytest.fixture()
def mock_fallback_id_provider() -> MagicMock:
    from app.exceptions import IdentifierNotFoundError

    mock = MagicMock(spec=IdentifierProvider)
    mock.lookup_ticker.side_effect = IdentifierNotFoundError("GB00B0PRVT01")
    return mock


@pytest.fixture()
def client_with_fallback(
    mock_fallback_inner_provider: MagicMock,
    mock_fallback_id_provider: MagicMock,
) -> Generator[TestClient, None, None]:
    from pathlib import Path as _Path

    from app.api.identifiers import get_identifier_service
    from app.api.securities import get_pricing_service
    from app.providers.fallback_provider import FallbackPricingProvider
    from app.providers.identifier_provider import FallbackIdentifierProvider
    from app.repositories.fallback_config import FallbackConfigRepository
    from app.services.gap_fill import GapFillService
    from app.services.identifier_service import IdentifierService
    from app.services.pricing_service import PricingService

    pricing_repo = FallbackConfigRepository(_Path("tests/fixtures/fallback_config.json"))
    isin_repo = FallbackConfigRepository(_Path("tests/fixtures/fallback_config_isin.json"))

    def override_pricing() -> PricingService:
        provider = FallbackPricingProvider(
            inner=mock_fallback_inner_provider, fallback_repo=pricing_repo
        )
        return PricingService(provider=provider, gap_fill=GapFillService())

    def override_identifier() -> IdentifierService:
        provider = FallbackIdentifierProvider(
            inner=mock_fallback_id_provider, fallback_repo=isin_repo
        )
        return IdentifierService(provider=provider)

    app.dependency_overrides[get_pricing_service] = override_pricing
    app.dependency_overrides[get_identifier_service] = override_identifier
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
