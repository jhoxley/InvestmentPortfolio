---
description: "Task list for Security Pricing API — 001-security-pricing-api"
---

# Tasks: Security Pricing API

**Input**: Design documents from `/specs/001-security-pricing-api/`
**Prerequisites**: plan.md ✅ spec.md ✅ data-model.md ✅ contracts/openapi.yaml ✅ research.md ✅

**Tests**: BDD Gherkin `.feature` files and step definitions are MANDATORY per the project constitution (Principle III — NON-NEGOTIABLE). They MUST be written and confirmed failing before any implementation task in the same user story begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All tasks include exact file paths

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — satisfies all six constitutional principles before any feature work begins

- [ ] T001 Create project directory structure: `app/`, `app/api/`, `app/services/`, `app/providers/`, `app/models/`, `tests/`, `tests/features/`, `tests/steps/`, `logs/`
- [ ] T002 [P] Create `pyproject.toml` with project metadata and pinned dependencies: fastapi==0.115.*, uvicorn[standard], yfinance==0.2.*, pydantic>=2.0, structlog, httpx, pytest, pytest-bdd, ruff, mypy
- [ ] T003 [P] Configure `ruff` linting rules in `pyproject.toml` (`[tool.ruff]` section — target-version, line-length, select rules); configure `mypy` strict mode in `[tool.mypy]` section
- [ ] T004 [P] Create `requirements.txt` with pinned versions matching `pyproject.toml` (use `pip freeze` after install to pin)
- [ ] T005 [P] Copy `specs/001-security-pricing-api/contracts/openapi.yaml` to project root `openapi.yaml` (authoritative committed contract)
- [ ] T006 [P] Add `logs/` and `__pycache__/` to `.gitignore`; create `logs/.gitkeep`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story implementation begins

**⚠️ CRITICAL**: No user story work begins until this phase is complete

- [ ] T007 Create `app/models/pricing.py` with Pydantic v2 models: `PriceResponse`, `PricePoint`, `PriceHistoryResponse`, `ErrorResponse` (fields per `specs/001-security-pricing-api/data-model.md`)
- [ ] T008 [P] Create `app/logging_config.py`: configure `structlog` with JSON renderer; attach `logging.handlers.RotatingFileHandler` writing to `logs/market-data-api.log` (max 10MB, 3 backups); also stream to console
- [ ] T009 [P] Create custom exception classes in `app/exceptions.py`: `DataNotFoundError`, `ProviderUnavailableError`, `InvalidTickerError`
- [ ] T010 [P] Create `app/providers/__init__.py` with abstract base class `PricingProvider` (methods: `get_current_price(ticker: str)`, `get_price_history(ticker: str, from_date, to_date)`)
- [ ] T011 Create `app/providers/yfinance_provider.py`: implement `YFinanceProvider(PricingProvider)` — stub methods that raise `NotImplementedError` (real implementation added in US1/US2 phases)
- [ ] T012 Create `app/services/pricing_service.py`: implement `PricingService` with constructor `__init__(self, provider: PricingProvider)` — stub methods returning `NotImplemented` (real implementation added per story)
- [ ] T013 [P] Create `app/api/securities.py`: `APIRouter(prefix="/securities", tags=["Securities"])` with stub route handlers for `GET /{ticker}/price` and `GET /{ticker}/history` returning 501
- [ ] T014 Create `app/main.py`: instantiate FastAPI app, register `securities` router, add HTTP request/response logging middleware using `structlog`, add global exception handlers skeleton, call `logging_config.setup_logging()`
- [ ] T015 [P] Create `tests/conftest.py`: define `client` fixture (FastAPI `TestClient`), define `mock_provider` fixture (returns a `MagicMock` implementing `PricingProvider` interface)

**Checkpoint**: Run `uvicorn app.main:app --reload` — server should start and return 501 on all `/securities/` routes. Run `ruff check app/ && mypy app/` — must pass with zero errors.

---

## Phase 3: User Story 1 — Current Price Endpoint (Priority: P1) 🎯 MVP

**Goal**: A consumer can GET the current price for any valid ticker and receive a well-formed JSON response.

**Independent Test**: `pytest tests/ -k current_price -v` — all US1 BDD scenarios green.

### BDD Scenarios for User Story 1 (MANDATORY — write and confirm failing FIRST) ⚠️

> **MUST fail before any implementation task below begins (Red-Green-Refactor)**

