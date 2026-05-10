# Tasks: YFinance Price Data Cache

**Input**: Design documents from `specs/003-yfinance-cache/`
**Prerequisites**: plan.md âœ…, spec.md âœ…, research.md âœ…, data-model.md âœ…, contracts/openapi-additions.yaml âœ…

**Tests**: BDD Gherkin `.feature` files and their step definitions are MANDATORY per the project constitution (Principle III). They MUST be written and confirmed failing before any implementation task in the same user story begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on concurrent tasks)
- **[Story]**: Which user story this task belongs to (US1â€“US5)
- Exact file paths are included in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new dependency, create the configuration file, and establish the OpenAPI contract before any implementation begins (Principle VI â€” OpenAPI-First).

- [X] T001 Update pyproject.toml â€” add `pyyaml>=6.0` to `project.dependencies`
- [X] T002 [P] Create `config.yaml` at project root with content: `cache:\n  directory: ./cache`
- [X] T003 [P] Update `openapi.yaml` â€” merge additions from `specs/003-yfinance-cache/contracts/openapi-additions.yaml`: add `DELETE /cache/{ticker}` and `DELETE /cache` paths; add `CacheDeleteResponse` and `CacheClearResponse` component schemas

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story can be implemented. No user story work begins until this phase is done.

- [X] T004 Create `app/config.py` â€” define `CacheSettings(BaseModel)` with `directory: Path = Path("./cache")`; `Settings(BaseModel)` with `cache: CacheSettings`; `load_settings(config_path)` reading `config.yaml` via `yaml.safe_load`; `get_settings()` FastAPI dependency (module-level singleton)
- [X] T005 [P] Create `app/cache/__init__.py` (empty module marker)
- [X] T006 Create `app/cache/repository.py` â€” implement `CacheRepository` with injected `cache_dir: Path`; implement `_filename(ticker)` (sanitise unsafe chars with `_`); `read(ticker) -> list[tuple[date, float]] | None` (parse CSV; return `None` on missing/unreadable); `write(ticker, records)` (sort by date, dedup, write to `{ticker}.csv.tmp`, `os.replace` to `{ticker}.csv`); `delete(ticker) -> bool`; `delete_all() -> int`
- [X] T007 [P] Add `CacheDeleteResponse(BaseModel)` with `ticker: str`, `deleted: bool`; and `CacheClearResponse(BaseModel)` with `deleted_count: int` to `app/models/pricing.py`
- [X] T008 [P] Update `tests/conftest.py` â€” add `tmp_cache_dir(tmp_path) -> Path` fixture; add `client_with_cache(tmp_cache_dir) -> Generator[TestClient, None, None]` fixture that overrides `get_settings` via `app.dependency_overrides` and restores after yield
- [X] T009 Update `app/main.py` lifespan â€” import and call `get_settings()` at startup; call `settings.cache.directory.mkdir(parents=True, exist_ok=True)` (FR-011); log `cache_dir_ready` at INFO with `path=settings.cache.directory`

**Checkpoint**: Foundation ready â€” all user story implementation can now begin.

---

## Phase 3: User Story 1 â€” Full Cache Hit (Priority: P1) ðŸŽ¯ MVP

**Goal**: `GET /securities/{ticker}/history` serves historical prices entirely from the local cache when the requested range is fully covered, making zero calls to YFinance.

**Independent Test**: Seed `{ticker}.csv` in `tmp_cache_dir` covering a date range; call `GET /securities/{ticker}/history` for that same range via `client_with_cache`; assert the response contains the expected prices; assert the inner provider's `get_price_history` was never called.

### BDD Scenarios for User Story 1 (MANDATORY â€” write and confirm failing FIRST) âš ï¸

> **MUST be red before any implementation task below begins (Red-Green-Refactor)**

