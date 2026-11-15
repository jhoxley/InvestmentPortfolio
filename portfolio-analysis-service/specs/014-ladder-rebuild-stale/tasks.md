---

description: "Task list for feature implementation"
---

# Tasks: On-Demand Ladder Rebuild for Stale Requests

**Input**: Design documents from `/specs/014-ladder-rebuild-stale/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rebuild-trigger-delta.md, quickstart.md

**Tests**: Required, not optional — the project constitution (`.specify/memory/constitution.md`,
Principle I, NON-NEGOTIABLE) mandates TDD for all feature development: tests written and
reviewed before implementation, Gherkin BDD scenarios for every acceptance criterion, and a
Red-Green-Refactor cycle. Every test task below MUST be completed, and MUST be verified to fail,
before its corresponding implementation task begins.

**Organization**: Tasks are grouped by user story (US1/US2/US3 from spec.md) to enable
independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single existing FastAPI project. All paths are relative to
`C:\GitHub\JHoxley\InvestmentPortfolio\portfolio-analysis-service`.

---

## Phase 1: Setup

**Purpose**: Create the new package and feature test scaffolding; no behavior yet.

- [X] T001 Create `app/services/rebuild/__init__.py` (new package for all rebuild orchestration code)
- [X] T002 [P] Create `tests/features/ladder_rebuild_on_stale_request.feature` with the `Feature:` header and all Gherkin scenarios transcribed verbatim from spec.md's three user stories, tagged `@us1`, `@us2`, `@us3` per `pyproject.toml`'s existing marker convention
- [X] T003 [P] Create empty `tests/steps/ladder_rebuild_on_stale_request_steps.py` with the pytest-bdd `scenarios("../features/ladder_rebuild_on_stale_request.feature")` registration, matching the pattern in `tests/steps/var_series_backtest_api_steps.py`

**Checkpoint**: Feature file parses under `pytest --collect-only`; no steps implemented yet (expected to fail collection until Foundational+US1 step defs exist — acceptable at this stage).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data-model changes and the rebuild orchestration services every user story
depends on. No user story can be implemented until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Data model changes

- [X] T004 [P] Add `rebuilt_at: datetime | None` field to `AccountMeta` in `app/repositories/ladder_repository.py`; update `write()`/`read_meta()` round-trip (no behavior change yet, just the field)
- [X] T005 [P] Add `rebuilt_at: datetime | None` field to `CapitalMeta` in `app/repositories/capital_repository.py`; update `write()`/`write_meta()`/`read_meta()` round-trip
- [X] T006 [P] Add a `provenance: Literal["ingested", "projected"]` column to every row written by `LadderRepository.write()`'s caller contract — update `app/services/ingestion_service.py` to set `provenance="ingested"` on every row it writes (both the new-account and checksum-match-refresh paths), and update `app/repositories/ladder_repository.py`'s `read_ladder_df()`/`read_full_df()` docstrings/column lists to include `provenance`
- [X] T007 [P] Apply the same `provenance="ingested"` tagging to every row written by `app/services/capital_ingestion_service.py`

### Rebuild orchestration services

- [X] T008 Add an explicit `end_date: date` parameter to `LadderExpander.expand()` in `app/services/ladder_expander.py` (currently hardcoded to `today` minus 2 business days internally); update `IngestionService` call site in `app/services/ingestion_service.py` to pass the existing T-2 `end_date` explicitly so ingestion behavior is unchanged
- [X] T009 [P] Unit test `tests/unit/test_ladder_expander_end_date.py` proving `LadderExpander.expand()` expands through an arbitrary caller-supplied `end_date`, not just the T-2 default (write first; verify it fails against the pre-T008 signature, then passes after T008)
- [X] T010 [US-shared] Implement `RebuildLockRegistry` in `app/services/rebuild/rebuild_lock_registry.py`: an in-process `threading.Lock` keyed by `(account_name, resource)` where `resource` is `"ladder" | "capital"`, mirroring the `ThreadRunScheduler` pattern in `app/services/var/run_scheduler.py` (lazy per-key lock creation guarded by one outer lock)
- [X] T011 [P] Unit test `tests/unit/test_rebuild_lock_registry.py` proving two concurrent callers for the same `(account, resource)` key serialise (second blocks until first releases), while different keys do not block each other (write first; verify it fails with no implementation, then passes after T010)
- [X] T012 Factor `TimeseriesDateResolver._most_recent_business_day_on_or_before`/`_business_day_before` out of `app/services/timeseries_date_resolver.py` into a new shared `app/services/business_day_helpers.py` module (both are pure functions of `today` with no dependency on the resolver's own state); update `TimeseriesDateResolver` to import and use them from there. Then implement `StalenessGate` in `app/services/rebuild/staleness_gate.py`, using the shared helpers to compute the capped `rebuild_target_end` from `last_known_date`, `resolved_end`, and `today`, and whether a rebuild is needed
- [X] T013 [P] Unit test `tests/unit/test_staleness_gate.py` covering: no rebuild needed when `resolved_end <= last_known_date`; rebuild needed and correctly capped when `resolved_end > last_known_date`; cap never exceeds the prior business day even when `resolved_end` requests further forward (write first; verify failure, then pass after T012)
- [X] T013a [P] Unit test `tests/unit/test_business_day_helpers.py` covering the two functions factored out in T012 directly, plus a regression check that `TimeseriesDateResolver`'s existing tests still pass unchanged after the refactor
- [X] T014 Implement `LadderRebuildService` in `app/services/rebuild/ladder_rebuild_service.py`: reads the stored ladder via `LadderRepository.read_ladder_df()`, calls `LadderExpander.expand(df, end_date=rebuild_target_end)` (T008), then `PricingEnrichmentService.enrich()` and `ReturnsEnrichmentService.enrich()`, tags newly-added rows `provenance="projected"`, concatenates with the existing stored rows, and persists via `LadderRepository.write()` with `AccountMeta.to_date` advanced and `rebuilt_at` set (T004); on `PriceCoverageError`, classifies partial vs. total unavailability per research.md R7 (every requested business day missing pricing for at least one sub-account = total; otherwise partial) and applies FR-013 (total: raise a new `RebuildUnavailableError` the caller catches to fall back, persist nothing) or FR-010 (partial: persist the rebuildable prefix, set `market_value`/dependent columns to `None` for unresolved dates)
- [X] T015 [P] Add `RebuildUnavailableError` to `app/exceptions.py` (caught internally by callers of `LadderRebuildService`/`CapitalRebuildService` to trigger the FR-013 silent fallback; never surfaces as an HTTP error itself)
- [X] T016 [P] Unit test `tests/unit/test_ladder_rebuild_service.py` covering: successful full rebuild (fresh prices available for every gap day, `provenance="projected"` rows appended, `AccountMeta` updated); partial unavailability (some dates null, persisted prefix correct); total unavailability (raises `RebuildUnavailableError`, nothing persisted) — using a fake `MarketDataClient` (write first; verify failure, then pass after T014/T015)
- [X] T017 Implement `CapitalRebuildService` in `app/services/rebuild/capital_rebuild_service.py`: reads the stored capital series via `CapitalRepository.read_df()`, extends it through `rebuild_target_end` using `expand_business_days()` (no pricing dependency — values are carried forward as-is per research.md R3), tags new rows `provenance="projected"`, persists via `CapitalRepository.write()` with `to_date` advanced and `rebuilt_at` set
- [X] T018 [P] Unit test `tests/unit/test_capital_rebuild_service.py` covering: extension through `rebuild_target_end` with carried-forward values, `provenance="projected"` tagging, and `AccountMeta`/`CapitalMeta` update (write first; verify failure, then pass after T017)

**Checkpoint**: Foundation ready — `StalenessGate`, `LadderRebuildService`, `CapitalRebuildService`,
and `RebuildLockRegistry` all exist and are unit-tested in isolation. No read endpoint calls them
yet. User story implementation can now begin.

---

## Phase 3: User Story 1 - Fresh market data instead of stale flat-fill (Priority: P1) 🎯 MVP

**Goal**: Every date-range-bearing GET endpoint returns real, day-by-day market-priced values
for a stale account instead of one repeated flat-filled figure, with the rebuild capped at the
prior business day.

**Independent Test**: Request `GET /v1/accounts/{account}/timeseries` for a range extending past
the account's last ingested/rebuilt date; confirm returned values vary with market pricing and
no date beyond the prior business day is populated.

### Tests for User Story 1 (write first; MUST fail before implementation)

- [X] T019 [P] [US1] Implement the `@us1` step definitions in `tests/steps/ladder_rebuild_on_stale_request_steps.py` for both US1 scenarios (stale request extends past last ingested date; requested end date in the future)
- [X] T020 [P] [US1] Integration test `tests/unit/test_timeseries_service_rebuild_trigger.py` proving `TimeSeriesService.get_series()` invokes the rebuild when `resolved_end` exceeds the ladder's/capital's last-known date, using fake repositories/clients, and that returned `market_value` values differ per day rather than repeating

### Implementation for User Story 1

- [X] T021 [US1] Wire `StalenessGate` + `LadderRebuildService`/`CapitalRebuildService` + `RebuildLockRegistry` into `TimeSeriesService.get_series()` in `app/services/timeseries_service.py`: after `self._date_resolver.resolve(...)` and before `self._ladder_repo.read_full_df()`/`self._capital_repo.read_df()`, check staleness per needed resource, acquire the resource's lock, rebuild if required, release, then proceed to read
- [X] T022 [P] [US1] Apply the equivalent wiring to `app/services/position_timeseries_service.py` (backs `GET /v1/accounts/{account}/position` only — `GET /v1/accounts/{account}/positions`, the plural enumeration endpoint, takes no `start`/`end` and reads `ladder_repo.read_full_df()` directly in `app/api/position_timeseries.py`'s `list_account_positions`, bypassing this service entirely; it needs no wiring and already satisfies FR-011 by construction, see T028a)
- [X] T023 [P] [US1] Apply the equivalent wiring to `app/services/performance_service.py` (backs `GET /v1/accounts/{account}/performance`)
- [X] T024 [P] [US1] Apply the equivalent wiring to `app/services/daily_return_series_loader.py` (backs `GET /v1/accounts/{account}/risk/return-histogram`)
- [X] T025 [US1] Make `TimeSeriesEntry`'s dynamically-allowed attribute values nullable in `app/models/timeseries.py` (currently forced to `float(...)` in `TimeSeriesService.get_series()` — change to allow `None` passthrough when the underlying value is null, per contracts/rebuild-trigger-delta.md)
- [X] T026 [P] [US1] Apply the equivalent nullable-value change to `app/models/position_timeseries.py` and `app/models/performance.py` for their own per-date numeric fields
- [X] T027 [US1] On total market-data unavailability (`RebuildUnavailableError` from T014/T015), catch it in each of the four wired services (T021-T024) and fall back to the pre-rebuild read path for that request only, per FR-013
- [X] T028 [US1] Append the documented sentence from `contracts/rebuild-trigger-delta.md` to the OpenAPI `description`/docstring of each affected endpoint in `app/api/timeseries.py`, `app/api/position_timeseries.py` (the `/position` endpoint only), `app/api/performance.py`, and `app/api/risk.py`
- [X] T028a [US1] Integration test `tests/unit/test_fr011_datelss_endpoints_reflect_rebuild.py` (FR-011) asserting that after a rebuild is triggered and persisted via `TimeSeriesService.get_series()` (T021), a subsequent call to each date-less read path — `LadderRepository.read_meta()`/`read_full_df()` as used by `GET .../ladder` and `GET .../ladder/download`, `CapitalRepository.read_meta()` as used by `GET .../capital`, `AccountsService.list_summaries()` as used by `GET /v1/accounts`, and `list_account_positions`'s direct `read_full_df()` call as used by `GET .../positions` — reflects the rebuild's advanced `to_date`/new rows, with no production code change required to pass
- [X] T029 [US1] Add structured JSON log events (`rebuild_triggered`, `rebuild_complete`, `rebuild_fallback_total_unavailable`) via the existing `structlog` pattern in `app/services/rebuild/staleness_gate.py`, `ladder_rebuild_service.py`, and `capital_rebuild_service.py`

**Checkpoint**: User Story 1 is fully functional and independently testable — a stale request to
any of the four affected endpoints now triggers a rebuild and returns fresh data, capped at the
prior business day.

---

## Phase 4: User Story 2 - Rebuild happens once, not on every request (Priority: P2)

**Goal**: A rebuild triggered by one request is persisted so subsequent requests for the same or
a narrower range are served without repeating the rebuild, and concurrent requests for the same
gap produce exactly one rebuild.

**Independent Test**: Issue the same stale request twice with a call-counting fake market-data
client; confirm the client is called only on the first request. Issue two concurrent requests
requiring the same gap; confirm the client is called only once in total.

### Tests for User Story 2 (write first; MUST fail before implementation)

- [X] T030 [P] [US2] Implement the `@us2` step definitions in `tests/steps/ladder_rebuild_on_stale_request_steps.py` for both US2 scenarios (no re-trigger on repeat request; concurrent requests produce one rebuild)
- [X] T031 [P] [US2] Unit test `tests/unit/test_timeseries_service_rebuild_once.py` proving a second call to `TimeSeriesService.get_series()` for an already-rebuilt range makes zero calls to the fake market-data client (first call rebuilds and advances `AccountMeta.to_date`/`CapitalMeta.to_date`; second call reads only)
- [X] T032 [P] [US2] Concurrency unit test `tests/unit/test_rebuild_concurrency.py` using two threads calling `TimeSeriesService.get_series()` for the same stale account/gap simultaneously against a fake market-data client with an internal call counter; assert the counter shows exactly one rebuild's worth of calls and both threads receive identical, correct results

### Implementation for User Story 2

- [X] T033 [US2] Add a unit test asserting that T021-T024's wiring re-reads `AccountMeta`/`CapitalMeta` only *after* acquiring the `RebuildLockRegistry` lock, not before — i.e. a caller that waited on the lock observes the just-completed rebuild's updated `to_date` and correctly skips re-rebuilding. If the test fails against T021-T024's current ordering, fix the staleness-check-then-lock-then-reread sequence in `app/services/timeseries_service.py`, `app/services/position_timeseries_service.py`, `app/services/performance_service.py`, and `app/services/daily_return_series_loader.py` until it passes (same files as T021-T024)

**Checkpoint**: User Stories 1 AND 2 both work independently — repeated and concurrent stale
requests each result in exactly one rebuild.

---

## Phase 5: User Story 3 - Later ledger ingestion corrects previously rebuilt periods (Priority: P3)

**Goal**: When a new ledger is ingested with trades/corporate actions dated within a previously
rebuilt (projected) span, the persisted ladder is recomputed so that span reflects the real
transactions, not the earlier held-constant projection.

**Independent Test**: Rebuild a gap for an account, then ingest a ledger containing a transaction
dated inside that gap; confirm the persisted ladder for that period changes and `provenance`
flips from `"projected"` to `"ingested"` for the superseded dates.

### Tests for User Story 3 (write first; MUST fail before implementation)

- [X] T034 [P] [US3] Implement the `@us3` step definitions in `tests/steps/ladder_rebuild_on_stale_request_steps.py` for the ledger-supersession scenario
- [X] T035 [P] [US3] Unit test `tests/unit/test_ingestion_service_supersession.py` covering: a new ledger whose date range overlaps `provenance="projected"` rows triggers recomputation of that overlapping span (re-expand, re-price, re-return, re-persist with `provenance="ingested"`); a new ledger with no overlap with any projected span falls through to today's existing checksum-mismatch `MergeNotSupportedError` behavior, unchanged

### Implementation for User Story 3

- [X] T036 [US3] Add the supersession branch to `IngestionService.ingest()` in `app/services/ingestion_service.py` per research.md R5: on checksum mismatch, before raising `MergeNotSupportedError`, check whether the uploaded ledger's own date range overlaps any `provenance="projected"` row in the currently stored ladder (via `LadderRepository.read_full_df()`); if so, re-run `LadderExpander.expand()` over the union of the new ledger's rows and any stored `provenance="ingested"` rows outside its range, re-enrich via `PricingEnrichmentService`/`ReturnsEnrichmentService`, tag the result `provenance="ingested"` for the recomputed span, and persist; otherwise raise `MergeNotSupportedError` as today
- [X] T037 [US3] Add a structured log event (`ingestion_supersedes_projected_span`) in `app/services/ingestion_service.py` recording the account, the superseded date range, and the row counts affected

**Checkpoint**: All three user stories are independently functional. The feature is complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all stories.

- [X] T038 [P] Run `mypy --strict` and `ruff check`/`ruff format` across all new and changed files; fix any violations (Constitution III)
- [X] T039 [P] Add/verify docstrings (purpose, args, returns, raises) on every new public class/function per Constitution III
- [X] T040 Execute `quickstart.md` end-to-end against a locally running instance (`uvicorn app.main:app --reload`) and confirm every numbered step behaves as documented
- [X] T041 Run the full test suite (`python -m pytest`) and confirm all existing tests still pass alongside the new ones (no regression in ingestion, timeseries, position, performance, or risk endpoints)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational and on US1's wiring (T021-T024) existing,
  since it verifies/exercises that same wiring's concurrency and idempotency behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational only (the `provenance` column from T006 and
  `LadderRebuildService` from T014) — independently testable from US1/US2, though it is most
  meaningful once US1 can actually produce `provenance="projected"` rows to supersede.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T004, T005, T006, T007 (data model changes) can run in parallel — different files.
- T009, T011, T013, T013a, T016, T018 (foundational unit tests) can each run in parallel with
  each other, but each must follow its own implementation task per the Red-Green-Refactor rule.
- T022, T023, T024 (wiring the other two read services plus `/position`) can run in parallel once
  T021 establishes the pattern in `TimeSeriesService`.
- T026 can run in parallel with T025.
- T028a can run in parallel with T028, T029 once T021-T024 are complete.

---

## Parallel Example: Foundational Data Model Changes

```bash
Task: "Add rebuilt_at to AccountMeta in app/repositories/ladder_repository.py"
Task: "Add rebuilt_at to CapitalMeta in app/repositories/capital_repository.py"
Task: "Tag provenance=ingested in app/services/ingestion_service.py"
Task: "Tag provenance=ingested in app/services/capital_ingestion_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run `tests/features/ladder_rebuild_on_stale_request.feature`'s `@us1`
   scenarios and `quickstart.md` steps 1-4 independently.
5. Deploy/demo if ready — this alone fixes the reported defect.

### Incremental Delivery

1. Setup + Foundational → rebuild services exist, nothing wired yet.
2. Add US1 → stale requests return fresh data (MVP — fixes the reported bug).
3. Add US2 → repeated/concurrent stale requests no longer duplicate rebuild work.
4. Add US3 → later ledger ingestion correctly supersedes a previously rebuilt span.
5. Polish → type/lint clean, full regression pass, quickstart validated end-to-end.

---

## Notes

- [P] tasks touch different files with no uncompleted dependency between them.
- [Story] labels map each task to spec.md's US1/US2/US3 for traceability.
- Per Constitution Principle I, every test task listed above must be written and observed to
  fail before its paired implementation task is started — do not implement first and backfill
  tests.
- Commit after each task or logical group, per repository convention.
