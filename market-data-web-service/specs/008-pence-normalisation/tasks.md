# Tasks: Pence Unit Normalisation

**Input**: Design documents from `specs/008-pence-normalisation/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: BDD Gherkin `.feature` files and their step definitions are MANDATORY per the project constitution (Principle III). They MUST be written and confirmed failing before any implementation task in the same user story begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Phase 1: Setup

**Purpose**: Update API contract documentation before any implementation begins (OpenAPI-First, Principle VI).

- [X] T001 Update `openapi.yaml` — add sub-unit normalisation description to the `GET /securities/{ticker}/price` and `GET /securities/{ticker}/history` endpoint descriptions and to the `currency` and `price`/`close` field descriptions in `PriceResponse` and `PricePoint` schemas; bump version `0.1.1` → `0.1.2`

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: `SubUnitNormaliser` is required by all three user stories. It MUST be complete before any user story implementation task begins.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [X] T002 Create `app/services/minor_unit.py` — implement `SubUnitNormaliser` class; define `_MINOR_UNIT_MAP: dict[str, tuple[str, float]] = {"GBp": ("GBP", 100.0), "USd": ("USD", 100.0)}` at **module scope** (not inside a method) so new entries can be added without structural changes (FR-008); implement three methods: `is_minor_unit(currency: str) -> bool` (normalise input with `.lower()` on third char for case-insensitive lookup against map keys), `normalise(currency: str, price: float) -> tuple[str, float]` (returns unchanged tuple if not a minor unit), and `normalise_series(currency: str, series: list[tuple[date, float]]) -> tuple[str, list[tuple[date, float]]]` (divides all prices if minor unit); full type annotations; structlog debug emission when normalisation is applied

**Checkpoint**: `SubUnitNormaliser` complete — user story BDD and implementation can now begin.

---

## Phase 3: User Story 1 — Current Price Returns Whole-Unit Amount (Priority: P1) 🎯 MVP

**Goal**: `GET /securities/{ticker}/price` returns `GBP`/`USD` currency and the price ÷ 100 when the source reports `GBp`/`USd`.

**Independent Test**: Request current price of a mock ticker returning `31140 GBp`; assert response is `311.40 GBP`.

### BDD Scenarios — MUST fail before T005 begins ⚠️

- [X] T003 [P] [US1] Write `tests/features/pence_normalisation_current.feature` — five scenarios from spec.md US1: (1) `GBp` price 31140 normalised to `GBP` 311.40 for `CNKY.L`, (2) `USD` price 150.00 passed through unchanged, (3) `USd` price 15000 normalised to `USD` 150.00, (4) major-unit `GBP` price 311.40 passed through unchanged confirming `"GBP"` is not treated as a sub-unit (F2 — GBP vs GBp distinction), (5) variant casing `"gBp"` price 31140 normalised to `GBP` 311.40 confirming case-insensitive detection (FR-007/C1)
- [X] T004 [P] [US1] Implement `tests/steps/pence_normalisation_current_steps.py` — bind all five scenarios from `pence_normalisation_current.feature` using `pytest-bdd`; use `FastAPI TestClient` with `get_pricing_service` dependency override injecting a mock `PricingProvider` that returns the specified currency/price dict; assert `response.json()["currency"]` and `response.json()["price"]`; confirm all five scenarios RED before proceeding

### Implementation

- [X] T005 [US1] Modify `app/services/pricing_service.py` — add `normaliser: SubUnitNormaliser` as a third constructor parameter to `PricingService.__init__`; in `get_current_price()`, after reading `raw["currency"]` and `raw["price"]`, call `currency, price = self._normaliser.normalise(str(raw["currency"]), float(raw["price"]))` and use the normalised values when constructing `PriceResponse`
- [X] T006 [US1] Update `get_pricing_service()` factory in `app/api/securities.py` — import `SubUnitNormaliser` from `app.services.minor_unit`; pass `normaliser=SubUnitNormaliser()` as the third argument to `PricingService(provider=..., gap_fill=..., normaliser=...)`
- [X] T007 [US1] Confirm all five scenarios in `tests/features/pence_normalisation_current.feature` are GREEN by running `pytest tests/steps/pence_normalisation_current_steps.py -v`

**Checkpoint**: US1 complete — current-price endpoint returns major-unit values for GBp/USd tickers.

---

## Phase 4: User Story 2 — Price History Returns Whole-Unit Amounts (Priority: P2)

**Goal**: `GET /securities/{ticker}/history` returns all `close` values ÷ 100 and `currency` as the major-unit code when the source reports `GBp`/`USd`.

**Independent Test**: Request history for a mock ticker returning `GBp` prices; assert every `close` is the raw value ÷ 100 and the response `currency` is `GBP`.

### BDD Scenarios — MUST fail before T010 begins ⚠️

- [X] T008 [P] [US2] Write `tests/features/pence_normalisation_history.feature` — two scenarios from spec.md US2: (1) `GBp` series for `CNKY.L` normalised to `GBP` with each close ÷ 100, (2) `EUR` series passed through unchanged with each close unmodified
- [X] T009 [P] [US2] Implement `tests/steps/pence_normalisation_history_steps.py` — bind scenarios from `pence_normalisation_history.feature`; override `get_pricing_service` with a mock provider whose `get_price_history()` returns sample tuples and `get_current_price()` returns the configured currency; assert `response.json()["currency"]` and each element of `response.json()["prices"]`; confirm both scenarios RED before proceeding

### Implementation

- [X] T010 [US2] Modify `get_price_history()` in `app/services/pricing_service.py` — after gap-filling `filled`, obtain `currency` from the existing `get_current_price()` call; replace the direct `currency = c` assignment with `currency, filled = self._normaliser.normalise_series(currency, list(filled))` so the filled series prices are also scaled; use the normalised `currency` string when constructing `PriceHistoryResponse`
- [X] T011 [US2] Confirm both scenarios in `tests/features/pence_normalisation_history.feature` are GREEN by running `pytest tests/steps/pence_normalisation_history_steps.py -v`

**Checkpoint**: US2 complete — history endpoint returns major-unit values for GBp/USd tickers.

---

## Phase 5: User Story 3 — FX Conversion Applies Normalisation Before Conversion (Priority: P3)

**Goal**: When a consumer requests FX-converted prices for a pence-quoted ticker, the service divides by 100 first and then applies the FX rate — never applying the FX rate to the raw pence value.

**Independent Test**: Request pence-quoted history with `currency=USD` and a known FX rate; assert the result equals `(raw_pence ÷ 100) × fx_rate`, not `raw_pence × fx_rate`.

### BDD Scenarios — MUST fail before T014 begins ⚠️

- [X] T012 [P] [US3] Write `tests/features/pence_normalisation_fx.feature` — two scenarios from spec.md US3: (1) history for a `GBp` ticker requested with `currency=USD` and FX rate 1.25 → each close is `(raw_pence ÷ 100) × 1.25`, (2) current price for a `GBp` ticker `31140` requested with `currency=USD` and FX rate 1.25 → price `389.25`, currency `USD`
- [X] T013 [P] [US3] Implement `tests/steps/pence_normalisation_fx_steps.py` — bind scenarios from `pence_normalisation_fx.feature`; override both `get_pricing_service` (mock `GBp` provider) and `get_currency_service` (mock FX provider returning the specified rate); assert final price values and currency code; confirm both scenarios RED before proceeding

### Implementation

- [X] T014 [US3] Confirm both scenarios in `tests/features/pence_normalisation_fx.feature` are GREEN by running `pytest tests/steps/pence_normalisation_fx_steps.py -v` — no new production code should be required; the correct ordering is a natural consequence of US1+US2 placing normalisation inside `PricingService` before the API layer calls `CurrencyService`; if scenarios are not GREEN, investigate whether `PricingService.get_price_history()` is returning the normalised `currency` field correctly (required for the FX pair string `"GBPUSD"`)

**Checkpoint**: All three user stories complete and verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T015 [P] Run the full pytest suite — `pytest --tb=short -q` — and confirm all pre-existing tests still pass (zero regressions); fix any test that now fails due to the `PricingService` constructor signature change (tests using `PricingService(provider=..., gap_fill=...)` must be updated to pass `normaliser=SubUnitNormaliser()`)
- [X] T016 [P] Run `ruff check app/ tests/` and `mypy app/ tests/` — fix all violations; confirm 0 errors before marking feature complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1; BLOCKS all user story implementation tasks
- **US1 BDD (T003, T004)**: Can start after Phase 2 (SubUnitNormaliser exists to reference in steps)
- **US1 impl (T005, T006)**: MUST follow T003+T004 confirmed RED
- **US2 BDD (T008, T009)**: Can start in parallel with US1 BDD after Phase 2
- **US2 impl (T010)**: MUST follow T008+T009 confirmed RED; MUST follow T005+T006 (PricingService constructor already updated)
- **US3 BDD (T012, T013)**: Can start after T005+T006+T010 are complete (full normalisation in place)
- **US3 impl (T014)**: MUST follow T012+T013 confirmed RED
- **Polish (Phase 6)**: After all user stories complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational (T002)
- **US2 (P2)**: Depends on Foundational + US1 implementation (shares `PricingService` constructor change)
- **US3 (P3)**: Depends on US1 + US2 implementation complete (FX ordering relies on normalised currency from both)

### Parallel Opportunities

- T003 and T008 and T012 (all feature files) can be written in parallel — separate files
- T004 and T009 (step definitions for US1 and US2) can be written in parallel — separate files
- T015 and T016 (polish) can run in parallel — separate concerns

---

## Parallel Example: US1 + US2 BDD

After T002 (Foundational) is complete:

```
Parallel batch A (BDD authoring):
  Task T003: Write pence_normalisation_current.feature
  Task T008: Write pence_normalisation_history.feature

