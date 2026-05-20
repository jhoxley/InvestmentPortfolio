# Tasks: Local Price File Fallback

**Input**: Design documents from `specs/007-local-price-fallback/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: BDD Gherkin `.feature` files and their step definitions are MANDATORY per the project constitution (Principle III). They MUST be written and confirmed failing before any implementation task in the same user story begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: OpenAPI contract updates, config extension, and test fixtures — all prerequisites that every user story depends on.

- [X] T001 Update `openapi.yaml`: revise 503 descriptions on `/securities/{ticker}/price` and `/securities/{ticker}/history` to mention fallback file errors; update `/identifiers/{identifier}` description to document pseudo-ticker behaviour; add `FallbackConfigEntry` and `FallbackConfig` schemas under `components/schemas`; bump version to `0.1.1`
- [X] T002 Add `FallbackSettings(config_path: Path | None = None)` Pydantic model and `fallback: FallbackSettings = FallbackSettings()` field to `Settings` in `app/config.py`
- [X] T003 [P] Create CSV test fixture files in `tests/fixtures/`: `priv01_prices.csv` (two rows: `2025-01-02,100.00` and `2025-01-06,110.00`); `priv_isin_prices.csv` (one row: `2025-01-02,150.00`); `priv01_empty.csv` (headers `Date,Close` only, no data rows). Each file has headers `Date,Close`.
- [X] T004 [P] Create JSON fallback config fixture files in `tests/fixtures/`: `fallback_config.json` (PRIV01 → priv01_prices.csv, GBP, use_local_only=false); `fallback_config_isin.json` (GB00B0PRVT01 → priv_isin_prices.csv, GBP, use_local_only=true); `fallback_config_local_only.json` (PRIV01 → priv01_prices.csv, GBP, use_local_only=true); `fallback_config_missing_file.json` (PRIV01 → `/nonexistent/path.csv`, GBP). Use paths relative to the project root for csv_path values.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on — must complete before any BDD scenarios can even be wired up.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create `app/models/fallback.py` with Pydantic `FallbackEntry(BaseModel)`: fields `csv_path: Path`, `currency: str` (validated `^[A-Z]{3}$` with `@field_validator`), `date_column: str`, `price_column: str`, `use_local_only: bool = False`. Include `model_config = ConfigDict(frozen=True)`.
- [X] T006 Create `app/repositories/fallback_config.py` with `FallbackConfigRepository`: `__init__(self, config_path: Path | None)` stores the path; `lookup(self, identifier: str) -> FallbackEntry | None` re-reads the JSON file on each call (no caching), normalises the key to uppercase before comparing, returns `None` if `config_path` is `None`, if file does not exist raises `ProviderUnavailableError` with message `"Fallback config file not found: {path}"`, if identifier absent returns `None`. Parse JSON with `json.loads`; validate each entry with `FallbackEntry.model_validate`. Log at DEBUG with structlog on each lookup.
- [X] T007 Create `app/providers/local_provider.py` with `LocalPricingProvider(PricingProvider)`: `__init__(self, entry: FallbackEntry)` stores the entry. Stub both `get_price_history` and `get_current_price` to raise `NotImplementedError("not yet implemented")`. This stub is replaced in Phase 3.

**Checkpoint**: Foundation complete — BDD test files can now be written (they import these new modules).

---

## Phase 3: User Story 1 — Price History Fallback (Priority: P1) 🎯 MVP

**Goal**: Price history and identifier resolution requests for configured fallback tickers serve data from the local CSV file, with gap-fill applied, cache bypassed, and ISIN/CUSIP/SEDOL identifiers resolvable as pseudo-tickers.

**Independent Test**: Configure `PRIV01` in `fallback_config.json`, request `GET /securities/PRIV01/history?from=2025-01-02&to=2025-01-06`. Verify 200 response with 3 gap-filled entries (Mon–Fri, Jan 2/3/6), currency GBP, data from CSV.

### BDD Scenarios for User Story 1 (MANDATORY — write and confirm failing FIRST) ⚠️

> **MUST fail before any implementation task below begins (Red-Green-Refactor)**

- [X] T008 [US1] Write `tests/features/local_price_fallback_history.feature` with all 5 US1 Gherkin scenarios from `spec.md` verbatim: (1) price history served from local fallback; (2) gap-fill applied to local data; (3) unknown ticker with no fallback → 404; (4) ISIN-keyed fallback entry served via pseudo-ticker; (5) `use_local_only` bypasses primary source. Use `Feature: Local price file fallback — price history`.
- [X] T009 [US1] Implement step definitions in `tests/steps/local_price_fallback_history_steps.py`: import `scenarios("local_price_fallback_history.feature")`; wire all `@given`, `@when`, `@then` steps using `MagicMock` for the inner provider (configured to raise `DataNotFoundError("PRIV01")`), `FallbackConfigRepository` pointing at `tests/fixtures/fallback_config.json`, `FallbackPricingProvider`, and `PricingService`. Confirm all 5 scenarios are RED (failing with `NotImplementedError` or import errors) before proceeding.
- [ ] T010 [US1] Add fallback test fixtures to `tests/conftest.py`: add `client_with_fallback(tmp_path)` pytest fixture that builds a `TestClient` overriding `get_pricing_service` with a `PricingService(provider=FallbackPricingProvider(inner=mock_yfinance_raises_not_found, fallback_repo=FallbackConfigRepository(Path("tests/fixtures/fallback_config.json"))), gap_fill=GapFillService())` and overriding `get_identifier_service` with `IdentifierService(provider=FallbackIdentifierProvider(inner=mock_identifier_raises_not_found, fallback_repo=FallbackConfigRepository(Path("tests/fixtures/fallback_config_isin.json"))))`. Expose `mock_yfinance` and `mock_identifier` as attributes for assertion in steps.

### Implementation for User Story 1

- [ ] T011 [US1] Implement `LocalPricingProvider.get_price_history` in `app/providers/local_provider.py`: use `pd.read_csv(entry.csv_path)` — raise `ProviderUnavailableError(f"Fallback CSV file not found: {entry.csv_path}")` if `FileNotFoundError`; raise `ProviderUnavailableError` if the configured `date_column` or `price_column` is absent from the CSV headers; raise `DataNotFoundError(ticker)` if the DataFrame has zero rows after filtering `price > 0`; parse each date cell with `dateutil.parser.parse(cell).date()`; skip rows where price ≤ 0; return `sorted(list[tuple[date, float]])`. Add structlog DEBUG log on read start and INFO log on success with row count.
- [ ] T012 [US1] Implement `LocalPricingProvider.get_current_price` in `app/providers/local_provider.py`: call `get_price_history(ticker, date(2000,1,1), date.today())` to obtain all rows; take the last entry `(as_of_date, price)`; return `{"price": price, "as_of_date": as_of_date, "currency": self._entry.currency, "market_state": None}`. Propagate `DataNotFoundError` and `ProviderUnavailableError` unchanged.
- [ ] T013 [US1] Create `app/providers/fallback_provider.py` with `FallbackPricingProvider(PricingProvider)`: `__init__(self, inner: PricingProvider, fallback_repo: FallbackConfigRepository)`; implement `get_price_history`: lookup entry → if `None` delegate to inner; if `use_local_only` go straight to `LocalPricingProvider(entry).get_price_history()`; otherwise try inner, catch `DataNotFoundError` only and delegate to `LocalPricingProvider(entry).get_price_history()` — let `ProviderUnavailableError` propagate unchanged. Log `event="fallback_triggered"` at INFO on interception; `event="local_only_bypass"` at INFO when `use_local_only` is set. Implement `get_current_price` with the identical intercept pattern.
- [ ] T014 [US1] Update `get_pricing_service()` in `app/api/securities.py`: import `FallbackPricingProvider` and `FallbackConfigRepository`; construct `fallback_repo = FallbackConfigRepository(settings.fallback.config_path)`; wrap existing `CachedPricingProvider(YFinanceProvider(), repo)` as `yf_provider`; build `provider = FallbackPricingProvider(inner=yf_provider, fallback_repo=fallback_repo)`; pass `provider` to `PricingService`. Keep `get_currency_service()` unchanged.
- [ ] T015 [US1] Add `FallbackIdentifierProvider(IdentifierProvider)` class to `app/providers/identifier_provider.py`: `__init__(self, inner: IdentifierProvider, fallback_repo: FallbackConfigRepository)`; `lookup_ticker(self, identifier: str, identifier_type: str) -> dict[str, object]`: call `self._inner.lookup_ticker(identifier, identifier_type)`; catch `IdentifierNotFoundError` only; on catch, call `self._fallback_repo.lookup(identifier)` — if entry found return `{"ticker": identifier, "security_name": "", "exchange": ""}` and log `event="identifier_fallback_resolved"` at INFO; if entry not found re-raise the original `IdentifierNotFoundError`. Let `ProviderUnavailableError` propagate unchanged.
- [ ] T016 [US1] Update `get_identifier_service()` in `app/api/identifiers.py`: inject `settings: Settings = Depends(get_settings)`; construct `fallback_repo = FallbackConfigRepository(settings.fallback.config_path)`; build `provider = FallbackIdentifierProvider(inner=YFinanceIdentifierProvider(), fallback_repo=fallback_repo)`; return `IdentifierService(provider=provider)`.

**Checkpoint**: All 5 US1 BDD scenarios should now be GREEN. Run `pytest tests/steps/local_price_fallback_history_steps.py -v`.

---

## Phase 4: User Story 2 — Current Price Fallback (Priority: P2)

**Goal**: Current price requests for configured fallback tickers serve the most recent CSV entry as the current price, with `market_status="closed"`.

**Independent Test**: Configure `PRIV01` in `fallback_config.json`, request `GET /securities/PRIV01/price`. Verify 200 with `price=110.00`, `currency="GBP"`, `market_status="closed"`, `as_of_date="2025-01-06"`.

### BDD Scenarios for User Story 2 (MANDATORY — write and confirm failing FIRST) ⚠️

> **MUST fail before any implementation task below begins (Red-Green-Refactor)**

- [ ] T017 [P] [US2] Write `tests/features/local_price_fallback_current.feature` with the 2 US2 Gherkin scenarios from `spec.md` verbatim: (1) current price served from local fallback file; (2) current price fallback ticker with no configuration → 404. Use `Feature: Local price file fallback — current price`.
- [ ] T018 [P] [US2] Implement step definitions in `tests/steps/local_price_fallback_current_steps.py`: import `scenarios("local_price_fallback_current.feature")`; reuse `client_with_fallback` fixture from conftest; wire all steps (mock inner provider, assert price=110.00, currency="GBP", market_status="closed", as_of_date="2025-01-06"). Confirm both scenarios are RED before proceeding to implementation below.

### Implementation for User Story 2

No new implementation tasks required — `LocalPricingProvider.get_current_price` and `FallbackPricingProvider.get_current_price` were fully implemented in Phase 3 (T012 and T013). Verify both US2 scenarios turn GREEN after confirming RED.

**Checkpoint**: Both US2 BDD scenarios should be GREEN. Run `pytest tests/steps/local_price_fallback_current_steps.py -v`.

---

## Phase 5: User Story 3 — FX Currency Conversion (Priority: P3)

**Goal**: Local file prices are converted to the requested target currency using the same FX pipeline as primary-source prices.

**Independent Test**: Configure `PRIV01` (GBP), mock GBPUSD rate at 1.25, request `GET /securities/PRIV01/history?from=2025-01-02&to=2025-01-02&currency=USD`. Verify `price=125.00`, `currency="USD"`.

### BDD Scenarios for User Story 3 (MANDATORY — write and confirm failing FIRST) ⚠️

> **MUST fail before any implementation task below begins (Red-Green-Refactor)**

- [ ] T019 [P] [US3] Write `tests/features/local_price_fallback_fx.feature` with the 1 US3 Gherkin scenario from `spec.md` verbatim: local fallback prices converted to requested target currency (GBP→USD at 1.25, price 100.00→125.00). Use `Feature: Local price file fallback — FX currency conversion`.
- [ ] T020 [P] [US3] Implement step definitions in `tests/steps/local_price_fallback_fx_steps.py`: import `scenarios("local_price_fallback_fx.feature")`; use `client_with_fallback` fixture extended to also mock the FX provider returning `[(date(2025,1,2), 1.25)]` for GBPUSD; override `get_currency_service` with a real `CurrencyService` that uses the mocked FX provider; assert response `prices[0]["close"] == 125.00` and `prices[0]["fx_rate"] == 1.25`. Confirm scenario is RED before proceeding.

### Implementation for User Story 3

No new implementation tasks required — `FallbackPricingProvider` returns `list[tuple[date, float]]` identical in structure to YFinance output; the existing `CurrencyService` and `FxAligner` pipeline in `PricingService.get_price_history` handles FX conversion transparently. Verify the US3 scenario turns GREEN.

**Checkpoint**: US3 BDD scenario should be GREEN. Run `pytest tests/steps/local_price_fallback_fx_steps.py -v`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge case BDD coverage, logging completeness, and quality gate passage.

- [ ] T021 [P] Write `tests/features/local_price_fallback_edge.feature` with edge case scenarios: (1) missing CSV file returns 503 with descriptive message; (2) empty CSV file (headers only) returns 404. Implement step definitions in `tests/steps/local_price_fallback_edge_steps.py`. Use `client_with_fallback` fixture variant pointing to `fallback_config_missing_file.json` and `fallback_config.json` with the empty CSV path. Confirm RED then verify GREEN after no additional implementation is needed (error handling already in T011/T013).
- [ ] T022 Add structlog structured logging to `app/repositories/fallback_config.py`: DEBUG on successful config read including `entry_count`; ERROR on file not found. Add to `app/providers/local_provider.py`: DEBUG on CSV read start (ticker, path), DEBUG on read success (ticker, path, row_count), ERROR on file not found, WARNING on empty CSV.
- [ ] T023 [P] Run `ruff check app/models/fallback.py app/repositories/fallback_config.py app/providers/local_provider.py app/providers/fallback_provider.py app/api/securities.py app/api/identifiers.py app/config.py` — fix all violations (E501 line length, I001 imports, RUF rules). Run `ruff format` on the same files.
- [ ] T024 [P] Run `mypy --strict app/models/fallback.py app/repositories/fallback_config.py app/providers/local_provider.py app/providers/fallback_provider.py app/api/securities.py app/api/identifiers.py` — fix all type errors. Ensure all functions have complete annotations including return types.
- [ ] T025 Run the full pytest BDD suite: `python -m pytest tests/ -v` — all scenarios green, zero failures, zero ruff/mypy violations.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001–T004 can start immediately; T003 and T004 are parallel
- **Foundational (Phase 2)**: Depends on Phase 1 completion — T005 → T006 → T007 (sequential; each builds on the previous)
- **US1 (Phase 3)**: Depends on Phase 2 completion — T008/T009/T010 parallel; T011/T012 parallel; T013 after T011+T012; T014 after T013; T015 after T014; T016 after T015
- **US2 (Phase 4)**: Depends on Phase 3 completion — T017/T018 parallel (then verify GREEN)
- **US3 (Phase 5)**: Depends on Phase 3 completion — T019/T020 parallel (then verify GREEN); can run in parallel with US2
- **Polish (Phase 6)**: Depends on all user story phases complete — T021/T023/T024 parallel; T022 after T021; T025 last

### User Story Dependencies

- **US1 (P1)**: Core infrastructure phase — US2 and US3 both depend on US1's provider implementations
- **US2 (P2)**: Depends on US1 provider implementations; independently testable via current price endpoint
- **US3 (P3)**: Depends on US1 provider implementations; independently testable via currency parameter

### Within US1

```
T008 (feature file) ──┐
T009 (steps, RED)  ──┤── must all be RED ──▶ T011 (LocalPricingProvider.get_price_history)
T010 (conftest)    ──┘                         │
                                               T012 (LocalPricingProvider.get_current_price) ─┐
                                               T013 (FallbackPricingProvider)                 ─┤──▶ T014 (securities.py)
                                               T015 (FallbackIdentifierProvider)              ─┘         │
                                                                                                          T016 (identifiers.py)
