# Tasks: Price Series Gap Fill

**Input**: Design documents from `/specs/006-price-series-fill/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/gap_fill_behavior.md ✓, quickstart.md ✓

**Tests**: BDD Gherkin `.feature` files and their step definitions are MANDATORY per the project constitution (Principle III). They MUST be written and confirmed failing before any implementation task in the same user story begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (`US1`, `US2`, `US3`)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (OpenAPI Contract — Constitutional Prerequisite)

**Purpose**: Update the OpenAPI contract before any implementation begins (Constitution Principle VI: OpenAPI-First).

- [X] T001 Update `openapi.yaml` — add gap-fill guarantee to description of `GET /securities/{ticker}/history` (append: "All Mon–Fri business days in the requested range are guaranteed to have an entry — gaps from holidays or data outages are filled by forward/backward carry of the nearest observation.") and `GET /fx/{pair}/history` (append: "All Mon–Fri business days in the requested range are guaranteed to have a rate entry — gaps are filled by forward/backward carry of the nearest available rate.")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required by all user story phases. MUST be complete before user story BDD tests can be written.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Create `app/services/gap_fill.py` — define `GapFillService` with method `fill(self, observations: list[tuple[date, float]], from_date: date, to_date: date) -> list[tuple[date, float]]`: (1) if `observations` is empty return `[]`; (2) build `obs_map: dict[date, float] = dict(observations)` and `first_obs_price = min(observations, key=lambda x: x[0])[1]`; (3) walk a Mon–Fri grid (`current = from_date; current <= to_date; current += timedelta(days=1)`) skipping weekdays ≥ 5; (4) for each business day: if in `obs_map` → use value, update `last_price`; elif `last_price is None` → back-fill with `first_obs_price`; else → forward-fill with `last_price`; (5) add `import structlog` at top; add `logger = structlog.get_logger(__name__)`; after building the result, log `logger.info("gap_fill_applied", from_date=str(from_date), to_date=str(to_date), raw_observations=len(observations), filled_count=len(result), gaps_filled=len(result) - len(observations) if len(result) >= len(observations) else 0)`; (6) add full type annotations (`from __future__ import annotations` not needed; use stdlib `from datetime import date, timedelta`)

- [X] T003 Add `client_with_gap_fill` fixture to `tests/conftest.py` — import `GapFillService` from `app.services.gap_fill`; define `client_with_gap_fill(tmp_cache_dir, mock_inner_provider, mock_fx_provider) -> Generator[TestClient, None, None]`: import `get_pricing_service` from `app.api.securities`, `get_currency_service` from `app.api.securities`, `get_fx_provider` from `app.api.fx`; import `CacheRepository`, `CacheSettings`, `Settings`, `get_settings`, `CachedPricingProvider`, `CurrencyService`, `FxAligner`, `PricingService`; define `override_settings()` → `Settings(cache=CacheSettings(directory=tmp_cache_dir))`; define `override_service()` → `PricingService(provider=CachedPricingProvider(mock_inner_provider, CacheRepository(tmp_cache_dir)))` (NO `gap_fill` arg yet — intentional for red phase); define `override_currency_service()` → `CurrencyService(fx_provider=CachedPricingProvider(mock_fx_provider, CacheRepository(tmp_cache_dir)), aligner=FxAligner())` (NO `gap_fill` arg yet); define `override_fx_provider()` → `CachedPricingProvider(mock_fx_provider, CacheRepository(tmp_cache_dir))`; register all four overrides; yield `TestClient(app)`; clear overrides

**Checkpoint**: Foundation ready — user story BDD tests can now be authored and confirmed failing.

---

## Phase 3: User Story 1 — Forward-Fill Price Gaps Within History (Priority: P1) 🎯 MVP

**Goal**: The security price history endpoint returns an entry for every Mon–Fri business day in the requested range, filling gaps by carrying the most recent observation forward.

**Independent Test**: Send a request with a date range that spans a mid-week gap (only two dates returned by the mock) and assert the response contains all Mon–Fri dates in the range including the gap.

### BDD Scenarios for User Story 1 — MUST fail before implementation tasks below ⚠️

- [X] T004 [P] [US1] Write `tests/features/price_gap_fill.feature` with 3 US1 scenarios: (1) `Scenario: Mid-series gap is filled by forward-fill` — Given provider returns prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00; When client requests history from 2025-01-02 to 2025-01-06; Then response contains 3 entries and entry for 2025-01-03 has close 100.00 and entry for 2025-01-06 has close 102.00; (2) `Scenario: Multiple consecutive gaps are all forward-filled` — Given provider returns prices for 2025-01-02 at 100.00 and 2025-01-07 at 105.00; When client requests history from 2025-01-02 to 2025-01-07; Then response contains 4 entries and entries for 2025-01-03 and 2025-01-06 both have close 100.00; (3) `Scenario: End-of-range gap is filled forward to requested end date` — Given provider returns prices for 2025-01-02 at 100.00 and 2025-01-03 at 98.00; When client requests history from 2025-01-02 to 2025-01-07; Then response contains 4 entries and entries for 2025-01-06 and 2025-01-07 both have close 98.00; write ONLY these 3 US1 scenarios (US2 and US3 scenarios added later)

- [X] T005 [P] [US1] Write `tests/steps/price_gap_fill_steps.py` — `scenarios("price_gap_fill.feature")`; write HARD-CODED (not parametrized) given/when/then steps: `@given("the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00")` sets `mock_inner_provider.get_price_history.return_value = [(date(2025,1,2), 100.0), (date(2025,1,6), 102.0)]` and `mock_inner_provider.get_current_price.return_value = {"currency": "USD", "price": 100.0, "as_of_date": date(2025,1,6), "market_state": "CLOSED"}`; `@given("the data source has prices for 2025-01-02 at 100.00 and 2025-01-07 at 105.00")` sets `return_value = [(date(2025,1,2), 100.0), (date(2025,1,7), 105.0)]`; `@given("the data source has prices for 2025-01-02 at 100.00 and 2025-01-03 at 98.00")` sets `return_value = [(date(2025,1,2), 100.0), (date(2025,1,3), 98.0)]`; `@when("a client requests price history from 2025-01-02 to 2025-01-06", target_fixture="response")` calls `client_with_gap_fill.get("/securities/AAPL/history", params={"from": "2025-01-02", "to": "2025-01-06"})`; write separate `@when` steps for `2025-01-02 to 2025-01-07`; `@then("the response contains 3 price entries")` asserts `len(response.json()["prices"]) == 3`; `@then("the response contains 4 price entries")` asserts `len == 4`; `@then("the entry for 2025-01-03 has close price 100.00")` asserts `next(p for p in response.json()["prices"] if p["date"] == "2025-01-03")["close"] == pytest.approx(100.0)`; write equivalent then-steps for all required date/price assertions; run `pytest tests/steps/price_gap_fill_steps.py -v` and confirm all 3 scenarios fail (response only has 2 entries, not the filled count)

### Implementation for User Story 1

- [X] T006 [US1] Modify `app/services/pricing_service.py` — (a) add `from app.services.gap_fill import GapFillService` import; (b) add `gap_fill: GapFillService` as second parameter to `__init__`; store as `self._gap_fill = gap_fill`; (c) in `get_price_history()`, after `raw = self._provider.get_price_history(ticker, resolved_from, resolved_to)`, add `filled = self._gap_fill.fill(raw, resolved_from, resolved_to)`; change `prices = [PricePoint(date=d, close=v) for d, v in raw]` to use `filled`; then update THREE locations: (d) in `app/api/securities.py` update `get_pricing_service()` to `return PricingService(provider=provider, gap_fill=GapFillService())`; add `from app.services.gap_fill import GapFillService` import; (e) in `tests/conftest.py` update `client_with_gap_fill.override_service()` to `return PricingService(provider=CachedPricingProvider(mock_inner_provider, CacheRepository(tmp_cache_dir)), gap_fill=GapFillService())`; (f) in `tests/conftest.py` update `client_with_cache.override_service()` to also pass `gap_fill=GapFillService()`; add `from app.services.gap_fill import GapFillService` import at top of conftest; update `client_with_fx.override_service()` to pass `gap_fill=GapFillService()`

- [X] T007 [US1] Verify all 3 US1 BDD scenarios pass green — run `pytest tests/steps/price_gap_fill_steps.py -v` and confirm zero failures for the 3 US1 scenarios

**Checkpoint**: US1 fully functional. Security price history returns a complete Mon–Fri series with forward-fill.

---

## Phase 4: User Story 2 — Back-Fill from Requested Start Date (Priority: P2)

**Goal**: When the requested start date precedes the first available observation, the response back-fills from the first observation to the requested start date.

**Independent Test**: Send a request starting before the first mock observation and assert that entries carry the first observation's price backward to the start date.

### BDD Scenarios for User Story 2 — MUST fail before implementation tasks below ⚠️

- [X] T008 [P] [US2] Extend `tests/features/price_gap_fill.feature` — append 1 US2 scenario: `Scenario: Start of range precedes first observation — back-fill applied` — Given provider has no price before 2025-01-06 (first observation is 2025-01-06 at 100.00 and 2025-01-07 at 102.00); When client requests history from 2025-01-02 to 2025-01-07; Then response contains 4 entries and entries for 2025-01-02 and 2025-01-03 both have close 100.00

- [X] T009 [P] [US2] Extend `tests/steps/price_gap_fill_steps.py` — add `@given("the data source has no price before 2025-01-06")` step that sets `mock_inner_provider.get_price_history.return_value = [(date(2025,1,6), 100.0), (date(2025,1,7), 102.0)]` and `mock_inner_provider.get_current_price.return_value = {"currency": "USD", "price": 100.0, "as_of_date": date(2025,1,7), "market_state": "CLOSED"}`; add `@then("the entries for 2025-01-02 and 2025-01-03 both have close price 100.00")` asserting both date entries have close ≈ 100.0; run `pytest tests/steps/price_gap_fill_steps.py::test_start_of_range_precedes_first_observation_back_fill_applied -v` and confirm it passes (algorithm already handles back-fill from Phase 3)

- [X] T010 [US2] Verify US2 BDD scenario passes green — run `pytest tests/steps/price_gap_fill_steps.py -v` and confirm all 4 scenarios (3 US1 + 1 US2) pass with zero failures

**Checkpoint**: US2 fully functional. Back-fill from first observation to requested start date works correctly.

---

## Phase 5: User Story 3 — Fill Forward to Today When Source Data Is Stale (Priority: P3)

**Goal**: When the requested end date is today and the source data is T-1 or T-2 stale, the response contains an entry for today forward-filled from the last available observation.

**Independent Test**: Set mock to return T-1 price only, request history ending today, assert today's entry exists with T-1 price.

### BDD Scenarios for User Story 3 — MUST fail before implementation tasks below ⚠️

- [X] T011 [P] [US3] Extend `tests/features/price_gap_fill.feature` — append 2 US3 scenarios: (1) `Scenario: Data source only has observation for yesterday — today is forward-filled` — Given today is a business day and provider has a price for T-1 at 100.00 but no price for today; When client requests price history ending today; Then response contains an entry for today and it has close price 100.00; (2) `Scenario: Data source observation is two business days old — today is forward-filled` — Given today is a business day and provider has a price for T-2 at 100.00 but no observations for T-1 or today; When client requests price history ending today; Then response contains entries for T-1 and today and both have close price 100.00; note: these scenarios use relative day references which step definitions resolve dynamically using `date.today()`

- [X] T012 [P] [US3] Extend `tests/steps/price_gap_fill_steps.py` — add `from datetime import date, timedelta`; add helper `_last_bday(d: date) -> date` that walks back day by day until `weekday() < 5`; add `@given("today is a business day")` that calls `pytest.skip("Requires business day")` if `date.today().weekday() >= 5`; add `@given("the data source has a price for yesterday (T-1) at 100.00 but no price for today")` that computes `t1 = _last_bday(date.today() - timedelta(days=1))` and sets `mock_inner_provider.get_price_history.return_value = [(t1, 100.0)]` and sets `get_current_price` return value with `as_of_date=t1`; add `@given("the data source has a price for T-2 at 100.00 but no observations for T-1 or today")` that computes T-1 then T-2 by applying `_last_bday` twice and sets mock to `[(t2, 100.0)]`; add `@when("a client requests price history ending today", target_fixture="response")` calling `client_with_gap_fill.get("/securities/AAPL/history", params={"from": str(date.today() - timedelta(days=10)), "to": str(date.today())})`; add `@then("the response contains an entry for today")` asserting `str(date.today())` in `{p["date"] for p in response.json()["prices"]}`; add `@then("it has close price 100.00")` asserting the today entry close ≈ 100.0; add `@then("the response contains entries for T-1 and today")` and `@then("both have close price 100.00")` checking both T-1 and today entries exist with close ≈ 100.0

- [X] T013 [US3] Verify both US3 BDD scenarios pass green — run `pytest tests/steps/price_gap_fill_steps.py -v` and confirm all 6 scenarios (US1×3 + US2×1 + US3×2) pass with zero failures

**Checkpoint**: All three security price history user stories fully functional.

---

## Phase 6: FX Pair History Gap-Fill (FR-009)

**Goal**: The FX pair history endpoint returns a rate entry for every Mon–Fri business day in the requested range, using the same forward/back-fill algorithm.

**Independent Test**: Send a request to `/fx/GBPUSD/history` with a mock returning only 2 dates spanning a 3-business-day range; assert 3 rate entries are returned and the gap date carries the prior rate.

### BDD Scenarios for FX Gap-Fill — MUST fail before implementation tasks below ⚠️

- [X] T014 [P] Write `tests/features/fx_gap_fill.feature` with 1 scenario: `Scenario: FX pair history contains a rate for every business day in range` — Given FX provider returns rates for GBPUSD on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only; When client requests GBPUSD history from 2025-01-02 to 2025-01-06; Then response contains 3 rate entries and rate for 2025-01-03 is 1.25

- [X] T015 [P] Write `tests/steps/fx_gap_fill_steps.py` — `scenarios("fx_gap_fill.feature")`; write hard-coded steps: `@given("the FX provider returns rates for GBPUSD on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only")` sets `mock_fx_provider.get_price_history.return_value = [(date(2025,1,2), 1.25), (date(2025,1,6), 1.27)]`; `@when("a client requests GBPUSD history from 2025-01-02 to 2025-01-06", target_fixture="response")` calls `client_with_gap_fill.get("/fx/GBPUSD/history", params={"from": "2025-01-02", "to": "2025-01-06"})`; `@then("the response contains 3 rate entries")` asserts `len(response.json()["rates"]) == 3`; `@then("the rate for 2025-01-03 is 1.25")` finds the entry with `date == "2025-01-03"` and asserts `rate == pytest.approx(1.25)`; run `pytest tests/steps/fx_gap_fill_steps.py -v` and confirm it fails (currently only 2 entries returned)

### Implementation for FX Gap-Fill

- [X] T016 Modify `app/api/fx.py` — (a) add `from app.services.gap_fill import GapFillService` import; (b) add dependency factory `def get_fx_gap_fill_service() -> GapFillService: return GapFillService()`; (c) add `gap_fill: GapFillService = Depends(get_fx_gap_fill_service)` parameter to `get_fx_history()` endpoint function; (d) after `records = fx_provider.get_price_history(pair_upper, resolved_from, resolved_to)`, add `filled = gap_fill.fill(records, resolved_from, resolved_to)`; (e) change the `FxHistoryResponse` construction to use `filled` instead of `records`: `rates=[FxRateEntry(date=d, rate=r) for d, r in filled]`; no changes needed to conftest — the `client_with_gap_fill` fixture already overrides `get_fx_provider` so the real `GapFillService()` from `get_fx_gap_fill_service` will be used automatically

- [X] T017 Verify FX gap-fill BDD scenario passes green — run `pytest tests/steps/fx_gap_fill_steps.py -v` and confirm zero failures

**Checkpoint**: FX pair history endpoint returns complete Mon–Fri series.

---

## Phase 7: FX Conversion No-Spikes (FR-010, SC-005)

**Goal**: When converting security prices to a target currency, gap-filled FX rates are used so that missing FX data cannot introduce artificial spikes or zeros in the converted price series.

**Independent Test**: Configure mock with complete security prices Mon–Fri but FX rates with a mid-range gap; request history with currency conversion; assert every converted entry has a non-zero close and the gap date uses the gap-filled FX rate.

### BDD Scenarios for FX Conversion Gap-Fill — MUST fail before implementation tasks below ⚠️

- [X] T018 [P] Write `tests/features/gap_fill_fx_conversion.feature` with 1 scenario: `Scenario: Currency conversion uses gap-filled FX rates — no spikes from missing rates` — Given provider returns security prices for 2025-01-02 at 100.00, 2025-01-03 at 100.00, and 2025-01-06 at 100.00 (note: these are the same price to keep arithmetic simple); And FX provider returns rates for GBPUSD on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only (2025-01-03 FX rate missing); When client requests AAPL history from 2025-01-02 to 2025-01-06 with currency GBP; Then response contains 3 price entries; And the entry for 2025-01-03 has a non-zero close; And the entry for 2025-01-03 close price equals 125.00 (100.00 × 1.25 gap-filled rate)

- [X] T019 [P] Write `tests/steps/gap_fill_fx_conversion_steps.py` — `scenarios("gap_fill_fx_conversion.feature")`; hard-coded steps: `@given("the provider returns security prices for 2025-01-02 at 100.00 and 2025-01-03 at 100.00 and 2025-01-06 at 100.00")` sets `mock_inner_provider.get_price_history.return_value = [(date(2025,1,2), 100.0), (date(2025,1,3), 100.0), (date(2025,1,6), 100.0)]` and `mock_inner_provider.get_current_price.return_value = {"currency": "USD", "price": 100.0, "as_of_date": date(2025,1,6), "market_state": "CLOSED"}`; `@given("the FX provider returns rates for GBPUSD on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only")` sets `mock_fx_provider.get_price_history.return_value = [(date(2025,1,2), 1.25), (date(2025,1,6), 1.27)]`; `@when("the client requests AAPL history from 2025-01-02 to 2025-01-06 with currency GBP", target_fixture="response")` calls `client_with_gap_fill.get("/securities/AAPL/history", params={"from": "2025-01-02", "to": "2025-01-06", "currency": "GBP"})`; `@then("the response contains 3 price entries")` asserts `len == 3`; `@then("the entry for 2025-01-03 has a non-zero close")` asserts `close > 0`; `@then("the entry for 2025-01-03 close price equals 125.00")` asserts `close == pytest.approx(125.0)`; run `pytest tests/steps/gap_fill_fx_conversion_steps.py -v` and confirm it fails (currently FxAligner uses the raw 2-entry FX series and backward-fills 2025-01-03 using the 2025-01-06 rate, giving 127.00 — wrong; or raises FxAlignmentError)

### Implementation for FX Conversion Gap-Fill

- [X] T020 Modify `app/services/currency_service.py` — (a) add `from app.services.gap_fill import GapFillService` import; (b) add `gap_fill: GapFillService` as third parameter to `__init__` (after `aligner`); store as `self._gap_fill = gap_fill`; (c) in `translate_history()`, after `fx_series = self._fx_provider.get_price_history(pair, from_date, to_date)`, add `fx_series = self._gap_fill.fill(fx_series, from_date, to_date)` (replaces raw fx_series with gap-filled series before passing to aligner); then update THREE locations: (d) in `app/api/securities.py` update `get_currency_service()` to `return CurrencyService(fx_provider=fx_prov, aligner=FxAligner(), gap_fill=GapFillService())`; (e) in `tests/conftest.py` update `client_with_gap_fill.override_currency_service()` to pass `gap_fill=GapFillService()`; (f) in `tests/conftest.py` update `client_with_fx.override_currency_service()` to pass `gap_fill=GapFillService()`

- [X] T021 Verify FX conversion no-spikes BDD scenario passes green — run `pytest tests/steps/gap_fill_fx_conversion_steps.py -v` and confirm zero failures; the 2025-01-03 entry should show close ≈ 125.00 (100.00 × 1.25 forward-filled FX rate, NOT 1.27 backward-fill)

**Checkpoint**: All user stories and requirements fully functional. Gap-fill applied to security prices, FX rates (endpoint), and FX rates (internal conversion).

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T022 [P] Run `ruff check app/services/gap_fill.py app/services/pricing_service.py app/services/currency_service.py app/api/fx.py app/api/securities.py tests/conftest.py tests/steps/price_gap_fill_steps.py tests/steps/fx_gap_fill_steps.py tests/steps/gap_fill_fx_conversion_steps.py` and fix all violations (E, F, W, I, UP, ANN, B, SIM, RUF rules)

- [X] T023 [P] Run `mypy app/services/gap_fill.py app/services/pricing_service.py app/services/currency_service.py app/api/fx.py app/api/securities.py` in strict mode and fix all type errors

- [X] T024 Run full pytest suite `pytest -v` and confirm all scenarios green with zero regressions in existing features (current_price, historical_price, error_handling, cache, fx, currency translation, identifier lookup)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 completion
- **Phase 4 (US2)**: BDD tasks (T008, T009) can start in parallel with Phase 3; verification (T010) requires Phase 3 complete
- **Phase 5 (US3)**: BDD tasks (T011, T012) can start after Phase 2; verification (T013) requires Phase 3 complete
- **Phase 6 (FX endpoint)**: BDD tasks (T014, T015) can start after Phase 2; implementation (T016) can run in parallel with Phase 4/5; verification (T017) requires T016 complete
- **Phase 7 (FX conversion)**: BDD tasks (T018, T019) can start after Phase 2; implementation (T020) requires T016 complete (conftest overlap); verification (T021) requires T020 complete
- **Phase 8 (Polish)**: Depends on all previous phases complete

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 — no dependencies on other stories; MVP
- **US2 (P2)**: BDD independent; implementation is zero additional code (GapFillService already handles back-fill); depends on T007 (US1 green) to ensure algorithm works
- **US3 (P3)**: Same as US2 — BDD independent; implementation inherited

### Within Each Phase

- T004, T005 are parallel (feature file and steps file are independent files)
- T006 is sequential after T005 (modifies services that step definitions reference)
- T008, T009 are parallel
- T011, T012 are parallel
- T014, T015 are parallel
- T018, T019 are parallel
- T022, T023 are parallel (ruff vs mypy, different tools)
- T024 depends on T022 and T023

### Parallel Opportunities

- T004 + T005 (US1 BDD authoring)
- T008 + T009 (US2 BDD)
- T011 + T012 (US3 BDD)
- T014 + T015 (FX endpoint BDD)
- T018 + T019 (FX conversion BDD)
- T022 + T023 (ruff + mypy)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Update openapi.yaml
2. Complete Phase 2: GapFillService + conftest fixture
3. Write US1 BDD tests (confirm red)
4. Implement US1: modify PricingService + factories + conftest update
5. **STOP and VALIDATE**: `GET /securities/AAPL/history?from=2025-01-02&to=2025-01-06` returns 3 entries for a date range where only 2 observations exist

### Incremental Delivery

1. Phase 1 + Phase 2 → infrastructure ready
2. Phase 3 (US1) → forward-fill security prices working → MVP
3. Phase 4 (US2) → back-fill from start date working
4. Phase 5 (US3) → fill to today working
5. Phase 6 → FX endpoint returns complete series
6. Phase 7 → currency conversion uses gap-filled FX rates
7. Phase 8 → quality gates pass, full regression suite green

---

## Notes

- `GapFillService.fill()` handles all three fill cases (forward, back, to-end) in a single pass — implementing US1 simultaneously provides the infrastructure for US2 and US3
- The `client_with_gap_fill` fixture in `tests/conftest.py` intentionally starts WITHOUT gap-fill wired into the services (Phase 2, T003) so that BDD scenarios fail RED as required. The fixture is updated in T006 and T020 when service constructors are modified
- `get_current_price` on `mock_inner_provider` MUST be configured in each given step because `PricingService.get_price_history()` calls it to determine the currency code
- Weekend dates (Sat/Sun) are never in `GapFillService.fill()` output — they are skipped in the Mon–Fri grid walk (`weekday() < 5`)
- T019's "confirm red" note: the existing `FxAligner` may backward-fill 2025-01-03 using 2025-01-06's rate (1.27) when only 2 FX dates are available, making close ≈ 127.00 instead of the expected 125.00 — this is the observable red state
