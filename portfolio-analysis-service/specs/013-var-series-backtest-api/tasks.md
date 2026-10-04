---

description: "Task list for 013 — VaR Series, Backtest and Methods Endpoints"
---

# Tasks: VaR Series, Backtest and Methods Endpoints

**Input**: Design documents from `/specs/013-var-series-backtest-api/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md
**Methodology**: `docs/proposals/value-at-risk.md` §4

**Tests**: REQUIRED. The constitution's Principle I makes TDD non-negotiable. Every test task
must be written and **seen to fail** before its implementation task starts. BDD scenarios come
from spec.md's Gherkin blocks and go in `tests/features/var_series_backtest_api.feature` with
steps in `tests/steps/var_series_backtest_api_steps.py`; each story adds its own scenarios to
these two files, seeding the store directly via `VarRepository.commit()` (no calculation run is
executed — this feature never triggers one).

**Organization**: Tasks are grouped by user story. Paths are relative to
`portfolio-analysis-service/` unless prefixed with `(repo root)`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story from spec.md (US1–US4)

## Conventions every task must follow

- Full type annotations; Google-style docstrings on every public symbol; `mypy --strict app/`
  and `ruff check app/ tests/` clean; `ruff format`.
- Confidence levels are integer basis points internally (9500/9750/9900); the query boundary
  accepts percentages (`95`, `97.5`, `99`) and converts once, at the router (research.md §3).
- `var_window.py` (T006) must never call `LadderRepository.read_full_df()` — only
  `AccountsService.get_summary()` and `TimeseriesDateResolver`, matching
  `VarStatusService`'s existing pattern (research.md §1). A unit test MUST assert this.
- Quality ordering is `ok` > `degraded` > `insufficient`; `insufficient` and pending-outcome
  dates are always excluded from the backtest observation set, regardless of `min_quality`
  (FR-011) — never conditionally.
- Business-day adjacency for the Christoffersen chain-break rule and the VaR-stability
  measure uses `pandas.offsets.BDay(1)` on the *filtered* observation sequence (research.md §7).
- These endpoints MUST NOT write to the VaR store, call `VarRepository.commit()`,
  `write_run()`, or trigger `RunScheduler`/`VarRunService` in any way (FR-023).
- Never modify `app/services/var/engine.py`, `app/repositories/var_repository.py`,
  `app/services/var/var_run_service.py`, `app/services/var/var_status_service.py`, or any
  existing response shape from feature 012.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Empty test/feature-file skeletons everything else fills in. No new dependencies.

- [ ] T001 Create empty test modules `tests/unit/test_var_backtest_stats.py`,
  `tests/unit/test_var_window.py`, `tests/unit/test_var_series_service.py`,
  `tests/unit/test_var_backtest_service.py`, `tests/unit/test_var_methods_service.py`,
  `tests/unit/test_risk_var_series_openapi.py`; `tests/features/var_series_backtest_api.feature`
  (Feature header only); `tests/steps/var_series_backtest_api_steps.py` (binds the feature file
  via `scenarios(...)`, following the pattern already used in
  `tests/steps/var_calculation_runs_steps.py`).

**Checkpoint**: Empty files exist and import cleanly; `pytest --collect-only` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration, exceptions, response models and the shared ladder-free date-window
helper that every story's endpoint depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 [P] Write a unit test in `tests/unit/test_var_settings.py` (extend the existing file)
  asserting `VarSettings().headline_lookback == "2y"` and that constructing
  `VarSettings(headline_lookback="3y")` (not a key of `lookbacks`) raises `ValidationError` at
  construction time.
- [ ] T003 Add `headline_lookback: str = "2y"` to `VarSettings` in `app/config.py` with a
  `model_validator(mode="after")` asserting it is a key of `self.lookbacks` (research.md §10),
  making T002 pass.
- [ ] T004 [P] Write a unit test in `tests/unit/test_var_problem_details.py` (extend the existing
  file from feature 012) asserting `InvalidVarQueryError(message=..., fields=[...])` produces,
  through the FastAPI test client, a 422 `application/problem+json` body with
  `type` ending `invalid-var-query`, the given `detail`, and a non-empty `correlation_id`.
- [ ] T005 Add `InvalidVarQueryError(message: str, fields: list[str] | None = None)` to
  `app/exceptions.py`, following `InvalidVarRunRequestError`'s existing shape (research.md §2),
  and register its handler in `app/main.py` using the existing `_var_problem()` helper
  (422, slug `invalid-var-query`, title `"Invalid VaR Query"`), making T004 pass.
- [ ] T006 [P] Write a unit test in `tests/unit/test_var_window.py`: given a fake
  `AccountsService` whose `get_summary()` returns ladder metadata and a fake
  `LadderRepository` whose `read_full_df()` raises `AssertionError` if called,
  `resolve_window()` returns the correct resolved start/end without raising, and raises
  `AccountNotFoundError` / `MissingRequiredSourceError` / `FutureEndDateError` /
  `InvalidDateRangeError` in the same cases `DailyReturnSeriesLoader.load()` does.
- [ ] T007 Create `app/services/var/var_window.py`: a frozen `WindowResolution` dataclass
  (`resolved_start`, `resolved_end`, `ladder_from_date`) and `resolve_window(accounts_service,
  date_resolver, account_name, start, end, today, attribute_label) -> WindowResolution`
  (research.md §1), making T006 pass.
- [ ] T008 [P] Create `app/models/var_series.py` per data-model.md: `ConfidenceLevelEstimate`,
  `VarSeriesEntry`, `VarSeriesResponse`, `RollingExceptionPoint`, `BacktestConfidenceResult`,
  `VarBacktestResponse`, `MethodLookback`, `VarMethodsResponse` (`PnlBasis` and
  `TrafficLightZone` type aliases; `_links` aliased via `ConfigDict(populate_by_name=True)`,
  matching `app/models/var.py`'s existing pattern). Add a unit test (new
  `tests/unit/test_var_series_models.py`) proving `model_dump(by_alias=True)` on each response
  model produces a `_links` key, and that `var_gbp`/`exception_dates`/`rolling_exceptions`
  accept `None` where data-model.md says so.

**Checkpoint**: `mypy --strict app/` passes; `pytest tests/unit/test_var_settings.py
tests/unit/test_var_problem_details.py tests/unit/test_var_window.py
tests/unit/test_var_series_models.py` pass.

---

## Phase 3: User Story 1 - Read an Account's VaR Time Series (Priority: P1) 🎯 MVP

**Goal**: `GET /v1/accounts/{account_name}/risk/var` returns the stored estimate/outcome series
for a resolved range, one look-back and one or more confidence levels, joining `estimates.csv`
and `outcomes.csv` without recomputing anything.

**Independent Test**: Seed `estimates.csv`/`outcomes.csv` for an account via
`VarRepository.commit()` for a known date; request the series for that date and look-back;
assert every field matches the seeded row exactly, confidence-level/look-back filters narrow the
response correctly, and an account with nothing seeded returns `200` with an empty `series` and
`status`/`runs` links.

### Tests for User Story 1 (write first, must fail)

- [ ] T009 [P] [US1] Write `tests/unit/test_var_series_service.py` against a `VarRepository`
  pointed at `tmp_path`, seeded directly via `commit()` (no run service involved). Cover:
  a date with a full `ok`-quality estimate at one look-back/confidence returns exact values
  (SC-001); only the requested look-back's row is returned when multiple look-backs are stored
  for the same date; only the requested confidence levels appear in `levels`; omitting
  `confidence` returns every configured level; a `quality="insufficient"` row still appears with
  every `levels[].var_gbp`/`es_gbp`/exception field `None`; a pending-outcome row (
  `outcome_status="pending"`) has `hypothetical_pnl_gbp`/`ladder_pnl_gbp`/both exception flags
  `None`; the hypothetical-exception flag is `True` exactly when `hypothetical_pnl_gbp <
  -var_gbp` (strict); an account with nothing stored returns an empty `series` with `status` and
  `runs` links populated (FR-008, SC-005) rather than raising. **FR-023 guard**: pass a
  `VarRepository` test double (or spy) whose `commit()` and `write_run()` raise `AssertionError`
  if called, and assert `get_series()` never calls either — this endpoint must be provably
  read-only, not just read-only by omission.
- [ ] T010 [P] [US1] Add the five Gherkin scenarios from spec.md's User Story 1 to
  `tests/features/var_series_backtest_api.feature` under an `@us1` tag, and implement their step
  definitions in `tests/steps/var_series_backtest_api_steps.py`, seeding the store through
  `VarRepository.commit()` directly in `Given` steps.

### Implementation for User Story 1

- [ ] T011 [US1] Create `app/services/var/var_series_service.py`: `VarSeriesService.get_series(
  account_name, start, end, lookback, confidence_levels_bp, today) -> VarSeriesResponse`. Uses
  `resolve_window()` (T007) for validation/defaulting, reads
  `VarRepository.read_estimates()`/`read_outcomes()`, joins on `date`, filters to the resolved
  range and requested look-back, builds `VarSeriesEntry`/`ConfidenceLevelEstimate` per
  research.md §4–§5, and always includes `status`/`runs` in `_links` (making T009 pass).
- [ ] T012 [US1] Add `GET /accounts/{account_name}/risk/var` to `app/api/risk_var.py`: query
  params `start`, `end`, `lookback` (defaults to `settings.var.headline_lookback`), `confidence`
  (repeatable percentages, parsed and validated against `settings.var.confidence_levels_bp`,
  raising `InvalidVarQueryError` naming the supported values on an unsupported `lookback` or
  `confidence`); a `_get_var_series_service` dependency factory wiring `VarSeriesService` from
  `AccountsService`, `TimeseriesDateResolver` and `VarRepository`; a structlog
  `var_series_request` event logging `account_name`, `lookback`, confidence levels requested and
  the returned row count, mirroring `risk_service.py`'s `return_histogram_request` event
  (making T010's scenarios pass).
- [ ] T013 [US1] Add the series endpoint's paths/schemas from `contracts/openapi.yaml` to
  `tests/unit/test_risk_var_series_openapi.py`: assert `GET /v1/accounts/{account_name}/risk/var`
  is present in the live `/openapi.json`, with the `VarSeriesResponse` schema's required fields.

**Checkpoint**: User Story 1 is fully functional and independently testable —
`GET /v1/accounts/{account}/risk/var` works end-to-end against a seeded store.

---

## Phase 4: User Story 2 - Backtest a Confidence Level Against Realised Outcomes (Priority: P1)

**Goal**: `GET /v1/accounts/{account_name}/risk/var/backtest` returns Kupiec, Christoffersen,
conditional-coverage, traffic-light zone, exception dates, mean VaR and VaR stability per
confidence level, filterable by `pnl_basis` and `min_quality`, with an optional rolling
250-day exception series.

**Independent Test**: For a hand-constructed set of estimates/outcomes with a known exception
count, request the backtest and verify every statistic against an independently calculated
value (spec.md's Independent Test for US2); verify the Basel 0–4/5–9/10+ zone reproduction at
N=250, 99% exactly (SC-003).

### Tests for User Story 2 (write first, must fail)

- [ ] T014 [P] [US2] Write `tests/unit/test_var_backtest_stats.py` covering, against hand-worked
  values from `docs/proposals/value-at-risk.md` §4.3 and spec.md's scenarios, every numeric
  assertion compared **within 1e-9 relative tolerance** for decimals and **exactly** for
  integers/strings (SC-002):
  `kupiec_pof(n, x, alpha)` at `x=0`, `x=N` (the `0 ln 0 = 0` convention) and a mid-range value,
  with `p = math.erfc(math.sqrt(lr/2))`; `N=0` returns `(None, None)`.
  `christoffersen_independence()` on a hand-built indicator sequence with a known gap (asserting
  the gap breaks the transition chain, FR-014) and with `N<2` returning `(None, None)`.
  `conditional_coverage()` combining both, returning `None` if either input is `None`, with
  `p = math.exp(-lr/2)`.
  `traffic_light_zone(n=250, x, alpha=0.01)` returns `"green"` at `x=4`, `"yellow"` at `x=7`,
  `"red"` at `x=11` (SC-003, SC-002), and `None` at `n=0`.
  `var_stability()` over a list of `(var_value, holdings_changed)` pairs excludes
  holdings-changed transitions and returns `None` with fewer than 2 qualifying log-changes.
  `rolling_exception_counts(indicators, window=250)` returns `[]` for fewer than 250 entries and
  one point per date from the 250th entry onward otherwise.
- [ ] T015 [P] [US2] Write `tests/unit/test_var_backtest_service.py` against a seeded
  `VarRepository`. Cover: exception count matches the number of stored days where the chosen
  PnL basis's loss exceeds that day's stored VaR (spec.md scenario); `pnl_basis="ladder"` versus
  the default `"hypothetical"` changes which days count as exceptions when the two disagree;
  `min_quality="ok"` narrows the observation count to only `ok`-quality days; `insufficient`
  and pending-outcome days are excluded from the observation count regardless of `min_quality`
  (FR-011); a day excluded by `min_quality` breaks the independence transition chain for its
  neighbours (FR-014); requesting `rolling=True` over 500 seeded days returns a 250-point rolling
  series; an account/range with zero qualifying observations returns `observation_count=0` and
  every rate/statistic `None` except the counts (spec.md Edge Cases); the reported
  `exception_dates` list matches the seeded exception days exactly (FR-013); `mean_var_gbp`
  equals the mean of `var_gbp` over the observation set exactly (FR-013). **FR-023 guard**: pass
  a `VarRepository` test double whose `commit()` and `write_run()` raise `AssertionError` if
  called, and assert `get_backtest()` never calls either.
- [ ] T016 [P] [US2] Add the eight Gherkin scenarios from spec.md's User Story 2 to
  `tests/features/var_series_backtest_api.feature` under an `@us2` tag, with step definitions in
  `tests/steps/var_series_backtest_api_steps.py`.

### Implementation for User Story 2

- [ ] T017 [US2] Create `app/services/var/backtest.py`: pure functions `kupiec_pof`,
  `christoffersen_independence`, `conditional_coverage`, `traffic_light_zone`, `var_stability`,
  `rolling_exception_counts`, implementing research.md §8 exactly (stdlib `math.erfc`,
  `math.exp`, `math.lgamma` only; no numpy/pandas dependency in this module, mirroring
  `engine.py`'s pure-function convention), making T014 pass.
- [ ] T018 [US2] Create `app/services/var/var_backtest_service.py`: `VarBacktestService.
  get_backtest(account_name, start, end, lookback, confidence_levels_bp, pnl_basis, min_quality,
  rolling, today) -> VarBacktestResponse`. Uses `resolve_window()` (T007), reads
  `VarRepository.read_estimates()`/`read_outcomes()`, builds the observation set per research.md
  §6, calls `backtest.py`'s functions (T017) per confidence level, and always includes
  `status`/`runs` in `_links` (making T015 pass).
- [ ] T019 [US2] Add `GET /accounts/{account_name}/risk/var/backtest` to `app/api/risk_var.py`:
  query params `start`, `end`, `lookback`, `confidence` (same parsing as T012), `pnl_basis`
  (`hypothetical`|`ladder`, default `hypothetical`), `min_quality` (`ok`|`degraded`, default
  `degraded`), `rolling` (bool, default `false`) — an unsupported `pnl_basis` or `min_quality`
  raises `InvalidVarQueryError` naming the supported values (FR-021); a
  `_get_var_backtest_service` dependency factory; a structlog `var_backtest_request` event
  logging `account_name`, `lookback`, `pnl_basis`, `min_quality`, and each confidence level's
  `observation_count`/`exception_count` (making T016's scenarios pass).
- [ ] T020 [US2] Extend `tests/unit/test_risk_var_series_openapi.py` to assert the backtest
  endpoint's path and `VarBacktestResponse` schema are present in the live `/openapi.json`.

**Checkpoint**: User Stories 1 AND 2 both work independently — the backtest endpoint reproduces
the Basel traffic-light thresholds exactly and all statistics match hand-worked values.

---

## Phase 5: User Story 3 - Discover the Available Method, Look-backs and Measures (Priority: P2)

**Goal**: `GET /v1/risk/var/methods` describes the configured method, look-backs, confidence
levels and measures, requiring no account.

**Independent Test**: Request the methods endpoint with no account ingested anywhere and verify
it lists the configured look-backs (with the headline marked), confidence levels and measures.

### Tests for User Story 3 (write first, must fail)

- [ ] T021 [P] [US3] Write `tests/unit/test_var_methods_service.py`: `build_methods_response(
  VarSettings())` returns one `MethodLookback` per configured look-back with `business_days`
  matching `settings.lookbacks`, exactly one with `is_headline=True` matching
  `settings.headline_lookback`, `confidence_levels_bp` equal to `settings.
  confidence_levels_bp`, a non-empty static `measures` list, and `_links.self` set — with no
  repository or I/O dependency (pass only `VarSettings`).
- [ ] T022 [P] [US3] Add the two Gherkin scenarios from spec.md's User Story 3 to
  `tests/features/var_series_backtest_api.feature` under an `@us3` tag, with step definitions
  asserting the endpoint succeeds even when no account has ever been ingested in the test
  fixture's data directory.

### Implementation for User Story 3

- [ ] T023 [US3] Create `app/services/var/var_methods_service.py`: `build_methods_response(
  settings: VarSettings) -> VarMethodsResponse`, a pure function per research.md §9, making T021
  pass.
- [ ] T024 [US3] Add `GET /risk/var/methods` to `app/api/risk_var.py` (no account path
  parameter, no validation beyond FastAPI's own routing), depending only on `Settings` via
  `get_settings`, making T022's scenarios pass.

**Checkpoint**: All three read endpoints exist and are independently functional.

---

## Phase 6: User Story 4 - Clear Handling of Invalid Requests (Priority: P2)

**Goal**: An unknown account, unsupported `lookback`/`confidence`/`pnl_basis`/`min_quality`
value, or invalid date range produces the same predictable, documented error shape the
performance and VaR run endpoints already use.

**Independent Test**: Issue each invalid-request class in spec.md's User Story 4 against the
series and backtest endpoints and verify the documented status code, error type slug, and (for
the new validation type) a `correlation_id` and a message naming the supported values.

### Tests for User Story 4 (write first, must fail)

- [ ] T025 [P] [US4] Add the five Gherkin scenarios from spec.md's User Story 4 to
  `tests/features/var_series_backtest_api.feature` under an `@us4` tag, with step definitions
  asserting: an unsupported `lookback` → 422 `invalid-var-query` naming `1y`/`2y`/`5y`; an
  unsupported `confidence` → 422 `invalid-var-query` naming the configured percentages; an
  unknown account → 404 `account-not-found`; start after end → 422 `invalid-date-range`; an
  account with only a capital ledger (no position ladder) → 422
  `missing-required-source`, all consistent with the performance endpoints (FR-024, SC-006).
- [ ] T026 [P] [US4] Extend `tests/unit/test_var_series_service.py` and
  `tests/unit/test_var_backtest_service.py` with the same five cases at the service layer
  (bypassing the router), asserting the exact exception type raised in each case.

### Implementation for User Story 4

- [ ] T027 [US4] Review `app/api/risk_var.py`'s query-parameter validation added in T012/T019;
  ensure every `InvalidVarQueryError` message explicitly lists the currently configured valid
  values (not a generic "invalid value" message), satisfying FR-009/FR-021/SC-006. Adjust
  messages only if T025/T026 reveal a gap — this story should require no new production code
  beyond what US1–US3 already built, since every error path is already wired by `resolve_window()`
  (T007), `InvalidVarQueryError` (T005), and the router validation (T012, T019).

**Checkpoint**: Every invalid-request class across both account-scoped endpoints is covered and
passes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final verification across all four stories.

- [ ] T028 [P] Write `tests/unit/test_var_series_performance.py` (SC-004): seed ~2,700 dates ×
  3 look-backs × 3 confidence levels into `estimates.csv`/`outcomes.csv` via `VarRepository.
  commit()` (mirroring feature 012's `test_performance.py` seeding pattern), then assert
  `VarSeriesService.get_series()` and `VarBacktestService.get_backtest()` (with `rolling=True`)
  each return in under 2 seconds — the budget is achievable because neither reads the ladder
  file (research.md §1).
- [ ] T029 [P] Update `README.md`: add the three new endpoints to the capability table; document
  `var.headline_lookback` alongside the existing `var:` config block; note the `invalid-var-query`
  error type in the error-type table.
- [ ] T030 [P] Run every step of `quickstart.md` manually against a running service with at
  least one completed feature-012 run, confirming each expected response shape.
- [ ] T031 Run `mypy --strict app/`, `ruff check app/ tests/`, `ruff format --check`, and the
  full `pytest` suite; fix any failure before marking this feature complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (every story needs
  `headline_lookback`, `InvalidVarQueryError`, the response models, and `resolve_window()`).
- **User Stories (Phase 3–6)**: All depend on Foundational completion.
  - US1 and US2 are both P1 and independent of each other (different endpoints, different
    service files); they share only the Foundational artifacts and can proceed in parallel.
  - US3 depends only on Foundational (it needs no `resolve_window()` or store read at all).
  - US4 depends on US1 and US2 being implemented (it tests their validation paths) — it adds no
    new production code of its own except a review/adjustment pass.
- **Polish (Phase 7)**: Depends on all four stories being complete.

### Within Each User Story

- Tests MUST be written and seen to fail before implementation starts.
- Pure functions (`backtest.py`) before the service that calls them.
- Service before the router endpoint.
- Router endpoint before its OpenAPI-presence test.

### Parallel Opportunities

- All Phase 2 test-writing tasks (T002, T004, T006, T008) can run in parallel — different files.
- US1 (T009–T013) and US2 (T014–T020) can be implemented in parallel by different
  contributors once Phase 2 is complete, since they touch disjoint files except the shared
  `risk_var.py` router (coordinate on that one file, or land US1's endpoint first).
- US3 (T021–T024) can proceed in parallel with US1/US2 — it shares no files with either.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all Foundational test-writing tasks together:
Task: "Write tests/unit/test_var_settings.py headline_lookback cases"
Task: "Write tests/unit/test_var_problem_details.py InvalidVarQueryError case"
Task: "Write tests/unit/test_var_window.py resolve_window() cases"
Task: "Write tests/unit/test_var_series_models.py response-model cases"
```

