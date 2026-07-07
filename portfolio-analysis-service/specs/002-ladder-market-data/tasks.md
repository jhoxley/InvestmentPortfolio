---
description: "Task list for Ladder Market Data Enrichment feature"
---

# Tasks: Ladder Market Data Enrichment

**Input**: Design documents from `/specs/002-ladder-market-data/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅

**Tests**: Required — Constitution Principle I mandates TDD with BDD/Gherkin. Test tasks appear
before their corresponding implementation tasks in every phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]–[US4])
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization and configuration scaffolding — no dependencies, start immediately.

- [X] T001 [P] Update `pyproject.toml`: move `httpx>=0.27` from `[project.optional-dependencies].dev` into `[project.dependencies]` (it is now a runtime dependency used to call market-data-web-service, not just a test dependency); regenerate `requirements.txt` by pinning the exact installed version (`pip freeze` in the project venv)
- [X] T002 [P] Add a `market_data_service` section (`base_url: http://127.0.0.1:8001`, `timeout_seconds: 30`) and an `identifier_mapping` section (`path: C:/Users/jhoxl/OneDrive/Investments/InvestmentDataStatic.json`) to `config.yaml`
- [X] T003 [P] Extend `app/config.py`: add `MarketDataServiceSettings(base_url: str = "http://127.0.0.1:8001", timeout_seconds: float = 30.0)` and `IdentifierMappingSettings(path: Path | None = None)` Pydantic models; add `market_data_service: MarketDataServiceSettings` and `identifier_mapping: IdentifierMappingSettings` fields to the top-level `Settings` model, matching the existing `DataSettings` pattern

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required by every user story. No user story work begins until this phase is complete.

**⚠️ CRITICAL**: All user story phases depend on this phase being fully complete.

- [X] T004 [P] Create `app/models/market_data.py` with `IdentifierMappingEntry(name: str, isin: str | None = None, ticker: str | None = None)` and `PriceHistoryPoint(date: date, close: float)` Pydantic models (per data-model.md)
- [X] T005 [P] Add `IdentifierMappingError(sub_accounts: list[str])`, `PriceCoverageError(problems: dict[str, list[date]])`, and `MarketDataServiceError(sub_account: str, detail: str)` exception classes to `app/exceptions.py`; each builds a descriptive `.message` naming every affected sub-account (and date, where applicable), following the existing `EmptyDateRangeError` pattern of pre-formatting a human-readable message in `__init__`
- [X] T006 [P] In `app/models/ladder.py`, change `IngestionSummary.status` from `Literal["created", "unchanged"]` to `Literal["created", "refreshed"]` and update its `Field(description=...)` text to explain the new "refreshed" meaning (per research.md §6 — this is a rename, not an additive value; there is no longer a pure no-op path)
- [X] T007 Create `app/repositories/identifier_mapping_repository.py` — `IdentifierMappingRepository(mapping_path: Path | None)` that loads the configured JSON array once (lazily, on first `lookup()` call) into a `dict[str, IdentifierMappingEntry]` keyed by exact-match `name`; `lookup(sub_account: str) -> IdentifierMappingEntry | None`; raise a clear, descriptive error if `mapping_path` is `None`, the file does not exist, or it is not valid JSON; log a structlog event for load failures and for lookup misses (e.g. `identifier_mapping_load_error`, `identifier_mapping_miss`), following the existing `logger.bind(...)` pattern in `ingestion_service.py` (Constitution IV). Depends on T004 for the `IdentifierMappingEntry` import — do not start before T004 is written
- [X] T008 Create `app/clients/market_data_client.py` — a `MarketDataClient` `Protocol` with `get_price_history(self, identifier: str, from_date: date, to_date: date, currency: str) -> list[PriceHistoryPoint]`, and an `HttpMarketDataClient` implementation using `httpx.Client(base_url=settings.market_data_service.base_url, timeout=settings.market_data_service.timeout_seconds)` calling `GET /securities/{identifier}/history?from={from_date}&to={to_date}&currency={currency}`; parse the `PriceHistoryResponse.prices` array into `list[PriceHistoryPoint]`; raise `MarketDataServiceError` on any non-2xx response, timeout, or connection error; accept an optional `transport=` constructor argument so tests can inject `httpx.MockTransport`; log a structlog event for every outbound request (identifier, from_date, to_date, duration_ms, outcome) and for any `MarketDataServiceError` raised (Constitution IV). Depends on T004 for the `PriceHistoryPoint` import — do not start before T004 is written
- [X] T009 [P] Create a shared `fake_market_data_service` fixture in `tests/conftest.py` — an `httpx.MockTransport`-backed fake (usable as the `transport=` argument to `HttpMarketDataClient`, per T008) that records every request it receives (URL path, `from`/`to`/`currency` query params) and returns configurable canned price-history JSON per identifier; all of US1–US4's step files (T017, T019, T024, T026) MUST import and configure this one fixture rather than each building their own fake client, to avoid duplicated/drifting fake-client logic across step files

