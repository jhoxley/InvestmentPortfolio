# Implementation Plan: Security Pricing API

**Branch**: `001-security-pricing-api` | **Date**: 2026-05-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-security-pricing-api/spec.md`

## Summary

Implement a locally hosted Python FastAPI web service that exposes two RESTful endpoints — current price and historical price series — for individual securities identified by Yahoo Finance ticker symbols. The `yfinance` package is the sole data provider. All Gherkin acceptance scenarios from the spec are implemented as executable `pytest-bdd` tests. Structured JSON logging via `structlog` covers every request and response. An OpenAPI 3.1.0 contract (`openapi.yaml`) is authored and committed before any endpoint is implemented.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.115.x, uvicorn, yfinance 0.2.x, pydantic 2.x, structlog, pytest-bdd, pytest, httpx, ruff, mypy
**Storage**: N/A — no persistence; all data fetched live from Yahoo Finance per request
**Testing**: pytest-bdd (Gherkin BDD), pytest, httpx TestClient for end-to-end HTTP testing
**Target Platform**: Local machine — Windows/macOS/Linux; `localhost:8000`
**Project Type**: web-service
**Performance Goals**: Current price response < 3s; 12-month historical series < 5s (per SC-001/SC-002)
**Constraints**: Internet access required; no authentication required for v1; no caching in v1
**Scale/Scope**: Single user, personal portfolio tool

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Notes |
|-----------|-------|-------|
| I. SOLID Design | ✅ | Router → Service → Provider layering; DI via FastAPI `Depends()`; each class has one responsibility |
| II. Standard Dependencies | ✅ | FastAPI, yfinance, pydantic, structlog, pytest-bdd, ruff, mypy — all industry-standard; pinned in requirements.txt |
| III. BDD Test-First | ✅ | `.feature` files authored and step definitions confirmed failing before any endpoint implementation begins |
| IV. Code Quality Standards | ✅ | `ruff` + `mypy --strict` configured in `pyproject.toml`; same rules for app and test code |
| V. Observability & Logging | ✅ | `structlog` JSON logging covers all requests, responses, errors, and durations; written to `logs/` |
| VI. OpenAPI-First | ✅ | `openapi.yaml` contract authored and committed before endpoint implementation (see `contracts/openapi.yaml`) |

All six principles pass. No violations to document.

## Project Structure

### Documentation (this feature)

```text
specs/001-security-pricing-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output — OpenAPI contract
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
market-data-web-service/
├── app/
│   ├── main.py                    # FastAPI app: instantiation, router registration, lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   └── securities.py          # APIRouter: /securities/{ticker}/price and /history
│   ├── services/
│   │   ├── __init__.py
│   │   └── pricing_service.py     # PricingService: validation, zero-price filtering, response assembly
│   ├── providers/
│   │   ├── __init__.py
│   │   └── yfinance_provider.py   # YFinanceProvider: all yfinance calls; maps exceptions to provider errors
│   ├── models/
│   │   ├── __init__.py
│   │   └── pricing.py             # Pydantic models: PriceResponse, PriceHistoryResponse, ErrorResponse
│   └── logging_config.py          # structlog configuration; JSON formatter; rotating file handler
├── tests/
│   ├── features/
│   │   ├── current_price.feature  # BDD scenarios for US1
│   │   ├── historical_price.feature # BDD scenarios for US2
│   │   └── error_handling.feature # BDD scenarios for US3
│   ├── steps/
│   │   ├── __init__.py
│   │   ├── current_price_steps.py
│   │   ├── historical_price_steps.py
│   │   └── error_handling_steps.py
│   └── conftest.py                # FastAPI TestClient fixture; yfinance mock fixture
├── openapi.yaml                   # OpenAPI contract committed to repo root
├── pyproject.toml                 # ruff + mypy configuration
├── requirements.txt               # Pinned dependencies
└── logs/                          # JSON log output (git-ignored)
```

**Structure Decision**: Single web-service project. The `app/` package follows SOLID single-responsibility layering (api → service → provider → model). The `tests/` directory mirrors Gherkin feature files with corresponding step modules.

## Complexity Tracking

> No violations — all constitution checks pass.

---

## Phase 0: Research Summary

All unknowns resolved. See [research.md](research.md) for full decision log.

| Topic | Decision |
|-------|----------|
| Web framework | FastAPI — built-in OpenAPI, async, Pydantic |
| Data provider | `yfinance` — direct use via provider abstraction |
| BDD testing | `pytest-bdd` — Gherkin + pytest runner, CLI-executable |
| Structured logging | `structlog` — JSON output to console + rotating file |
| Linting / type-checking | `ruff` + `mypy --strict` in `pyproject.toml` |
| Caching | None in v1 — live fetch on every request |
| OpenAPI contract | FastAPI auto-generates; `openapi.yaml` exported and committed |

---

## Phase 1: Design Artifacts

- [data-model.md](data-model.md) — entities, Pydantic schemas, module boundaries
- [contracts/openapi.yaml](contracts/openapi.yaml) — OpenAPI 3.1.0 contract for both endpoints
- [quickstart.md](quickstart.md) — setup, run server, run BDD tests, check logs

---

## Implementation Notes

### Dependency Injection Pattern (Principle I)

```python
# app/api/securities.py
from fastapi import APIRouter, Depends
from app.services.pricing_service import PricingService

router = APIRouter(prefix="/securities", tags=["Securities"])

def get_pricing_service() -> PricingService:
    from app.providers.yfinance_provider import YFinanceProvider
    return PricingService(provider=YFinanceProvider())

@router.get("/{ticker}/price")
async def get_current_price(ticker: str, service: PricingService = Depends(get_pricing_service)):
    ...
```

The router depends on `PricingService` (abstract interface); `YFinanceProvider` is injected at runtime. Tests inject a mock provider instead.

### BDD Test Execution

All Gherkin scenarios run via a single command:
```powershell
pytest tests/ -v
```

The `conftest.py` provides a `TestClient` fixture wrapping the FastAPI app. The upstream provider (yfinance) is mocked in the `error_handling` feature tests to simulate 503 scenarios without network calls.

### Logging on Every Request

A FastAPI middleware in `app/main.py` logs each request/response using structlog:
```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    logger.info("request", method=request.method, path=request.url.path,
                status=response.status_code, duration_ms=round((time.time()-start)*1000, 2))
    return response
```

### Zero-Price Filtering

The `PricingService` rejects any price ≤ 0 from the provider and raises a `DataNotAvailableError`, which the router maps to a 404 response. This is enforced for both current and historical price endpoints.
