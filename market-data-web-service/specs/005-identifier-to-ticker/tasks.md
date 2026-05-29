# Tasks: Identifier-to-Ticker Lookup

**Input**: Design documents from `/specs/005-identifier-to-ticker/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/identifiers.yaml ✓, quickstart.md ✓

**Tests**: BDD Gherkin `.feature` files and their step definitions are MANDATORY per the project constitution (Principle III). They MUST be written and confirmed failing before any implementation task in the same user story begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (`US1`, `US2`)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (OpenAPI Contract — Constitutional Prerequisite)

**Purpose**: Author the OpenAPI contract before any endpoint implementation (Constitution Principle VI: OpenAPI-First).

- [X] T001 Update `openapi.yaml` — add `GET /identifiers/{identifier}` path with `identifier` path param (string, minLength 1), optional `type` query param (enum: ISIN, CUSIP, SEDOL), responses 200/404/422/503 referencing `TickerResolutionResponse` and `ErrorResponse` schemas; add `TickerResolutionResponse` component schema (fields: `identifier`, `identifier_type`, `ticker`, `security_name`, `exchange`, all required strings)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required by both user stories. MUST be complete before user story phases begin.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `IdentifierFormatError(identifier, message)` and `IdentifierNotFoundError(identifier, message)` to `app/exceptions.py` — follow the existing exception pattern (store `self.identifier`, `self.message`, call `super().__init__(self.message)`)
- [X] T003 [P] Add `TickerResolutionResponse(BaseModel)` to `app/models/pricing.py` with fields: `identifier: str`, `identifier_type: str`, `ticker: str`, `security_name: str`, `exchange: str` (all required, no defaults)
- [X] T004 [P] Create `app/validators/identifier.py` — define `ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")`, `CUSIP_PATTERN = re.compile(r"^[A-Z0-9]{9}$")`, `SEDOL_PATTERN = re.compile(r"^[A-Z0-9]{6,7}$")`; implement `detect_identifier_type(identifier: str) -> str` (normalise to uppercase, match in ISIN→CUSIP→SEDOL priority order, raise `IdentifierFormatError` if none match); implement `validate_identifier_format(identifier: str, identifier_type: str) -> None` (validate normalised identifier against the named type's pattern, raise `IdentifierFormatError` if no match)
- [X] T005 Create `app/providers/identifier_provider.py` — define `IdentifierProvider(ABC)` with abstract method `lookup_ticker(self, identifier: str, identifier_type: str) -> dict[str, object]`; implement `YFinanceIdentifierProvider(IdentifierProvider)` using `yf.Search(identifier, max_results=1, news_count=0)`; if `.quotes` is empty raise `IdentifierNotFoundError(identifier)`; return `{"ticker": quote["symbol"], "security_name": quote.get("longname") or quote.get("shortname") or "", "exchange": quote.get("exchange") or ""}`; catch `requests.exceptions.ConnectionError`, `requests.exceptions.Timeout`, `requests.exceptions.RequestException` and raise `ProviderUnavailableError`
- [X] T006 Create `app/services/identifier_service.py` — define `IdentifierService` with `__init__(self, provider: IdentifierProvider)`; implement `resolve(self, identifier: str, type_hint: str | None) -> TickerResolutionResponse`: normalise identifier to uppercase, call `validate_identifier_format(identifier, type_hint)` if hint provided else `detect_identifier_type(identifier)` to get `identifier_type`, delegate to `self._provider.lookup_ticker(identifier, identifier_type)`, return `TickerResolutionResponse` with all five fields populated
- [X] T007 Add `mock_identifier_provider` fixture (`MagicMock(spec=IdentifierProvider)`) and `client_with_identifiers` fixture (overrides `get_identifier_provider` dependency with a lambda returning `mock_identifier_provider`) to `tests/conftest.py`

**Checkpoint**: Foundation ready — user story BDD tests can now be authored and confirmed failing.

---

## Phase 3: User Story 1 — Translate a Security Identifier to a Ticker (Priority: P1) 🎯 MVP

**Goal**: A client submits an ISIN, CUSIP, or SEDOL and receives the resolved ticker, security name, and exchange in a single API call.

**Independent Test**: Submit ISIN `US0378331005` with mock returning `{"ticker": "AAPL", "security_name": "Apple Inc.", "exchange": "NMS"}` → HTTP 200, body fields all present and non-empty.

### BDD Scenarios for User Story 1 — MUST fail before implementation tasks below ⚠️