- [ ] T016 [P] [US1] Write `tests/features/current_price.feature` — Gherkin scenarios: (1) valid ticker returns 200 with price/currency/timestamp/market_status, (2) LSE ticker returns GBP currency, (3) price field is always positive (copy scenarios from `specs/001-security-pricing-api/spec.md` US1 verbatim)
- [ ] T017 [P] [US1] Write `tests/steps/current_price_steps.py` — implement `@given`, `@when`, `@then` step functions using `client` fixture from `conftest.py`; confirm all scenarios FAIL before proceeding

### Implementation for User Story 1

- [ ] T018 [US1] Implement `YFinanceProvider.get_current_price(ticker)` in `app/providers/yfinance_provider.py`: call `yfinance.Ticker(ticker).fast_info`; extract `last_price`, `currency`; raise `DataNotFoundError` if price is None or ≤ 0; raise `ProviderUnavailableError` on network exceptions
- [ ] T019 [US1] Implement `PricingService.get_current_price(ticker)` in `app/services/pricing_service.py`: call provider, validate price > 0, assemble `PriceResponse` with current UTC timestamp and `market_status` derived from `yfinance.Ticker.fast_info.market_state`
- [ ] T020 [US1] Implement `GET /securities/{ticker}/price` route in `app/api/securities.py`: inject `PricingService` via `Depends()`; catch `DataNotFoundError` → 404; catch `ProviderUnavailableError` → 503; return `PriceResponse`
- [ ] T021 [US1] Add global exception handlers to `app/main.py` for `DataNotFoundError` (→ 404 JSON), `ProviderUnavailableError` (→ 503 JSON), `InvalidTickerError` (→ 422 JSON); each response uses `ErrorResponse` schema

**Checkpoint**: `pytest tests/ -k current_price -v` — all US1 scenarios PASS. `curl http://localhost:8000/securities/AAPL/price` returns a valid JSON response with positive price.

---

## Phase 4: User Story 2 — Historical Price Series (Priority: P2)

**Goal**: A consumer can GET daily historical prices for any valid ticker and date range.

**Independent Test**: `pytest tests/ -k historical_price -v` — all US2 BDD scenarios green.

### BDD Scenarios for User Story 2 (MANDATORY — write and confirm failing FIRST) ⚠️

- [ ] T022 [P] [US2] Write `tests/features/historical_price.feature` — Gherkin scenarios: (1) valid ticker + date range returns ordered price list, (2) no date params returns default 30-day range with ≥1 entry, (3) from > to returns 422 (copy from spec.md US2 verbatim)
- [ ] T023 [P] [US2] Write `tests/steps/historical_price_steps.py` — step functions using `client` fixture; confirm all scenarios FAIL before proceeding

### Implementation for User Story 2

- [ ] T024 [US2] Implement `YFinanceProvider.get_price_history(ticker, from_date, to_date)` in `app/providers/yfinance_provider.py`: call `yfinance.Ticker(ticker).history(start=from_date, end=to_date)`; filter rows where Close ≤ 0; return list of `(date, close)` tuples; raise `DataNotFoundError` if result is empty; raise `ProviderUnavailableError` on network exceptions
- [ ] T025 [US2] Implement `PricingService.get_price_history(ticker, from_date, to_date)` in `app/services/pricing_service.py`: validate `from_date <= to_date` (raise `InvalidTickerError` with detail if not); default `from_date` to 30 days ago and `to_date` to today if None; call provider; assemble `PriceHistoryResponse` with chronologically sorted `prices` list
- [ ] T026 [US2] Implement `GET /securities/{ticker}/history` route in `app/api/securities.py`: accept optional `from` and `to` query params (type `date | None`); inject `PricingService`; delegate to service; return `PriceHistoryResponse`

**Checkpoint**: `pytest tests/ -k historical_price -v` — all US2 scenarios PASS. Both US1 and US2 scenarios pass together: `pytest tests/ -k "current_price or historical_price" -v`.

---

## Phase 5: User Story 3 — Error Handling (Priority: P3)

**Goal**: Invalid or unknown tickers and upstream failures always return a clear, standards-compliant error response.

**Independent Test**: `pytest tests/ -k error_handling -v` — all US3 BDD scenarios green.

### BDD Scenarios for User Story 3 (MANDATORY — write and confirm failing FIRST) ⚠️

- [ ] T027 [P] [US3] Write `tests/features/error_handling.feature` — Gherkin scenarios: (1) unknown ticker → 404 with `detail`, (2) malformed ticker → 422 with `detail`, (3) provider unavailable → 503 with `detail` (copy from spec.md US3 verbatim)
- [ ] T028 [P] [US3] Write `tests/steps/error_handling_steps.py` — step functions; for the 503 scenario use `monkeypatch` or override the DI provider to a mock that raises `ProviderUnavailableError`; confirm all scenarios FAIL before proceeding