## Parallel Example: User Story 1 and User Story 2

```bash
# Once Phase 2 is complete, these can proceed on separate branches/sessions:
Task: "Implement VarSeriesService + GET .../risk/var (T009-T013)"
Task: "Implement backtest.py + VarBacktestService + GET .../risk/var/backtest (T014-T020)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks everything).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: the series endpoint works end-to-end against a seeded store.
5. This alone unblocks a browser chart showing forecast VaR alongside realised PnL — the
   feature's stated core motivation.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. User Story 1 → test independently → series endpoint demo-able (MVP).
3. User Story 2 → test independently → backtest endpoint demo-able.
4. User Story 3 → test independently → methods endpoint demo-able.
5. User Story 4 → confirms every invalid-request class across US1/US2 behaves predictably.
6. Polish → README, quickstart validation, full quality-gate pass.

---

## Notes

- [P] tasks = different files, no dependency on an incomplete task.
- [Story] label maps task to specific user story for traceability.
- Verify every test fails before implementing (Principle I, non-negotiable).
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.
- Avoid: vague tasks, same-file conflicts between US1 and US2's shared edits to
  `risk_var.py` (land one before starting the other's router edit, or rebase), and any
  temptation to make the series/backtest endpoints read the ladder file directly — they must
  not (see `var_window.py`'s contract in T006/T007).
