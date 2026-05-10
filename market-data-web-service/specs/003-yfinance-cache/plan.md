# Implementation Plan: YFinance Price Data Cache

**Branch**: `003-yfinance-cache` | **Date**: 2026-05-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-yfinance-cache/spec.md`

## Summary

Introduce a local CSV-file cache in front of the YFinance API for historical price requests. The cache directory is configured via a new `config.yaml` file at the project root. On each `GET /securities/{ticker}/history` call, the service reads the cached file for the ticker (if any), determines the covered date range from the actual trading-day data present, identifies any uncovered segments in the request, fetches only those from YFinance, merges them into the cache, and returns the complete result. If YFinance fails during a missing-segment fetch, the entire request fails and the cache is left unchanged. Two new DELETE endpoints (`/cache/{ticker}` and `/cache`) allow targeted or full cache invalidation. Implementation follows the Open/Closed decorator pattern: a `CachedPricingProvider` wraps the existing `YFinanceProvider` without modifying it.

## Technical Context

**Language/Version**: Python 3.11+ (venv running 3.14.4)
**Primary Dependencies**: FastAPI 0.115.x, yfinance 0.2.x, pydantic >=2.0, structlog >=24.0, pyyaml >=6.0 (new — already in venv, not yet in pyproject.toml)
**Storage**: Local filesystem — one CSV file per ticker in a configurable cache directory
**Testing**: pytest-bdd 8.x (Gherkin BDD), pytest, httpx TestClient
**Target Platform**: Local machine — Windows; `localhost:8000`
**Project Type**: web-service (existing)
**Performance Goals**: Cache hit path adds <10ms overhead to `GET /securities/{ticker}/history`; YFinance fetch overhead unchanged
**Constraints**: No distributed locking (single-user, last-write-wins); no TTL-based expiry; cache deletion is manual via API
**Scale/Scope**: Single user, personal portfolio tool; tens of tickers at most

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Notes |
|-----------|-------|-------|
| I. SOLID Design | ✅ | `CacheRepository` (I/O), `CachedPricingProvider` (orchestration), `app/api/cache.py` (HTTP) have single responsibilities; all dependencies injected |
| II. Standard Dependencies | ✅ | `csv` and `datetime` are stdlib; `pyyaml` added to `pyproject.toml`; no bespoke utilities duplicating std-library functionality |
| III. BDD Test-First | ✅ | Four `.feature` files authored and confirmed failing before any implementation task begins |
| IV. Code Quality Standards | ✅ | Existing `ruff` + `mypy --strict` config covers all new modules; no per-file overrides |
| V. Observability & Logging | ✅ | Cache hit/miss/merge/write/delete events logged via structlog at INFO level; YFinance errors logged at ERROR |
| VI. OpenAPI-First | ✅ | `openapi.yaml` updated with `DELETE /cache` and `DELETE /cache/{ticker}` contracts before any endpoint implementation |

All six principles pass. No violations to document.

## Project Structure

### Documentation (this feature)

```text
specs/003-yfinance-cache/
├── plan.md                          # This file
├── research.md                      # Phase 0 output — decision log
├── data-model.md                    # Phase 1 output — entities and cache algorithm
├── contracts/
│   └── openapi-additions.yaml       # Phase 1 output — new DELETE endpoint contracts
└── tasks.md                         # Phase 2 output (/speckit-tasks command)
```

### Source Code (files added or modified by this feature)

```text
market-data-web-service/
├── config.yaml                               # NEW: cache.directory configuration
├── pyproject.toml                            # MODIFIED: add pyyaml dependency
├── openapi.yaml                              # MODIFIED: add DELETE /cache and /cache/{ticker}
├── app/
│   ├── config.py                             # NEW: Settings, load_settings(), get_settings()
│   ├── cache/
│   │   ├── __init__.py                       # NEW
│   │   └── repository.py                     # NEW: CacheRepository (CSV read/write/delete)
│   ├── providers/
│   │   ├── __init__.py                       # EXISTING: PricingProvider ABC (unchanged)
│   │   ├── yfinance_provider.py              # EXISTING (unchanged)
│   │   └── cached_provider.py                # NEW: CachedPricingProvider decorator
│   ├── models/
│   │   └── pricing.py                        # MODIFIED: add CacheDeleteResponse, CacheClearResponse
│   ├── api/
│   │   ├── securities.py                     # MODIFIED: inject CachedPricingProvider
│   │   └── cache.py                          # NEW: DELETE /cache, DELETE /cache/{ticker}
│   └── main.py                               # MODIFIED: include cache router; startup config
└── tests/
    ├── features/
    │   ├── cache_full_hit.feature             # NEW: User Story 1 BDD scenarios
    │   ├── cache_partial_hit.feature          # NEW: User Story 2 BDD scenarios
    │   ├── cache_miss.feature                 # NEW: User Story 3 BDD scenario
    │   └── cache_management.feature           # NEW: User Stories 4 + 5 BDD scenarios
    └── steps/
        ├── cache_full_hit_steps.py            # NEW
        ├── cache_partial_hit_steps.py         # NEW
        ├── cache_miss_steps.py                # NEW
        └── cache_management_steps.py          # NEW