```

### Parallel Opportunities

| Phase | Parallel tasks |
|-------|---------------|
| Phase 1 | T003 ‖ T004 |
| Phase 3 BDD | T008 ‖ T009 ‖ T010 |
| Phase 3 Impl | T011 ‖ T012 (different methods in same file, but no cross-dependency) |
| Phase 4 | T017 ‖ T018 |
| Phase 5 | T019 ‖ T020; US2 ‖ US3 |
| Phase 6 | T021 ‖ T023 ‖ T024 |

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T007)
3. Complete Phase 3: US1 (T008–T016)
4. **STOP and VALIDATE**: `pytest tests/steps/local_price_fallback_history_steps.py -v` — all 5 scenarios green
5. Deploy/demo: fallback price history and identifier resolution working

### Incremental Delivery

1. Setup + Foundational → Core infrastructure ready
2. US1 complete → Fallback price history + ISIN resolution working (MVP)
3. US2 complete → Fallback current price working
4. US3 complete → FX conversion on fallback data working
5. Polish → All edge cases, quality gates, full suite green

---

## Notes

- `LocalPricingProvider` uses `pandas.read_csv()` — already installed; no new dependency
- `dateutil.parser.parse()` is already installed as a transitive dependency of `yfinance`
- `FallbackConfigRepository` re-reads the JSON file on every `lookup()` call — this is intentional for hot-reload (SC-005)
- `FallbackPricingProvider` must NOT catch `ProviderUnavailableError` from the inner provider — only `DataNotFoundError`
- CSV `csv_path` values in test fixture JSON should be relative paths from the project root (e.g., `"tests/fixtures/priv01_prices.csv"`) so tests are portable
- The `get_current_price` implementation in `LocalPricingProvider` calls `get_price_history` with a wide date range (`date(2000,1,1)` to `date.today()`) to obtain all rows — this is intentional; the CSV is small
- `market_status` for local file data is always `"closed"` (static historical data)
- `PricingService.get_price_history()` calls `self._provider.get_current_price()` internally to detect currency — `FallbackPricingProvider.get_current_price()` must be implemented for US1 to fully pass, even though the current price endpoint test is in US2
