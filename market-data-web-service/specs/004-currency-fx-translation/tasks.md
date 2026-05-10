# Tasks: Currency Translation & FX Pair Endpoint

**Input**: Design documents from `specs/004-currency-fx-translation/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi-additions.yaml ✅, quickstart.md ✅

**Tests**: BDD Gherkin `.feature` files and their step definitions are MANDATORY per the project constitution (Principle III). They MUST be written and confirmed failing before any implementation task in the same user story begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on concurrent tasks)
- **[Story]**: Which user story this task belongs to (US1–US3)
- Exact file paths are included in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the OpenAPI contract before any implementation begins (Principle VI — OpenAPI-First).

- [X] T001 Merge `specs/004-currency-fx-translation/contracts/openapi-additions.yaml` into `openapi.yaml` — add `GET /fx/{pair}/history` path; add `currency` query param to `/securities/{ticker}/price` and `/securities/{ticker}/history`; add `FxRateEntry`, `FxHistoryResponse` component schemas; update `PricePoint` and `PriceResponse` schemas with `fx_rate` field

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story begins. No user story work starts until this phase is done.

- [X] T002 Update `app/exceptions.py` — add `FxAlignmentError(pair: str, security_date: date, message: str | None = None)` mapping to HTTP 404; add `CurrencyUnavailableError(ticker: str, message: str | None = None)` mapping to HTTP 404; add `InvalidCurrencyError(code: str, message: str | None = None)` mapping to HTTP 422; add `InvalidCurrencyPairError(pair: str, message: str | None = None)` mapping to HTTP 422
- [X] T003 [P] Create `app/validators/__init__.py` (empty module marker)
- [X] T004 [P] Create `app/validators/currency.py` — define `_ISO_4217_CODES: frozenset[str]` containing all ~170 ISO 4217 alphabetic currency codes (USD, GBP, EUR, JPY, CHF, AUD, CAD, HKD, SGD, NOK, SEK, DKK, NZD, MXN, ZAR, BRL, INR, CNY, KRW, and all others from the ISO 4217 maintenance table); implement `validate_currency_code(code: str) -> None` that raises `InvalidCurrencyError` if `code.upper()` is not a member of the set
- [X] T005 [P] Create `app/providers/fx_provider.py` — implement `FxInnerProvider(PricingProvider)` with `__init__(self, inner: PricingProvider)`; `get_current_price()` raises `NotImplementedError`; `get_price_history(pair, from_date, to_date)` constructs `fx_ticker = f"{pair}=X"` then delegates to `self._inner.get_price_history(fx_ticker, from_date, to_date)` — this adapter allows `CachedPricingProvider` to cache under the pair code while yfinance receives the `=X` suffix
- [X] T006 [P] Create `app/services/fx_aligner.py` — implement `FxAligner` class with `align_rates(self, security_dates: list[date], fx_series: list[tuple[date, float]]) -> dict[date, float]`; build `fx_map = dict(fx_series)`, `sorted_fx_dates = sorted(fx_map.keys())`; for each security date use `bisect_right(sorted_fx_dates, sec_date) - 1` for forward-fill (nearest prior); if idx < 0 use `bisect_left(sorted_fx_dates, sec_date)` for backward-fill (nearest subsequent); if neither resolves raise `FxAlignmentError(pair="", security_date=sec_date)`; import `bisect` from stdlib only
- [X] T007 Update `app/models/pricing.py` — add `fx_rate: float | None = None` field to `PricePoint`; add `fx_rate: float | None = None` field to `PriceResponse`; add new `FxRateEntry(BaseModel)` with `date: date` and `rate: float = Field(gt=0.0)`; add new `FxHistoryResponse(BaseModel)` with `pair: str`, `base_currency: str`, `quote_currency: str`, `rates: list[FxRateEntry]`
- [X] T008 Create `app/services/currency_service.py` — implement `CurrencyService` with `__init__(self, fx_provider: PricingProvider, aligner: FxAligner)`; implement `get_native_currency(ticker: str, security_provider: PricingProvider) -> str` by calling `security_provider.get_current_price(ticker)["currency"]`, raising `CurrencyUnavailableError(ticker)` on failure; implement `translate_current(ticker: str, response: PriceResponse, target_currency: str, security_provider: PricingProvider) -> PriceResponse` — fetch most recent FX rate via `fx_provider.get_price_history(pair, as_of_date, as_of_date)` (or use cache), multiply price, set `fx_rate`, log `currency_translation`; implement `translate_history(ticker: str, records: list[PricePoint], native_currency: str, target_currency: str, from_date: date, to_date: date) -> list[PricePoint]` — fetch FX series for `[from_date, to_date]`, call `aligner.align_rates()`, apply each rate, log `fx_align_fill` per fill operation
- [X] T009 Update `tests/conftest.py` — add `mock_fx_provider() -> MagicMock` fixture returning `MagicMock(spec=PricingProvider)`; add `client_with_fx(tmp_cache_dir, mock_inner_provider, mock_fx_provider) -> Generator[TestClient, None, None]` fixture that overrides `get_settings` → `Settings(cache=CacheSettings(directory=tmp_cache_dir))`, `get_pricing_service` → `PricingService(CachedPricingProvider(mock_inner_provider, repo))`, and `get_currency_service` → `CurrencyService(fx_provider=CachedPricingProvider(mock_fx_provider, repo), aligner=FxAligner())`

**Checkpoint**: Foundation ready — all user story implementation can now begin.

---

## Phase 3: User Story 1 — Currency Translation on Current Price (Priority: P1) 🎯 MVP

**Goal**: `GET /securities/{ticker}/price?currency=GBP` returns the current price translated to the requested currency. Without the `currency` param, behaviour is unchanged. Invalid codes return 422.

**Independent Test**: Seed a mock security provider returning price + native currency. Call with `?currency=GBP`. Assert translated price = native_price × fx_rate; assert `fx_rate` field present; assert `currency` field = target. Call without param; assert unchanged. Call with `?currency=INVALID`; assert 422.

### BDD Scenarios for User Story 1 (MANDATORY — write and confirm failing FIRST) ⚠️

> **MUST be red before any implementation task below begins (Red-Green-Refactor)**

- [X] T010 [P] [US1] Write `tests/features/currency_translation_current.feature` — 4 scenarios from spec US1: "Current price returned in native currency when no target currency specified", "Current price translated to requested target currency", "No translation applied when requested currency matches native currency", "Invalid currency code returns a validation error"
- [X] T011 [P] [US1] Write `tests/steps/currency_translation_current_steps.py` — step definitions using `client_with_fx` fixture; seed mock_inner_provider to return AAPL current price in USD; seed mock_fx_provider to return a USDGBP rate; assert translated close ≈ price × fx_rate; assert `currency` and `fx_rate` fields in response; run `pytest tests/features/currency_translation_current.feature` and confirm all scenarios fail (red)

### Implementation for User Story 1

- [X] T012 [US1] Add `get_currency_service` factory function to `app/api/securities.py` — `def get_currency_service(settings: Settings = Depends(get_settings)) -> CurrencyService`: creates `CacheRepository(settings.cache.directory)`, `CachedPricingProvider(FxInnerProvider(YFinanceProvider()), repo)`, `FxAligner()`, returns `CurrencyService(fx_provider, aligner)`
- [X] T013 [US1] Update `get_current_price()` endpoint in `app/api/securities.py` — add `currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$")` param; add `currency_svc: CurrencyService = Depends(get_currency_service)` param; if `currency` is not None call `validate_currency_code(currency)` (raises `InvalidCurrencyError`→422); call `service.get_current_price(ticker)`; if `currency` and `currency != response.currency` call `currency_svc.translate_current(ticker, response, currency, provider)` and return result; otherwise return response unchanged
- [X] T014 [US1] Update `app/main.py` — add exception handlers: `InvalidCurrencyError` → 422 with `ErrorResponse(detail=exc.message, code="INVALID_CURRENCY")`; `InvalidCurrencyPairError` → 422 with code `"INVALID_CURRENCY_PAIR"`; `FxAlignmentError` → 404 with code `"FX_ALIGNMENT_ERROR"`; `CurrencyUnavailableError` → 404 with code `"CURRENCY_UNAVAILABLE"`
- [X] T015 [US1] Add structured logging to `app/services/currency_service.py` — log `currency_translation` at INFO with fields `ticker`, `native_currency`, `target_currency`, `fx_rate` after translating current price; log `fx_align_no_translation` at INFO with fields `ticker`, `currency` when native == target (no-op path)