Parallel batch B (Step definitions — after batch A):
  Task T004: Implement pence_normalisation_current_steps.py (confirm RED)
  Task T009: Implement pence_normalisation_history_steps.py (confirm RED)

Sequential (implementation — after batch B confirmed RED):
  Task T005: Modify PricingService.get_current_price()
  Task T006: Update get_pricing_service() factory
  Task T010: Modify PricingService.get_price_history()
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. T001 — Update OpenAPI
2. T002 — Create SubUnitNormaliser
3. T003+T004 — BDD for current price (confirm RED)
4. T005+T006 — Modify PricingService + factory
5. T007 — Confirm GREEN
6. **VALIDATE**: `GET /securities/CNKY.L/price` returns `GBP 311.40`

### Incremental Delivery

1. Setup + Foundational → SubUnitNormaliser ready
2. US1 → current price normalised (MVP)
3. US2 → history normalised
4. US3 → FX ordering verified
5. Polish → full regression + quality gates

---

## Notes

- `[P]` tasks touch different files and have no intra-phase file conflicts
- US3 implementation (T014) may require zero new production code — the ordering is architectural; confirm before writing any code
- All test step files follow the existing `pytest-bdd` pattern: `scenarios("feature_file.feature")` at module top, `target_fixture` on `@given` steps, `app.dependency_overrides.clear()` in `@when`
- `PricingService` constructor signature change (adding `normaliser`) will break existing tests that construct `PricingService` directly — update those call sites in T015