- [X] T010 [P] [US1] Write `tests/features/cache_full_hit.feature` â€” two scenarios from spec US1: "Request is fully satisfied by cached data" and "Request for a sub-range of cached data uses cache only" (exact Gherkin from spec.md)
- [X] T011 [P] [US1] Write `tests/steps/cache_full_hit_steps.py` â€” step definitions: seed CSV to `tmp_cache_dir`, configure `client_with_cache`, assert response prices match seeded data, assert mock inner provider not called; run `pytest tests/features/cache_full_hit.feature` and confirm all scenarios fail (red)

### Implementation for User Story 1

- [X] T012 [US1] Create `app/providers/cached_provider.py` â€” `CachedPricingProvider(PricingProvider)` with `__init__(inner: PricingProvider, repo: CacheRepository)`; `get_current_price()` delegates to `inner` unchanged; `get_price_history()` reads from `repo.read(ticker)`, computes `cached_min` / `cached_max` from actual dates, returns filtered records when full coverage detected
- [X] T013 [US1] Update `app/api/securities.py` `get_pricing_service()` â€” add `settings: Settings = Depends(get_settings)` parameter; instantiate `CacheRepository(settings.cache.directory)` and `CachedPricingProvider(YFinanceProvider(), repo)`; inject into `PricingService`
- [X] T014 [US1] Add structlog `INFO` `cache_hit` log event to `app/providers/cached_provider.py` full-hit branch (fields: `ticker`, `from_date`, `to_date`, `records_returned`)

**Checkpoint**: User Story 1 fully functional and independently testable. Run `pytest tests/features/cache_full_hit.feature` â€” all green.

---

## Phase 4: User Story 2 â€” Partial Cache Hit (Priority: P2)

**Goal**: When the requested date range extends beyond the cached data, `GET /securities/{ticker}/history` fetches only the uncovered segments from YFinance, merges them into the cache, and returns the complete result. If YFinance fails, the entire request errors and the cache is unchanged.

**Independent Test**: Seed a partial-range CSV; request a wider range via `client_with_cache` with a mocked inner provider; assert only the uncovered segments are fetched (inner provider called exactly once or twice); assert the response contains the full range; assert the cache CSV now contains the merged data.

### BDD Scenarios for User Story 2 (MANDATORY â€” write and confirm failing FIRST) âš ï¸

- [X] T015 [P] [US2] Write `tests/features/cache_partial_hit.feature` â€” four scenarios from spec US2: "Request extends beyond start", "Request extends beyond end", "Request extends beyond both ends", "YFinance fails when fetching a missing segment"
- [X] T016 [P] [US2] Write `tests/steps/cache_partial_hit_steps.py` â€” step definitions: seed partial CSV, mock inner provider to return specific data, assert provider calls, assert cache file content; run and confirm all scenarios fail (red)

### Implementation for User Story 2

- [X] T017 [US2] Extend `get_price_history()` in `app/providers/cached_provider.py` â€” partial hit branch: compute `before_segment` (`[from_date, cached_min âˆ’ 1 day]` if applicable) and `after_segment` (`[cached_max + 1 day, to_date]` if applicable); fetch each missing segment from `inner`; on `ProviderUnavailableError` or `DataNotFoundError` propagate immediately without writing to cache (FR-012); merge fetched records with cached records (dedup by date, sort ascending); call `repo.write(ticker, merged)`; return filtered result
- [X] T018 [US2] Add structlog logging to `app/providers/cached_provider.py` â€” `INFO` `cache_partial_hit` (fields: `ticker`, `segments_fetched`, `records_added`); `INFO` `cache_write` (fields: `ticker`, `total_records`); `ERROR` `cache_yfinance_error` (fields: `ticker`, `segment`, `error`)

**Checkpoint**: User Stories 1 and 2 functional. Partial hit + YFinance failure path covered.

---

## Phase 5: User Story 3 â€” Cache Miss (Priority: P3)

**Goal**: When no cache entry exists for the requested ticker, `GET /securities/{ticker}/history` fetches the full range from YFinance and creates a new cache file, so subsequent requests for the same range are served from cache.

