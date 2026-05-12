# Implementation Plan: Identifier-to-Ticker Lookup

**Branch**: `005-identifier-to-ticker` | **Date**: 2026-05-12 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/005-identifier-to-ticker/spec.md`

## Summary

Build a new `GET /identifiers/{identifier}` endpoint that accepts a security identifier (ISIN, CUSIP, or SEDOL), auto-detects or validates its type from the structural format, and resolves it to a ticker symbol using yfinance's `Search` API. The response includes the ticker, security name, and exchange code (passed through from the data source as-is). Invalid formats return 422; unresolvable identifiers return 404; provider failures return 503 — consistent with existing pricing endpoints.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI 0.115.x, yfinance 0.2.x (`yf.Search`), pydantic 2.x, structlog 24.x  
**Storage**: None — lookups are not cached per spec assumption  
**Testing**: pytest 8.x, pytest-bdd 7.x, ruff, mypy (all existing, no new dev deps)  
**Target Platform**: Linux/Windows server (local deployment)  
**Project Type**: web-service (extending existing FastAPI application)  
**Performance Goals**: Same response envelope as existing endpoints; no new SLA for local deployment  
**Constraints**: No new external services; yfinance `Search` API for all identifier types; no Luhn check digit computation  
**Scale/Scope**: Low-volume local deployment; no caching or rate-limit concerns in initial scope

## Constitution Check

| Principle | Check | Notes |
|---|---|---|
| I. SOLID Design | ✓ Pass | New `IdentifierProvider` ABC segregates from `PricingProvider`; `YFinanceIdentifierProvider` is the only concrete impl; `IdentifierService` receives ABC via DI — zero modification to existing providers |
| II. Standard Dependencies | ✓ Pass | `yf.Search` is part of the already-pinned `yfinance==0.2.*`; stdlib `re` for format detection; no new packages added |
| III. BDD Test-First | ✓ Pass | `.feature` files for US1 and US2 authored and confirmed failing before implementation tasks begin |
| IV. Code Quality Standards | ✓ Pass | Existing `ruff` and `mypy --strict` config applies unchanged to all new modules |
| V. Observability & Logging | ✓ Pass | Structured log entries for: lookup request received, type detected, provider call dispatched, resolution result, and all error paths |
| VI. OpenAPI-First | ✓ Pass | `openapi.yaml` updated with `/identifiers/{identifier}` path and `TickerResolutionResponse` schema before any endpoint implementation |

No constitution violations — Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-identifier-to-ticker/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── identifiers.yaml # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
app/
├── providers/
│   ├── __init__.py                     # existing: PricingProvider ABC (unchanged)
│   ├── yfinance_provider.py            # existing (unchanged)
│   ├── cached_provider.py              # existing (unchanged)
│   ├── fx_provider.py                  # existing (unchanged)
│   └── identifier_provider.py          # NEW: IdentifierProvider ABC + YFinanceIdentifierProvider
├── services/
│   ├── pricing_service.py              # existing (unchanged)
│   ├── currency_service.py             # existing (unchanged)
│   ├── fx_aligner.py                   # existing (unchanged)
│   └── identifier_service.py           # NEW: IdentifierService (orchestration)
├── validators/
│   ├── __init__.py                     # existing (unchanged)
│   ├── currency.py                     # existing (unchanged)
│   └── identifier.py                   # NEW: format detection + validation logic
├── models/
│   └── pricing.py                      # MODIFIED: add TickerResolutionResponse
├── api/
│   ├── securities.py                   # existing (unchanged)
│   ├── fx.py                           # existing (unchanged)
│   ├── cache.py                        # existing (unchanged)
│   └── identifiers.py                  # NEW: GET /identifiers/{identifier} router
├── exceptions.py                       # MODIFIED: IdentifierFormatError, IdentifierNotFoundError
└── main.py                             # MODIFIED: include identifiers router + exception handlers

openapi.yaml                            # MODIFIED: new path + TickerResolutionResponse schema

tests/
├── features/
│   ├── identifier_lookup.feature       # NEW: US1 scenarios (happy path)
│   └── identifier_errors.feature       # NEW: US2 scenarios (error paths)
├── steps/
│   ├── identifier_lookup_steps.py      # NEW: US1 step definitions
│   └── identifier_errors_steps.py      # NEW: US2 step definitions
└── conftest.py                         # MODIFIED: add mock_identifier_provider + client_with_identifier fixtures
```

## Design Details

### IdentifierProvider ABC (`app/providers/identifier_provider.py`)