- [X] T008 [P] [US1] Write `tests/features/identifier_lookup.feature` with 4 scenarios: (1) ISIN "US0378331005" resolves to ticker — status 200, non-empty `ticker`/`security_name`/`exchange` fields; (2) CUSIP "037833100" resolves to ticker — status 200, non-empty `ticker`; (3) SEDOL "B020QX2" resolves to ticker — status 200, non-empty `ticker`; (4) ISIN with explicit `type=ISIN` hint resolves correctly — status 200, `identifier_type` is "ISIN"
- [X] T009 [P] [US1] Write `tests/steps/identifier_lookup_steps.py` — implement `scenarios("identifier_lookup.feature")`; write `given`/`when`/`then` steps: given steps configure `mock_identifier_provider.lookup_ticker.return_value` with appropriate dict; when step calls `client_with_identifiers.get("/identifiers/{identifier}")` (with optional `?type=` param) as `target_fixture="response"`; then steps assert `response.status_code == 200`, `response.json()["ticker"]` is a non-empty string, `response.json()["identifier_type"]` matches expected value; run `pytest tests/steps/identifier_lookup_steps.py` and confirm all scenarios fail (red — endpoint does not exist)

### Implementation for User Story 1

- [X] T010 [US1] Create `app/api/identifiers.py` — define `router = APIRouter(prefix="/identifiers", tags=["Identifiers"])`; define `get_identifier_provider() -> YFinanceIdentifierProvider` (returns `YFinanceIdentifierProvider()`); define `get_identifier_service(provider: IdentifierProvider = Depends(get_identifier_provider)) -> IdentifierService` (returns `IdentifierService(provider=provider)`); implement `GET /{identifier}` endpoint with `identifier: str = Path(..., min_length=1)` and `identifier_type_hint: str | None = Query(default=None, alias="type")` and `service: IdentifierService = Depends(get_identifier_service)`, returning `service.resolve(identifier, identifier_type_hint)` with `response_model=TickerResolutionResponse`
- [X] T011 [US1] Register identifiers router in `app/main.py` — add `from app.api import identifiers`; add `app.include_router(identifiers.router)`; add `@app.exception_handler(IdentifierFormatError)` returning 422 with `ErrorResponse(detail=exc.message, code="IDENTIFIER_FORMAT_ERROR")`; add `@app.exception_handler(IdentifierNotFoundError)` returning 404 with `ErrorResponse(detail=exc.message, code="IDENTIFIER_NOT_FOUND")`; import both exception types at the top of `app/main.py`
- [X] T012 [US1] Add structured logging to `app/services/identifier_service.py` — import `structlog`; add `logger = structlog.get_logger(__name__)`; log `logger.info("identifier_lookup", identifier=identifier, identifier_type=identifier_type, type_hint=type_hint)` after type detection; log `logger.info("identifier_resolved", identifier=identifier, ticker=result["ticker"], exchange=result["exchange"])` after successful provider call
- [X] T013 [US1] Verify all 4 US1 BDD scenarios pass green — run `pytest tests/steps/identifier_lookup_steps.py -v` and confirm zero failures

**Checkpoint**: US1 fully functional. ISIN, CUSIP, and SEDOL resolve to ticker via `GET /identifiers/{identifier}`.

---

## Phase 4: User Story 2 — Graceful Rejection of Invalid or Unresolvable Identifiers (Priority: P2)

**Goal**: Clients receive clear, machine-readable errors for malformed identifiers (422) and valid-format identifiers that cannot be resolved (404).

**Independent Test**: Submit `"NOT-VALID-FORMAT"` → HTTP 422, `code == "IDENTIFIER_FORMAT_ERROR"`, non-empty `detail`; submit `"US0000000000"` with mock raising `IdentifierNotFoundError` → HTTP 404, `code == "IDENTIFIER_NOT_FOUND"`.

### BDD Scenarios for User Story 2 — MUST fail before implementation tasks below ⚠️

- [X] T014 [P] [US2] Write `tests/features/identifier_errors.feature` with 4 scenarios: (1) "NOT-VALID-FORMAT" → status 422, response contains descriptive error message; (2) "US0000000000" with mock raising `IdentifierNotFoundError` → status 404, error message indicates not found; (3) "NOT-VALID-FORMAT" with `?type=ISIN` → status 422, format error; (4) provider raises `ProviderUnavailableError` → status 503
- [X] T015 [P] [US2] Write `tests/steps/identifier_errors_steps.py` — implement `scenarios("identifier_errors.feature")`; given steps configure `mock_identifier_provider.lookup_ticker.side_effect` to raise `IdentifierNotFoundError` or `ProviderUnavailableError` as required; when steps call `client_with_identifiers.get(...)` as `target_fixture="response"`; then steps assert status codes and response body `code` / `detail` fields; run `pytest tests/steps/identifier_errors_steps.py` and confirm scenarios that depend on the endpoint fail (red)