**Independent Test**: Ensure no CSV exists for a ticker in `tmp_cache_dir`; call `GET /securities/{ticker}/history` via `client_with_cache` with mocked inner provider; assert inner provider called for full range; assert `{ticker}.csv` now exists in `tmp_cache_dir` with correct content.

### BDD Scenarios for User Story 3 (MANDATORY â€” write and confirm failing FIRST) âš ï¸

- [X] T019 [P] [US3] Write `tests/features/cache_miss.feature` â€” one scenario from spec US3: "No cache exists for requested ticker"
- [X] T020 [P] [US3] Write `tests/steps/cache_miss_steps.py` â€” step definitions: assert no CSV present, mock inner provider, assert CSV created with correct rows after request; run and confirm scenario fails (red)

### Implementation for User Story 3

- [X] T021 [US3] Extend `get_price_history()` in `app/providers/cached_provider.py` â€” cache miss branch (triggered when `repo.read()` returns `None`): fetch full `[from_date, to_date]` from `inner`; call `repo.write(ticker, result)`; return result
- [X] T022 [US3] Add structlog `INFO` `cache_miss` log event to `app/providers/cached_provider.py` (fields: `ticker`, `from_date`, `to_date`)

**Checkpoint**: Full cache lifecycle operational â€” miss â†’ populate â†’ full hit â†’ partial hit â†’ merge. User Stories 1, 2, and 3 all functional.

---

## Phase 6: User Story 4 â€” Delete Single Ticker Cache (Priority: P4)

**Goal**: `DELETE /cache/{ticker}` removes the cache entry for the specified ticker and returns confirmation of whether an entry existed.

**Independent Test**: Seed a CSV for a ticker; call `DELETE /cache/{ticker}` via `client_with_cache`; assert 200 with `deleted=true`; assert CSV no longer exists; call again; assert 200 with `deleted=false`.

### BDD Scenarios for User Story 4 (MANDATORY â€” write and confirm failing FIRST) âš ï¸

- [X] T023 [P] [US4] Write `tests/features/cache_management.feature` â€” US4 scenarios: "Delete cache for an existing ticker" and "Delete cache for a ticker with no existing cache"
- [X] T024 [P] [US4] Write `tests/steps/cache_management_steps.py` â€” step definitions for US4: seed/no-seed CSV, call DELETE endpoint, assert response body and filesystem state; run and confirm scenarios fail (red)

### Implementation for User Story 4

- [X] T025 [US4] Create `app/api/cache.py` â€” `APIRouter(prefix="/cache", tags=["Cache Management"])`; `DELETE /{ticker}` endpoint with `ticker: str = Path(...)` and `settings: Settings = Depends(get_settings)`; call `CacheRepository(settings.cache.directory).delete(ticker)`; return `CacheDeleteResponse(ticker=ticker, deleted=deleted)`; add structlog `INFO` `cache_delete_ticker` event
- [X] T026 [US4] Update `app/main.py` â€” import `cache` router; add `app.include_router(cache.router)`

**Checkpoint**: User Stories 1â€“4 functional. Cache management API partially live.

---

## Phase 7: User Story 5 â€” Clear Entire Cache (Priority: P5)

**Goal**: `DELETE /cache` removes all cached price data for all tickers and returns the count of entries deleted. Works correctly on both a populated and an empty cache.

**Independent Test**: Seed CSVs for multiple tickers; call `DELETE /cache` via `client_with_cache`; assert 200 with `deleted_count` equal to the number seeded; assert all CSVs removed; call again; assert `deleted_count=0`.

### BDD Scenarios for User Story 5 (MANDATORY â€” write and confirm failing FIRST) âš ï¸

- [X] T027 [US5] Add US5 scenarios to `tests/features/cache_management.feature` â€” "Clear all cache entries when cache contains data" and "Clear all cache entries when cache is empty"
- [X] T028 [US5] Add US5 step definitions to `tests/steps/cache_management_steps.py` â€” seed multiple CSVs, call DELETE /cache, assert filesystem empty and count correct; run and confirm new scenarios fail (red)

### Implementation for User Story 5