### Implementation for User Story 3

- [ ] T029 [US3] Verify `yfinance_provider.py` raises `DataNotFoundError` for unknown tickers (e.g. `INVALIDXYZ99` returns empty data from yfinance — ensure this is caught and re-raised correctly)
- [ ] T030 [US3] Add path parameter validation for `ticker` in `app/api/securities.py`: use FastAPI `Path(..., min_length=1, pattern=r"^[A-Za-z0-9.\-^=]+$")` to auto-reject tickers with invalid characters (returns 422 automatically)
- [ ] T031 [US3] Confirm global exception handlers in `app/main.py` (added in T021) correctly map all three error types; add structured log entries at ERROR level for all exception handler invocations

**Checkpoint**: `pytest tests/ -v` — ALL scenarios across US1, US2, US3 PASS. Zero test failures.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, documentation, and validation of the complete service

- [ ] T032 [P] Run `ruff check app/ tests/` — fix all linting violations; run `mypy app/ --strict` — fix all type errors; commit clean state
- [ ] T033 [P] Export live OpenAPI schema: start server, run `python -c "import httpx; import json; r=httpx.get('http://localhost:8000/openapi.json'); print(json.dumps(r.json(), indent=2))" > openapi.yaml` — diff against committed `openapi.yaml` and update if needed
- [ ] T034 Run full BDD suite final confirmation: `pytest tests/ -v --tb=short` — all 9 scenarios (3 per story) PASS; record output
- [ ] T035 [P] Validate `specs/001-security-pricing-api/quickstart.md` end-to-end: start server → curl current price → curl history → check `logs/market-data-api.log` for JSON entries
- [ ] T036 [P] Update `specs/001-security-pricing-api/checklists/requirements.md` — verify all checklist items still pass post-implementation
- [ ] T037 [P] Create `tests/steps/__init__.py` if missing; ensure `pytest tests/` discovers all feature files without configuration changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; all T001–T006 can run in parallel
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories; T007–T015 have internal ordering (models before services before routes)
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion — BDD tasks (T016, T017) FIRST, then implementation
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion — can start in parallel with US1 after foundation
- **User Story 3 (Phase 5)**: Depends on Phase 2 completion — most tasks verify behaviour already built in US1/US2
- **Polish (Phase 6)**: Depends on all user story phases complete

### Within Each User Story (strict ordering)

1. Write `.feature` file(s) → 2. Write step definitions → 3. **Confirm all FAIL** → 4. Implement provider method → 5. Implement service method → 6. Implement route → 7. **Confirm all PASS**

### Parallel Opportunities

```bash
# Phase 1 — all parallel:
Task: "T002 Create pyproject.toml"
Task: "T003 Configure ruff + mypy"
Task: "T004 Create requirements.txt"
Task: "T005 Copy openapi.yaml to project root"
Task: "T006 Update .gitignore"

# Phase 2 — T007 first (models), then parallel:
Task: "T008 Create logging_config.py"
Task: "T009 Create exceptions.py"
Task: "T010 Create PricingProvider ABC"

# US1 BDD — parallel:
Task: "T016 Write current_price.feature"
Task: "T017 Write current_price_steps.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T006)
2. Complete Phase 2: Foundational (T007–T015) — **CRITICAL, blocks all stories**
3. Complete Phase 3: User Story 1 (T016–T021)
4. **STOP and VALIDATE**: `pytest tests/ -k current_price -v` all green; `curl localhost:8000/securities/AAPL/price` returns valid JSON
5. Deploy/demo at this point if needed — current price endpoint is fully functional

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add US1 (current price) → test independently → demo MVP ✅
3. Add US2 (historical prices) → test independently → demo enhanced
4. Add US3 (error handling) → test independently → service is production-quality
5. Polish → final quality gates

---

## Summary

| Phase | Tasks | Parallel | User Story |
|-------|-------|----------|------------|
| Setup | T001–T006 | 5 of 6 | — |
| Foundational | T007–T015 | partial | — |
| US1 Current Price | T016–T021 | 2 BDD tasks | P1 (MVP) |
| US2 Historical | T022–T026 | 2 BDD tasks | P2 |
| US3 Error Handling | T027–T031 | 2 BDD tasks | P3 |
| Polish | T032–T037 | 5 of 6 | — |
| **Total** | **37** | | |

**BDD scenarios**: 9 total (3 per user story) — all executable via `pytest tests/ -v`