**Checkpoint**: Foundation complete — all user story phases may now proceed. Note: T004 must land before T007/T008 begin; T005, T006, and T009 have no such ordering constraint.

---

## Phase 3: User Story 1 — View a Priced Position Ladder (Priority: P1) 🎯 MVP

**Goal**: Every row of an ingested (or refreshed) ladder carries `price`, `market_value`, and `portfolio_weight`; Cash is priced at 1.0 GBP; weights sum to 1.0 per date.

**Independent Test**: Ingest a ledger with an equity sub-account and Cash; verify every stored row has a price/market_value/portfolio_weight, Cash's price is 1.0, and per-date weights sum to 1.0. Re-submit the same file; verify `status: "refreshed"` and recomputed values.

### Tests for User Story 1 ⚠️ Write and verify FAILING before implementing

- [X] T010 [P] [US1] Write Gherkin feature file `tests/features/ladder_pricing.feature` with the US1 scenarios from `spec.md`: "Ingested ladder rows are enriched with price, market value, and weight", "Portfolio weight sums to 1.0 on every date", "Re-submitting an unchanged ledger reports a refreshed status" — use exact Gherkin from spec; tag each with `@us1`
- [X] T011 [P] [US1] Write failing unit tests in `tests/unit/test_pricing_enrichment_service.py`: `test_cash_priced_at_one_gbp_no_mapping_lookup()`, `test_market_value_equals_price_times_quantity()`, `test_portfolio_weight_sums_to_one_per_date()` (use `pytest.approx(1.0, abs=0.0001)`), `test_portfolio_weight_is_zero_when_total_market_value_is_zero()`, `test_ticker_preferred_over_isin_when_both_present()`; import `PricingEnrichmentService` from `app/services/pricing_enrichment_service.py` (fails at import until T013)

### Implementation for User Story 1