```

## Complexity Tracking

> No violations — all constitution checks pass.

---

## Phase 0: Research Summary

See [research.md](research.md) for full decision log.

| Topic | Decision |
|-------|----------|
| Cache file format | CSV (Python stdlib `csv` module); one file per ticker: `{ticker}.csv` |
| Config format | YAML (`config.yaml` at project root); parsed by PyYAML |
| Architecture pattern | Decorator: `CachedPricingProvider` wraps `PricingProvider`; `CacheRepository` handles all I/O |
| Coverage algorithm | Compare request range against actual min/max dates in cached data (FR-013) |
| YFinance failure | Propagate `ProviderUnavailableError` for entire request; cache left unchanged (FR-012) |
| New deps | `pyyaml>=6.0` (production); no other additions |

---

## Phase 1: Design Artifacts

- [data-model.md](data-model.md) — CacheEntry, PriceRecord, Settings, CacheDeleteResponse, CacheClearResponse entities; coverage algorithm
- [contracts/openapi-additions.yaml](contracts/openapi-additions.yaml) — DELETE /cache and DELETE /cache/{ticker} endpoint contracts; new response schemas

---

## Implementation Notes

### New: app/config.py

```python
from pathlib import Path
from pydantic import BaseModel
import yaml

class CacheSettings(BaseModel):
    directory: Path = Path("./cache")

class Settings(BaseModel):
    cache: CacheSettings = CacheSettings()

def load_settings(config_path: Path = Path("config.yaml")) -> Settings:
    if config_path.exists():
        with config_path.open() as f:
            data = yaml.safe_load(f) or {}
        return Settings.model_validate(data)
    return Settings()

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
```

### New: app/cache/repository.py

```python
class CacheRepository:
    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir

    def read(self, ticker: str) -> list[tuple[date, float]] | None:
        """Return sorted (date, close) rows or None if no file / unreadable."""

    def write(self, ticker: str, records: list[tuple[date, float]]) -> None:
        """Atomically write sorted records to {ticker}.csv."""

    def delete(self, ticker: str) -> bool:
        """Remove {ticker}.csv. Returns True if deleted, False if not found."""

    def delete_all(self) -> int:
        """Remove all *.csv files. Returns count deleted."""

    def _filename(self, ticker: str) -> Path:
        safe = re.sub(r'[\\/:*?"<>|^]', "_", ticker)
        return self._dir / f"{safe}.csv"
```

Atomic write strategy: write to `{ticker}.csv.tmp`, then `os.replace()` to `{ticker}.csv`. This prevents partially-written files from being read as valid cache entries.

### New: app/providers/cached_provider.py

```python
class CachedPricingProvider(PricingProvider):
    def __init__(self, inner: PricingProvider, repo: CacheRepository) -> None:
        self._inner = inner
        self._repo = repo

    def get_current_price(self, ticker: str) -> dict[str, object]:
        return self._inner.get_current_price(ticker)  # pass-through; no caching

    def get_price_history(self, ticker: str, from_date: date, to_date: date) -> list[tuple[date, float]]:
        cached = self._repo.read(ticker)
        if cached is None:
            # Cache miss: fetch full range, write cache, return
            ...
        # Determine coverage and missing segments
        # Fetch missing, merge, write, return filtered result
```

### Modified: app/api/securities.py

`get_pricing_service()` updated to inject `CachedPricingProvider`:

```python
def get_pricing_service(settings: Settings = Depends(get_settings)) -> PricingService:
    repo = CacheRepository(settings.cache.directory)
    provider = CachedPricingProvider(YFinanceProvider(), repo)
    return PricingService(provider=provider)
```

### New: app/api/cache.py

```python
router = APIRouter(prefix="/cache", tags=["Cache Management"])

@router.delete("/{ticker}", response_model=CacheDeleteResponse)
async def delete_ticker_cache(ticker: str = Path(...), settings: Settings = Depends(get_settings)) -> CacheDeleteResponse:
    repo = CacheRepository(settings.cache.directory)
    deleted = repo.delete(ticker)
    return CacheDeleteResponse(ticker=ticker, deleted=deleted)

@router.delete("", response_model=CacheClearResponse)
async def clear_all_cache(settings: Settings = Depends(get_settings)) -> CacheClearResponse:
    repo = CacheRepository(settings.cache.directory)
    count = repo.delete_all()
    return CacheClearResponse(deleted_count=count)
```

### BDD Test Strategy

Each `.feature` file uses a temporary cache directory fixture (via `tmp_path`) injected into the app through a `TestClient` override of `get_settings`. The `mock_provider` fixture from `conftest.py` is extended to control YFinance responses in cache scenarios.

**conftest.py additions**:
```python
@pytest.fixture()
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d

@pytest.fixture()
def client_with_cache(tmp_cache_dir: Path) -> Generator[TestClient, None, None]:
    settings = Settings(cache=CacheSettings(directory=tmp_cache_dir))
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### Logging Events (Observability)

All events logged via `structlog.get_logger(__name__)` at appropriate severity:

| Event | Level | Fields |
|-------|-------|--------|
| Cache hit (full) | INFO | `ticker`, `from_date`, `to_date`, `cached_records` |
| Cache hit (partial) | INFO | `ticker`, `segments_fetched`, `records_added` |
| Cache miss | INFO | `ticker`, `from_date`, `to_date` |
| Cache write | INFO | `ticker`, `total_records` |
| Cache delete (single) | INFO | `ticker`, `deleted` |
| Cache delete (all) | INFO | `deleted_count` |
| YFinance error in cache path | ERROR | `ticker`, `segment`, `error` |
| Cache file unreadable | WARNING | `ticker`, `path`, `error` |
| Cache directory created | INFO | `path` |