**Checkpoint**: User Story 1 fully functional. Run `pytest tests/features/currency_translation_current.feature` — all green.

---

## Phase 4: User Story 2 — Currency Translation on Historical Prices (Priority: P2)

**Goal**: `GET /securities/{ticker}/history?from=...&to=...&currency=GBP` returns the full date series with each entry translated using the nearest available FX rate (forward-fill first, backward-fill fallback). Each entry includes `fx_rate`. Without the `currency` param, behaviour is unchanged.

**Independent Test**: Seed mock security price series for AAPL (USD) and mock FX series for USDGBP with a deliberate gap on one date. Call history with `?currency=GBP`. Assert every entry has a non-null `fx_rate`. Assert the gap date uses the forward-filled rate. Assert translated close ≈ native close × fx_rate. Assert `currency` field in response = "GBP".

### BDD Scenarios for User Story 2 (MANDATORY — write and confirm failing FIRST) ⚠️

- [X] T016 [P] [US2] Write `tests/features/currency_translation_history.feature` — 4 scenarios from spec US2: "Historical prices translated across the full requested date range", "FX rate forward-filled when FX market is closed on a security trading day", "FX rate backward-filled when no prior rate exists", "No translation applied when native currency matches requested currency"
- [X] T017 [P] [US2] Write `tests/steps/currency_translation_history_steps.py` — step definitions using `client_with_fx`; seed `mock_inner_provider.get_price_history` with AAPL USD series; seed `mock_fx_provider.get_price_history` with USDGBP series that has a missing date; assert forward-fill logic; assert `fx_rate` field on every translated entry; confirm all scenarios fail (red)