- [X] T012 [US1] Add `LadderRepository.read_ladder_df(account_name: str) -> pd.DataFrame` to `app/repositories/ladder_repository.py` — reads back the stored `ladder.xlsx` via `pandas.read_excel` and returns only the base columns `[date, sub_account, book_cost, quantity, total_income]` (dropping `price`/`market_value`/`portfolio_weight` if already present), for re-enrichment on the refresh path; raise `FileNotFoundError` if no ladder is stored, matching `read_xlsx()`'s existing contract. Independent of T011 (different file); can run in parallel with it
- [X] T013 [US1] Implement `app/services/pricing_enrichment_service.py` — `PricingEnrichmentService(mapping_repo: IdentifierMappingRepository, market_data_client: MarketDataClient)` with `enrich(ladder_df: pd.DataFrame) -> pd.DataFrame`: for the `"Cash"` group, set `price = 1.0` for every row with no mapping lookup and no client call; for every other distinct `sub_account`, resolve its identifier via `mapping_repo.lookup()` (prefer `ticker`, fall back to `isin`), compute that sub-account's `min(date)`/`max(date)` within the input, call `market_data_client.get_price_history(identifier, min_date, max_date, "GBP")` exactly once, and merge the returned closes onto that sub-account's rows by `date`; compute `market_value = price * quantity` for every row; after all sub-accounts are priced, group by `date` and compute `portfolio_weight = market_value / sum(market_value)` for that date, using `0` when the date's total is `0`; return the input DataFrame with `price`, `market_value`, `portfolio_weight` appended as trailing columns; bind and log a structlog event per sub-account processed (sub_account, identifier, date range, outcome) and a summary event for the whole `enrich()` call (row_count, sub_account_count), following the existing `logger.bind(...)` pattern (Constitution IV); depends on T004, T007, T008 (Phase 2) and must run **after** T011 exists so its tests are red before this task turns them green — do NOT start this task in parallel with T011
- [X] T014 [US1] Update `app/services/ingestion_service.py`: inject `PricingEnrichmentService` into `IngestionService.__init__`; on the new-account path, call `enrich()` on the expanded ladder DataFrame before `repository.write()`; on the checksum-match path, replace the immediate early-return with: read the existing ladder via `repository.read_ladder_df()`, call `enrich()` on it, `repository.write()` the refreshed result, update `meta.ingested_at`, and return `IngestionSummary(status="refreshed", ...)`; `enrich()` is called strictly before any `repository.write()` call on both paths, so a raised enrichment error leaves the previously stored ladder (if any) completely untouched
- [X] T015 [US1] Fix the now-stale feature-001 regression: in `tests/features/ingest_ladder.feature`, rewrite the `@us3` "Re-submitting the same file is a no-op" scenario (from feature 001) to reflect that checksum-match now triggers a refresh rather than a pure no-op — assert `status: "refreshed"` and that price/market_value/portfolio_weight are recomputed, and drop the old "stored XLSX file is unchanged" assertion (the file's mtime now legitimately changes on every checksum-match re-submission); update the corresponding steps in `tests/steps/ingest_ladder_steps.py` (any `status == "unchanged"` or mtime-unchanged assertions) to match; this resolves the direct contradiction between feature 002's FR-013 and feature 001's original FR-007 idempotency guarantee (see spec.md Assumptions for the supersession note)
- [X] T016 [US1] Wire dependency injection in `app/api/ladder.py`: add `_get_identifier_mapping_repository(settings: Settings = Depends(get_settings))`, `_get_market_data_client(settings: Settings = Depends(get_settings))`, and `_get_pricing_enrichment_service(...)` FastAPI provider functions; update `_get_ingestion_service` to construct `IngestionService` with the new `PricingEnrichmentService` dependency
- [X] T017 [US1] Write BDD step implementations in `tests/steps/ladder_pricing_steps.py` for `ladder_pricing.feature` — use the shared `fake_market_data_service` fixture from `tests/conftest.py` (T009), configured to return deterministic GBP closes for a test ticker; assert enriched XLSX columns via `pandas.read_excel`, Cash's price of 1.0, per-date weight sums via `pytest.approx`, and the `status: "refreshed"` response plus recomputed values on re-submission; run `pytest tests/features/ladder_pricing.feature -m us1` to confirm all green

**Checkpoint**: US1 complete — priced ladder fully functional and BDD-tested independently.

---

## Phase 4: User Story 2 — Efficient Batch Price Retrieval Per Sub-Account (Priority: P1)

**Goal**: Exactly one price-history request is made per distinct non-Cash sub-account, covering its full active date range — never one request per date.

**Independent Test**: Ingest a ledger with a sub-account active across 60 business days; verify exactly one price-history request was made for it, spanning its full range.

**Note**: The batching behavior is inherent to `PricingEnrichmentService`'s design in T013 (one `get_price_history()` call per distinct sub-account group, never per row/date) — there is no separate "per-date" code path to replace. This phase adds dedicated call-count verification.

### Tests for User Story 2 ⚠️ Write and verify FAILING before implementing

- [X] T018 [P] [US2] Write Gherkin feature file `tests/features/batch_pricing.feature` with the US2 scenarios from spec: "One batch request per distinct non-Cash sub-account", "Multiple sub-accounts each get their own single batch request"; tag each with `@us2`

### Implementation for User Story 2

- [X] T019 [US2] Write BDD step implementations in `tests/steps/batch_pricing_steps.py` — use the shared `fake_market_data_service` fixture from `tests/conftest.py` (T009) to assert exact call counts per sub-account, that each call's date range matches that sub-account's active range, and that zero calls are made for `"Cash"`; run `pytest tests/features/batch_pricing.feature -m us2` to confirm all green

**Checkpoint**: US2 complete — batching behavior independently verified.

---

## Phase 5: User Story 3 — Fail Fast When GBP Prices Are Incomplete (Priority: P1)

**Goal**: Any unresolvable sub-account identifier or any business-day price gap aborts ingestion with a single error naming every affected sub-account and date; no ladder is written or overwritten.

**Independent Test**: Ingest a ledger where one sub-account has no mapping entry and another has a gap in its returned prices; verify a single 422 response names both problems and no ladder file changes.

### Tests for User Story 3 ⚠️ Write and verify FAILING before implementing

- [X] T020 [P] [US3] Write Gherkin feature file `tests/features/pricing_errors.feature` with all three US3 scenarios from spec: "Missing GBP price on a business day blocks ingestion", "Missing identifier mapping blocks ingestion", "Multiple simultaneous problems are all reported together"; tag each with `@us3`
- [X] T021 [P] [US3] Write failing unit tests in `tests/unit/test_pricing_enrichment_service.py` (extend the file from T011): `test_missing_mapping_entry_raises_identifier_mapping_error()`, `test_mapping_entry_with_neither_isin_nor_ticker_raises()`, `test_gap_in_returned_prices_raises_price_coverage_error()`, `test_multiple_sub_account_problems_reported_in_one_error()` (asserts both an `IdentifierMappingError`-worthy sub-account and a `PriceCoverageError`-worthy sub-account are named together, not just the first one found)

### Implementation for User Story 3

- [X] T022 [US3] Extend `PricingEnrichmentService.enrich()` (`app/services/pricing_enrichment_service.py`, from T013) to collect problems across *all* sub-accounts before raising — for each distinct non-Cash sub-account: if no usable mapping entry, record it for `IdentifierMappingError`; otherwise, after fetching its price history, compare every business day present in the ladder for that sub-account against the dates returned and record any missing dates for `PriceCoverageError`; after processing every sub-account, if either collection is non-empty, raise the corresponding error (or both, if both are non-empty) naming every affected sub-account/date in one place — never raise on the first problem found; log a structlog warning event for every collected mapping/coverage problem before raising, naming the sub-account(s)/date(s) (Constitution IV). Must run after T021 (makes its tests pass); modifies the same file as T013
- [X] T023 [US3] Register exception handlers in `app/main.py` for `IdentifierMappingError` (422), `PriceCoverageError` (422), and `MarketDataServiceError` (502), each built via the existing `_problem()` helper and returning an RFC 7807 `ProblemDetail`, following the pattern of the existing `InvalidAccountNameError`/`SchemaValidationError` handlers
- [X] T024 [US3] Write BDD step implementations in `tests/steps/pricing_errors_steps.py` for `pricing_errors.feature` — configure the shared `fake_market_data_service` fixture (T009) and the mapping repository per scenario to simulate a missing mapping entry, a date gap, and both simultaneously; assert the 422 response, that `ProblemDetail.detail` names every affected sub-account and date together, and that no ladder file was written or changed (compare stored file state before/after); run `pytest tests/features/pricing_errors.feature -m us3` to confirm all green

**Checkpoint**: US3 complete — fail-fast behavior independently verified.

---

## Phase 6: User Story 4 — Configure Market Data Service Location and Identifier Mapping (Priority: P2)

**Goal**: Market data service host/port and identifier mapping file path are read from configuration; `run_end_to_end.ps1` wires the two running services together automatically.

**Independent Test**: Change the configured `market_data_service.base_url` and `identifier_mapping.path` to alternate valid values; confirm ingestion uses the new location and mapping.

### Tests for User Story 4 ⚠️ Write and verify FAILING before implementing

- [X] T025 [P] [US4] Write Gherkin feature file `tests/features/market_data_config.feature` with all three US4 scenarios from spec: "Market data service location is read from configuration", "Identifier mapping file path is read from configuration", "End-to-end script wires the two services together"; tag each with `@us4`

### Implementation for User Story 4

- [X] T026 [US4] Write BDD step implementations in `tests/steps/market_data_config_steps.py` — override `get_settings()` in the test fixture with an alternate `market_data_service.base_url` and `identifier_mapping.path`; reuse the shared `fake_market_data_service` fixture (T009), pointed at the alternate base URL, to assert `HttpMarketDataClient` actually issues requests against it, and assert `IdentifierMappingRepository` reads from the alternate path; for the end-to-end wiring scenario, assert (via a lightweight parse of `run_end_to_end.ps1`, or a documented manual verification step per T027) that the script's `$MarketDataHost`/`$MarketDataPort` values are the ones written into portfolio-analysis-service's config; run `pytest tests/features/market_data_config.feature -m us4` to confirm all green
- [X] T027 [US4] Update `run_end_to_end.ps1` (repo root) Phase 2: replace the commented-out `market_data_service` placeholder block inside `$analysisDefaultConfig` with a real, uncommented block populated from the script's existing `$MarketDataHost`/`$MarketDataPort` variables, and add an `identifier_mapping.path` entry pointing at `Join-Path $InvestmentsDir "InvestmentDataStatic.json"`; extend the `Assert-ConfigYaml` call for portfolio-analysis-service to include `"market_data_service:"` and `"identifier_mapping:"` in `-ExpectedKeys`; update the `Write-Log` lines that currently describe the market-data integration as "not yet wired"

**Checkpoint**: All user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Code quality gates, contract sync, and end-to-end validation.

- [X] T028 [P] Run `ruff check app/ tests/` and `ruff format app/ tests/`; fix all reported issues including any `D` (pydocstyle) violations on the new modules (Constitution III); run `mypy --strict app/`; resolve all type errors; confirm zero errors in all three checks
- [X] T029 [P] Verify OpenAPI spec accuracy: start the server, fetch `http://localhost:8000/openapi.json`, compare against `specs/002-ladder-market-data/contracts/openapi.yaml` (particularly the `IngestionSummary.status` enum and the new 422/502 responses); update the project-root `openapi.yaml` if any discrepancies exist
- [X] T030 Run `quickstart.md` validation end-to-end against both live services: ingest a real ledger, verify the enriched XLSX download, re-submit the same file and verify the `refreshed` status, and trigger each documented failure mode — including the unreachable-market-data-service case, simulated by temporarily stopping the market-data-service process (or by pointing `market_data_service.base_url` at a closed port) — record and fix any discrepancies against `quickstart.md`
- [X] T031 [P] Add a test to `tests/unit/test_performance.py` measuring enrichment call volume: ingest a synthetic ladder with several distinct non-Cash sub-accounts against the fake market-data client and assert the number of simulated HTTP calls equals the number of distinct non-Cash sub-accounts (SC-003), independent of how many business days the ladder spans

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; all tasks parallelisable
- **Foundational (Phase 2)**: Depends on Phase 1 completion — blocks all user stories. Within Phase 2, T004 must land before T007/T008 start (they import its models); T009 is independent of T004/T007/T008
- **US1 (Phase 3)**: Depends on Phase 2 — MVP delivery point
- **US2 (Phase 4)**: Depends on Phase 3 (T013) — verifies batching behavior already built into `PricingEnrichmentService`'s design; cannot be meaningfully tested before US1's core service exists
- **US3 (Phase 5)**: Depends on Phase 3 (T013) — extends the same service with failure-detection logic
- **US4 (Phase 6)**: Depends on Phase 2 only (config + client/repo classes) — may proceed in parallel with US1/US2/US3
- **Polish (Phase 7)**: Depends on all desired user story phases being complete

### Within Phase 3 (US1) Dependencies

- T010, T011 → parallel (write tests first; no app code needed)
- T012 → independent of T010/T011 (repository method); can run in parallel with them
- T013 → strictly after T011 exists (makes it pass, per Constitution I Test-First — NOT marked `[P]`); depends on T004, T007, T008 from Phase 2
- T014 → after T012, T013
- T015 → after T014 (the refresh behavior it tests for now exists); fixes the feature-001 regression introduced by T014
- T016 → after T013, T014
- T017 → after T016 (steps call real endpoints); uses the shared fixture from T009

### Within Phase 5 (US3) Dependencies

- T020, T021 → parallel (write tests first)
- T022 → after T021 (makes it pass); modifies the same file as T013
- T023 → after T022 (handlers need the exception types raised by T022's logic)
- T024 → after T023

### Parallel Opportunities

```
Phase 1 parallel group: T001, T002, T003 (all can run simultaneously)

Phase 2: T004 first (defines models consumed by T007/T008), then T005, T006, T007, T008 in
parallel; T009 (conftest.py fixture) is independent and can run any time in Phase 2

Phase 3 test-writing group: T010, T011 (parallel); T012 can also run in parallel with both
Phase 3: T013 is NOT parallel — it must follow T011

Phase 4: T018 can be written in parallel with any Phase 3 implementation task

Phase 5 test-writing group: T020, T021 (parallel)

Phase 6: T025 can be written in parallel with Phase 3/4/5 work (US4 only depends on Phase 2)

Phase 7 parallel group: T028, T029, T031 (independent)
```

---

## Parallel Example: User Story 1

```bash
# Launch the test-writing and repository tasks for User Story 1 together:
Task: "Write Gherkin feature file tests/features/ladder_pricing.feature"
Task: "Write failing unit tests in tests/unit/test_pricing_enrichment_service.py"
Task: "Add LadderRepository.read_ladder_df() to app/repositories/ladder_repository.py"

# T013 (PricingEnrichmentService) must NOT start until the unit tests above exist and fail —
# it is intentionally excluded from this parallel batch.
```

---

## Implementation Strategy

### MVP: User Story 1 Only

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**:
   - `pytest tests/unit/test_pricing_enrichment_service.py tests/features/ladder_pricing.feature tests/features/ingest_ladder.feature -m "us1 or us3"`
   - `POST` a real ledger via curl against a running `market-data-web-service`; verify the downloaded XLSX has `price`/`market_value`/`portfolio_weight` columns
5. Proceed to Phase 4 (US2) once US1 is green

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) → priced ladder works end-to-end, feature-001 regression fixed → **demo-able MVP**
3. Phase 4 (US2) → batching behavior verified with dedicated tests
4. Phase 5 (US3) → fail-fast error paths covered
5. Phase 6 (US4) → configuration and end-to-end wiring verified
6. Phase 7 → code quality gates pass, OpenAPI/quickstart verified

---

## Notes

- `[P]` = parallelisable (different files, no blocking dependency). T013 and T022 deliberately do
  NOT carry `[P]` even though later phases might tempt it — both must follow the unit tests they
  make pass (Constitution I, NON-NEGOTIABLE)
- `[Story]` maps task to user story for traceability
- BDD test tasks MUST be written and verified to FAIL before implementation tasks begin
- Use `pytest -m us1` / `-m us2` etc. to run one story's tests in isolation (Gherkin `@usN` tags map to pytest marks — filter with `-m`, not `-k`); the `us1`–`us4` markers already registered in `pyproject.toml` (from feature 001) are reused here across the new `.feature` files — no new marker registration needed
- Commit after each checkpoint (end of each user story phase)
- `data/` and `logs/` remain gitignored — never commit runtime artefacts
- The identifier-mapping JSON file itself lives outside this repository (configured path) and is never committed
- T015 fixes a cross-feature regression: feature 002's FR-013 intentionally supersedes feature
  001's FR-007 idempotency guarantee (see spec.md Assumptions). Feature 001's spec.md is left
  unedited as a historical record; only the test code is updated