### Implementation for User Story 2

- [X] T016 [US2] Add ERROR-level structured logging for error paths in `app/services/identifier_service.py` — log `logger.warning("identifier_format_error", identifier=identifier, type_hint=type_hint, detail=exc.message)` when `IdentifierFormatError` is raised; add ERROR-level logging in `app/main.py` exception handlers for `IdentifierNotFoundError` and `IdentifierFormatError` following the existing handler pattern (include `identifier=exc.identifier` field)
- [X] T017 [US2] Verify all 4 US2 BDD scenarios pass green — run `pytest tests/steps/identifier_errors_steps.py -v` and confirm zero failures

**Checkpoint**: US1 and US2 both fully functional. All error paths return structured, machine-readable responses.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T018 [P] Run `ruff check app/exceptions.py app/models/pricing.py app/validators/identifier.py app/providers/identifier_provider.py app/services/identifier_service.py app/api/identifiers.py app/main.py tests/conftest.py tests/steps/identifier_lookup_steps.py tests/steps/identifier_errors_steps.py` and fix all violations (E, F, W, I, UP, ANN, B, SIM, RUF rules)
- [X] T019 [P] Run `mypy app/exceptions.py app/models/pricing.py app/validators/identifier.py app/providers/identifier_provider.py app/services/identifier_service.py app/api/identifiers.py app/main.py` in strict mode and fix all type errors
- [X] T020 Run full pytest suite `pytest -v` and confirm all scenarios green with zero regressions in existing features (current_price, historical_price, error_handling, cache, fx, currency translation)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (logical; openapi contract informs models) — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 completion
- **Phase 4 (US2)**: BDD tasks (T014, T015) can start after Phase 2; implementation (T016, T017) requires Phase 3 completion
- **Phase 5 (Polish)**: Depends on Phase 4 completion

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 — no dependencies on other stories
- **US2 (P2)**: BDD files independent; implementation depends on Phase 3 (endpoint must exist for error-path tests to pass)

### Within Each Phase

- T002, T003, T004 are fully parallel (different files, no shared imports)
- T005 depends on T002 (imports `IdentifierNotFoundError`)
- T006 depends on T002, T003, T004 (imports all three)
- T007 depends on T005 (needs `IdentifierProvider` spec for `MagicMock`)
- T008, T009 are parallel (feature file and step file are independent)
- T010 depends on T005, T006
- T011 depends on T010
- T012 can be done alongside T010 (same file) or as a separate pass
- T013 depends on T011 (endpoint registered in app)
- T014, T015 parallel; T015 depends on T014 (steps file references feature file)
- T016 modifies files touched in T006, T011 — sequential after T011
- T017 depends on T016 and T011
- T018, T019 parallel (ruff vs mypy, different tools)
- T020 depends on T017, T018, T019

### Parallel Opportunities

- T002 + T003 + T004 (Phase 2 setup — all different files)
- T008 + T009 (US1 BDD authoring — feature file and steps)
- T014 + T015 (US2 BDD authoring)
- T018 + T019 (Polish — ruff and mypy run independently)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Update openapi.yaml
2. Complete Phase 2: Foundation (exceptions, model, validator, provider, service, fixtures)
3. Write US1 BDD tests (confirm red)
4. Implement US1: `app/api/identifiers.py` + `app/main.py` registration
5. **STOP and VALIDATE**: `GET /identifiers/US0378331005` returns ticker

### Incremental Delivery

1. Phase 1 + Phase 2 → all infrastructure ready
2. Phase 3 (US1) → identifier resolution working end-to-end → MVP
3. Phase 4 (US2) → clear error messages for invalid/unresolvable identifiers
4. Phase 5 → quality gates pass, full regression suite green

---

## Notes

- The `identifier_type` query param alias is `"type"` (reserved Python keyword — use `alias="type"` in FastAPI `Query`)
- `YFinanceIdentifierProvider` does NOT extend `PricingProvider` — it implements the new `IdentifierProvider` ABC (Interface Segregation, Constitution Principle I)
- No caching layer for identifier lookups — per spec assumption, results are not cached in the initial implementation
- `ProviderUnavailableError` is reused from existing `app/exceptions.py` — no new exception needed for network failures
- `mock_identifier_provider` in `client_with_identifiers` overrides `get_identifier_provider`, NOT `get_identifier_service` — this keeps the real `IdentifierService` in the test path for accurate integration coverage