```python
class IdentifierProvider(ABC):
    @abstractmethod
    def lookup_ticker(self, identifier: str, identifier_type: str) -> dict[str, object]:
        """
        Resolve a pre-validated, normalised identifier to ticker info.
        Returns dict with keys: ticker (str), security_name (str), exchange (str).
        Raises IdentifierNotFoundError if data source returns no match.
        Raises ProviderUnavailableError on network failure.
        """
```

### YFinanceIdentifierProvider

Uses `yf.Search(identifier, max_results=1, news_count=0)`. Takes the first quote's `symbol`, `longname`/`shortname`, and `exchange`. Catches `requests` network exceptions → `ProviderUnavailableError`. Empty `.quotes` → `IdentifierNotFoundError`.

### IdentifierService (`app/services/identifier_service.py`)

Orchestration steps:
1. Normalise identifier to uppercase
2. Detect or validate identifier type (via `app/validators/identifier.py`)
3. Log `identifier_lookup` at INFO level (identifier, detected_type)
4. Delegate to `IdentifierProvider.lookup_ticker`
5. Log `identifier_resolved` at INFO level (ticker, exchange)
6. Return `TickerResolutionResponse`

### Validators (`app/validators/identifier.py`)

```python
ISIN_PATTERN  = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
CUSIP_PATTERN = re.compile(r"^[A-Z0-9]{9}$")
SEDOL_PATTERN = re.compile(r"^[A-Z0-9]{6,7}$")

def detect_identifier_type(identifier: str) -> str:
    """Normalise to uppercase, auto-detect type. Raises IdentifierFormatError if no match."""

def validate_identifier_format(identifier: str, identifier_type: str) -> None:
    """Validate against the specified type. Raises IdentifierFormatError if pattern fails."""
```

### New Models (`app/models/pricing.py` additions)

```python
class TickerResolutionResponse(BaseModel):
    identifier: str
    identifier_type: str
    ticker: str
    security_name: str
    exchange: str
```

### New Exceptions (`app/exceptions.py` additions)

```python
class IdentifierFormatError(Exception):
    def __init__(self, identifier: str, message: str | None = None) -> None: ...

class IdentifierNotFoundError(Exception):
    def __init__(self, identifier: str, message: str | None = None) -> None: ...
```

### API Endpoint (`app/api/identifiers.py`)

```python
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
```

### Exception Handlers (`app/main.py` additions)

```python
@app.exception_handler(IdentifierFormatError)
async def identifier_format_handler(...) -> JSONResponse:
    # 422, code="IDENTIFIER_FORMAT_ERROR"

@app.exception_handler(IdentifierNotFoundError)
async def identifier_not_found_handler(...) -> JSONResponse:
    # 404, code="IDENTIFIER_NOT_FOUND"
```

### OpenAPI additions

New path `GET /identifiers/{identifier}` with `TickerResolutionResponse` component schema. `identifier_type` query parameter with enum `[ISIN, CUSIP, SEDOL]`. Responses: 200, 404, 422, 503 (matching existing endpoint conventions).

### Test Fixtures (`tests/conftest.py` additions)

```python
@pytest.fixture()
def mock_identifier_provider() -> MagicMock:
    return MagicMock(spec=IdentifierProvider)

@pytest.fixture()
def client_with_identifiers(mock_identifier_provider) -> Generator[TestClient, None, None]:
    from app.api.identifiers import get_identifier_provider
    app.dependency_overrides[get_identifier_provider] = lambda: mock_identifier_provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### BDD Feature Files

**`tests/features/identifier_lookup.feature`** (US1):
- ISIN resolves to ticker (mock returns Apple data)
- CUSIP resolves to ticker
- SEDOL resolves to ticker
- Type hint provided, ISIN resolves correctly

**`tests/features/identifier_errors.feature`** (US2):
- Invalid format rejected with 422
- Valid format, unresolvable → 404
- Type hint provided but format conflicts → 422
- Provider unavailable → 503

## Structured Logging Plan

All log entries use structlog at the appropriate level.

| Event key | Level | Fields | Trigger |
|---|---|---|---|
| `identifier_lookup` | INFO | `identifier`, `identifier_type`, `type_hint` | Service called |
| `identifier_resolved` | INFO | `identifier`, `ticker`, `exchange`, `security_name` | Successful resolution |
| `identifier_format_error` | WARNING | `identifier`, `type_hint`, `detail` | Format validation fail |
| `identifier_not_found` | ERROR | `identifier`, `identifier_type`, `detail` | Provider returns no match |
| `provider_unavailable` | ERROR | `detail` | Network failure (existing handler reused) |

## Complexity Tracking

> No constitution violations — table not required.