### Implementation for User Story 2

- [X] T018 [US2] Update `get_price_history()` endpoint in `app/api/securities.py` — add `currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$")` param; add `currency_svc: CurrencyService = Depends(get_currency_service)` param; if `currency` provided call `validate_currency_code(currency)`; get `PriceHistoryResponse` from service; if `currency` and `currency != response.currency` call `currency_svc.translate_history(ticker, response.prices, response.currency, currency, resolved_from, resolved_to)` and return new response with translated prices and target currency; note `pricing_service.get_price_history()` resolves from/to dates internally — pass the resolved dates to `translate_history`
- [X] T019 [US2] Add structured logging to `CurrencyService.translate_history()` in `app/services/currency_service.py` — log `fx_fetch` at INFO with fields `pair`, `from_date`, `to_date` before fetching FX series; log `fx_align_fill` at INFO for each forward or backward fill with fields `pair`, `security_date`, `fx_date_used`, `fill_direction` (`"forward"` or `"backward"`); log `fx_align_error` at ERROR on `FxAlignmentError` before re-raising

**Checkpoint**: User Stories 1 and 2 functional. Run `pytest tests/features/currency_translation_current.feature tests/features/currency_translation_history.feature` — all green.

---

## Phase 5: User Story 3 — FX Pair History Endpoint (Priority: P3)

**Goal**: `GET /fx/USDGBP/history?from=...&to=...` returns the dated FX rate series for the pair, fully cached (hit/partial-hit/miss). Invalid codes return 422. Reversed date range returns 422.

**Independent Test**: Seed `USDGBP.csv` in `tmp_cache_dir` for a date range. Call `GET /fx/USDGBP/history` for that range via `client_with_fx`. Assert 200 with `pair`, `base_currency`, `quote_currency`, `rates`. Assert entries are chronologically ascending. Assert no external call made (mock_fx_provider not called). Then call with `?from=2025-03-31&to=2025-01-02`; assert 422.

### BDD Scenarios for User Story 3 (MANDATORY — write and confirm failing FIRST) ⚠️

- [X] T020 [P] [US3] Write `tests/features/fx_history.feature` — 4 scenarios from spec US3: "FX pair history returned for a valid currency pair and date range", "FX pair history served from cache on repeated request", "Invalid ISO currency code returns a validation error", "Start date after end date returns a validation error"
- [X] T021 [P] [US3] Write `tests/steps/fx_history_steps.py` — step definitions using `client_with_fx`; seed `CacheRepository(tmp_cache_dir).write("USDGBP", [...])` for cache-hit scenario; seed `mock_fx_provider.get_price_history` for cache-miss scenario; assert response structure matches `FxHistoryResponse`; assert cache-hit scenario does not call `mock_fx_provider`; confirm all scenarios fail (red)

### Implementation for User Story 3

- [X] T022 [US3] Create `app/api/fx.py` — `APIRouter(prefix="/fx", tags=["FX"])`; `get_fx_provider(settings: Settings = Depends(get_settings)) -> CachedPricingProvider` factory (creates `CacheRepository`, `FxInnerProvider(YFinanceProvider())`, `CachedPricingProvider`); `GET /{pair}/history` endpoint with `pair: str = Path(..., min_length=6, max_length=6, pattern=r"^[A-Za-z]{6}$")`, `from_date: date | None = Query(default=None, alias="from")`, `to_date: date | None = Query(default=None, alias="to")`; extract `base = pair[:3].upper()`, `quote = pair[3:].upper()`; call `validate_currency_code(base)` and `validate_currency_code(quote)`; raise `InvalidCurrencyPairError` if `base == quote`; resolve defaults (from: 30 days ago, to: today); validate `from <= to` (raise `InvalidTickerError` with date-range message → 422); call `fx_provider.get_price_history(pair.upper(), from_date, to_date)`; return `FxHistoryResponse(pair=pair.upper(), base_currency=base, quote_currency=quote, rates=[FxRateEntry(date=d, rate=r) for d, r in records])`; log `fx_fetch` at INFO
- [X] T023 [US3] Update `app/main.py` — import `from app.api import fx`; add `app.include_router(fx.router)`; also update `tests/conftest.py` `client_with_fx` fixture to also override `get_fx_provider` from `app.api.fx` pointing to `CachedPricingProvider(mock_fx_provider, CacheRepository(tmp_cache_dir))`