- [X] T029 [US5] Add `DELETE /` (clear all) endpoint to `app/api/cache.py` â€” call `CacheRepository(settings.cache.directory).delete_all()`; return `CacheClearResponse(deleted_count=count)`; add structlog `INFO` `cache_delete_all` event (fields: `deleted_count`)

**Checkpoint**: All five user stories complete and independently testable.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality gate â€” type checking, linting, and final BDD suite confirmation.

- [X] T030 [P] Run `mypy --strict` on all new and modified modules: `app/config.py`, `app/cache/repository.py`, `app/providers/cached_provider.py`, `app/api/cache.py`, `app/models/pricing.py`; fix all type errors
- [X] T031 [P] Run `ruff check` and `ruff format` on all new and modified files; fix all violations
- [X] T032 Run full BDD test suite: `python -m pytest tests/`; confirm all scenarios pass (green); all five user stories validated end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately; T002 and T003 are parallel
- **Foundational (Phase 2)**: Requires Phase 1 complete; T005, T007, T008 are parallel with T004 and T006
- **US Phases (3â€“7)**: All require Phase 2 complete; BDD tasks within each story are parallel with each other; implementation follows BDD
- **Polish (Phase 8)**: Requires all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Requires Phase 2 only â€” no dependency on other stories; implements the shared `CachedPricingProvider` skeleton
- **US2 (P2)**: Requires US1 (extends `CachedPricingProvider`)
- **US3 (P3)**: Requires US1 (extends `CachedPricingProvider`; can be done in parallel with US2)
- **US4 (P4)**: Requires Phase 2 only â€” independent of US1/US2/US3
- **US5 (P5)**: Requires US4 (extends `app/api/cache.py` and step definitions)

### Within Each User Story

1. BDD feature file + step definitions â†’ confirm red
2. Implementation tasks â†’ make scenarios green
3. Logging task â†’ add observability
4. Verify checkpoint

### Parallel Opportunities

- T002 â€– T003 (different files, no deps)
- T005 â€– T007 â€– T008 (during Phase 2, after T004 started)
- T010 â€– T011 (BDD file + steps â€” different files)
- T019 â€– T020 (BDD file + steps â€” different files)
- T023 â€– T024 (BDD file + steps â€” different files)
- T030 â€– T031 (different tools, same files are read-only)

---

## Parallel Examples

```bash
# Phase 1 parallel tasks:
T002: Create config.yaml
T003: Update openapi.yaml

# Phase 3 (US1) BDD tasks:
T010: Write cache_full_hit.feature
T011: Write cache_full_hit_steps.py

# Phase 5 (US3) BDD tasks:
T019: Write cache_miss.feature
T020: Write cache_miss_steps.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL â€” blocks all stories)
3. Complete Phase 3: User Story 1 (full cache hit)
4. **STOP and VALIDATE**: `pytest tests/features/cache_full_hit.feature` â€” all green
5. The service now avoids all redundant YFinance calls for repeat requests

### Incremental Delivery

1. Phase 1 + 2 â†’ Infrastructure ready
2. Phase 3 (US1) â†’ Full cache hits operational â†’ MVP
3. Phase 4 (US2) â†’ Partial cache hits + YFinance failure handling
4. Phase 5 (US3) â†’ Cache auto-populated on first request (full lifecycle)
5. Phase 6 (US4) â†’ Targeted cache invalidation via API
6. Phase 7 (US5) â†’ Full cache clear via API
7. Phase 8 â†’ Quality gate pass

---

## Notes

- `[P]` tasks touch different files and have no dependency on concurrently running tasks
- BDD tasks must produce **failing** tests before the implementation tasks in the same story begin
- `CachedPricingProvider.get_price_history()` is extended incrementally across US1/US2/US3 â€” test the relevant branch after each extension
- The `mock_provider` fixture in `tests/conftest.py` should be used as the `inner` provider in `CachedPricingProvider` for BDD tests; set its `get_price_history` return value to control what YFinance "returns"
- Commit after each phase checkpoint to keep git history clean and reversible