**Checkpoint**: All three user stories complete. Run full suite `pytest tests/features/currency_translation_current.feature tests/features/currency_translation_history.feature tests/features/fx_history.feature` — all green.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gate — linting, type checking, and full BDD suite confirmation.

- [X] T024 [P] Run `mypy --strict` on all new and modified modules: `app/exceptions.py`, `app/validators/currency.py`, `app/providers/fx_provider.py`, `app/services/fx_aligner.py`, `app/services/currency_service.py`, `app/models/pricing.py`, `app/api/securities.py`, `app/api/fx.py`, `app/main.py`; fix all type errors
- [X] T025 [P] Run `ruff check` on all new and modified files (same list as T024 plus test step files); fix all violations
- [X] T026 Run full BDD test suite: `python -m pytest tests/ -v`; confirm all scenarios pass (green); all three user stories validated end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001 can start immediately
- **Foundational (Phase 2)**: Requires Phase 1; T003–T006 are parallel; T007 requires T002; T008 requires T006+T007; T009 requires T008
- **US Phases (3–5)**: All require Phase 2 complete; BDD tasks within each story are parallel with each other; implementation follows BDD
- **Polish (Phase 6)**: Requires all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Requires Phase 2 — implements the `get_currency_service` factory used by US2 as well
- **US2 (P2)**: Requires US1 (reuses `get_currency_service` factory from T012; extends `get_price_history` endpoint)
- **US3 (P3)**: Requires Phase 2 only — independent of US1/US2; builds on the FX provider infrastructure

### Within Each User Story

1. BDD feature file + step definitions → confirm red
2. Implementation tasks → make scenarios green
3. Logging task → add observability
4. Verify checkpoint

### Parallel Opportunities

- T003 ‖ T004 ‖ T005 ‖ T006 (Phase 2 — all different files)
- T010 ‖ T011 (US1 BDD — different files)
- T016 ‖ T017 (US2 BDD — different files)
- T020 ‖ T021 (US3 BDD — different files)
- T024 ‖ T025 (Polish — different tools)

---

## Parallel Examples

```bash
# Phase 2 parallel tasks:
T003: Create app/validators/__init__.py
T004: Create app/validators/currency.py
T005: Create app/providers/fx_provider.py
T006: Create app/services/fx_aligner.py

# US1 BDD tasks (write both feature file and steps simultaneously):
T010: Write tests/features/currency_translation_current.feature
T011: Write tests/steps/currency_translation_current_steps.py

# US3 BDD tasks:
T020: Write tests/features/fx_history.feature
T021: Write tests/steps/fx_history_steps.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T009) — CRITICAL
3. Complete Phase 3: User Story 1 (T010–T015)
4. **STOP and VALIDATE**: `pytest tests/features/currency_translation_current.feature` — all green
5. The current price endpoint now supports currency translation

### Incremental Delivery

1. Phase 1 + 2 → Infrastructure ready
2. Phase 3 (US1) → Current price translation → MVP
3. Phase 4 (US2) → Historical price translation (most complex — alignment logic)
4. Phase 5 (US3) → Dedicated FX endpoint for diagnostics
5. Phase 6 → Quality gate pass

---

## Notes

- `[P]` tasks touch different files and have no dependency on concurrently running tasks
- BDD tasks must produce **failing** tests before implementation tasks in the same story begin
- `CurrencyService.translate_current()` needs the security provider to look up the `as_of_date` for the FX rate timestamp — use `response.as_of_date` from the `PriceResponse` to bound the FX fetch (fetch `PAIR=X` history for a 5-day window ending on `as_of_date`, take the last rate)
- `FxAligner` takes the pair name as a constructor parameter (or pass-through) so that `FxAlignmentError` can include it in the error message — adjust T006 if needed
- The `client_with_fx` fixture must override `get_currency_service` (from `app.api.securities`) AND `get_fx_provider` (from `app.api.fx`) for full test isolation — T009 covers the former, T023 adds the latter
- The `PriceHistoryResponse.currency` field is updated to the target currency by the endpoint handler after translation — `CurrencyService.translate_history()` returns the translated price list only; the endpoint sets the new `currency` value on the response
