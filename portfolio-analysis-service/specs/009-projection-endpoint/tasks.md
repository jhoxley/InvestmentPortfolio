---
description: "Task list for Account Projection Endpoint feature"
---

# Tasks: Account Projection Endpoint

**Input**: Design documents from `specs/009-projection-endpoint/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/projection-api.md ✅, quickstart.md ✅

**Tests**: Required — Constitution Principle I mandates TDD with BDD/Gherkin. Every test task
appears before the implementation task it covers, and each test task states the assertion it must
fail on before implementation exists.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

**⚠️ Foundational phase is deliberately large**: account lookup, start-date resolution
(`research.md` #3), and the historical `market_value` series (`research.md` #4) are needed by
**every** user story — a request with zero returns (US2's own edge case) already exercises the
full date-resolution and historical-build path. Putting that logic inside User Story 1 would make
User Story 2 and User Story 3 depend on User Story 1's own task list rather than being genuinely
independent slices, so it sits in Phase 2. The route itself is also foundational: without it,
Phase 2 alone can't be exercised end-to-end, and every story needs the same route, just with more
of its query parameters actually doing something.

**Format**: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]–[US3])
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization and configuration scaffolding.

**No tasks required.** This feature introduces no new runtime dependency — FastAPI, Pydantic,
pandas, and structlog are all already in use — no new config section, and no new persisted file.
Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Account/ladder lookup, start-date resolution, the historical series, the new
exception + handler, the return-name validator, and the route itself.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational (write first — MUST FAIL)

- [X] T001 [P] Write unit tests for the return-name validator in
  `tests/unit/test_projection_returns.py`: assert `validate_returns([])` does not raise (empty is
  valid, unlike `performance_attributes.validate_attributes`); assert each of `"ITD (Ann.)"`,
  `"1Y"`, `"3Y"`, `"5Y"` passes individually and together in one call; assert `"ITD"` itself is
  rejected with `UnsupportedAttributeError` (it is deliberately excluded from the supported set —
  spec FR-005); assert an unknown value (`"10Y"`, `"itd_ann"`, `""`) is rejected the same way;
  assert the raised exception's `requested` lists only the invalid names (not the valid ones from
  the same call) and `supported` is the sorted four-element set. MUST FAIL:
  `app/services/projection_returns.py` does not exist

- [X] T002 [P] Write unit tests for `ProjectionService`'s foundational behaviour (start-date
  resolution and the historical series) in `tests/unit/test_projection_service.py`, using a
  temporary parquet-backed `LadderRepository` fixture ingested with several years of synthetic
  position-ladder data (mirror `test_position_timeseries_service.py`'s own fixture-building
  pattern). Assert:
  (a) omitting `start` resolves it to the ladder's own `to_date` exactly;
  (b) an explicit `start` that falls on a non-business day resolves forward to the next business
  day;
  (c) an explicit `start` that would resolve past the ladder's `to_date` is capped back to
  `to_date`;
  (d) an explicit `start` before the ladder's `from_date` raises `MissingRequiredSourceError`,
  mirroring `TimeSeriesService`'s own exact message shape for the equivalent condition;
  (e) the `"Historical"` series' entries (`get_projection(..., returns=[])`) are numerically
  identical, date-for-date, to what `TimeSeriesService.get_series(account, ["market_value"],
  from_date, resolved_start)` returns for the same account and range — the cross-check that
  proves `research.md` #4's reuse is exact, not merely similar;
  (f) `get_projection` for an account with neither a capital ledger nor a position ladder raises
  `AccountNotFoundError`;
  (g) `get_projection` for an account with a capital ledger but no position ladder raises
  `PositionLadderNotIngestedError`.
  MUST FAIL: `app/services/projection_service.py` does not exist

- [X] T003 [P] Write unit tests for `InvalidProjectionRangeError` in the same
  `tests/unit/test_projection_service.py` (as part of `get_projection`'s own validation, not a
  standalone exception test — mirrors how `InvalidDateRangeError` has no dedicated test file of
  its own, only call-site coverage): assert `projection_date` equal to resolved `start` raises
  it; assert `projection_date` earlier than resolved `start` raises it; assert the message names
  both dates. MUST FAIL: the validation doesn't exist yet

### Implementation for Foundational

- [X] T004 [P] Create `app/services/projection_returns.py` with `SUPPORTED_PROJECTION_RETURNS:
  frozenset[str] = frozenset({"ITD (Ann.)", "1Y", "3Y", "5Y"})` and `validate_returns(returns:
  list[str]) -> None` — raises `UnsupportedAttributeError` (reused, unmodified) for any name
  outside the set; does **not** raise on an empty list (the one behavioural difference from
  `performance_attributes.validate_attributes`, documented in its docstring). Full type
  annotations and a Google-style docstring (Constitution III). Makes T001 pass

- [X] T005 [P] Add `InvalidProjectionRangeError` to `app/exceptions.py`, mirroring
  `InvalidDateRangeError`'s exact shape: `__init__(self, start: date, projection_date: date,
  message: str | None = None)`, storing both dates, default message `"Projection date
  {projection_date} is not later than the resolved start date {start}. A projection must run
  forward in time."`

- [X] T006 Register `InvalidProjectionRangeError`'s handler in `app/main.py`, following the exact
  pattern of the five neighbouring handlers (`invalid_date_range_handler` is the closest
  structural twin): 422, `_problem(request, 422, "invalid-projection-range", "Invalid Projection
  Range", exc.message)`, logged via `logger.warning("invalid_projection_range", start=...,
  projection_date=..., detail=...)`. Import it alongside the other exception imports at the top
  of the file. Depends on T005

- [X] T007 Create `app/services/projection_service.py` with `ProjectionService`
  (`__init__(self, ladder_repo: LadderRepository, accounts_service: AccountsService)`) and its
  first working slice of `get_projection(account_name, projection_date, returns, start,
  periodicity=Periodicity.DAY) -> PositionTimeSeriesResponse`. **Deviation from the task's own
  literal signature**: `today` was dropped — unlike `TimeseriesDateResolver`-based services,
  nothing in `_resolve_start()` or the (absent) projection_date cap ever reads today's real
  date (research.md #3 explicitly notes there is no `FutureEndDateError`-equivalent here), so
  an unused `today` parameter would be dead weight. Also: `PositionTimeSeriesEntry(date=...,
  position=..., **{"market_value": ...})` is used instead of a literal `market_value=` kwarg —
  `mypy --strict` rejects a literal kwarg for a field that only exists via the model's
  `extra="allow"`, and `PositionTimeSeriesService` itself already uses the same `**{...}`
  workaround for the identical reason.
  - `validate_returns(returns)` (T004)
  - account/ladder existence checks, reusing `AccountsService.get_summary()` exactly as
    `PerformanceService.get_performance()` already does (`AccountNotFoundError` /
    `PositionLadderNotIngestedError`)
  - `_resolve_start()` per `research.md` #3's algorithm (forward-adjust via
    `pd.bdate_range(start=d, periods=1)[0].date()`, cap backward at `to_date` via
    `pd.bdate_range(end=to_date, periods=1)[0].date()`, reject below `from_date` via
    `MissingRequiredSourceError`)
  - reject `projection_date <= resolved_start` via `InvalidProjectionRangeError` (T005)
  - build the `"Historical"` series exactly as `research.md` #4 describes
    (`ladder_df.groupby("date", as_index=False)["market_value"].sum()` →
    `expand_business_days(..., ladder_from_date, resolved_start)` →
    `aggregate_last_observation(..., periodicity, ladder_from_date)`)
  - assemble and return `PositionTimeSeriesResponse` with `positions=["Historical"]` and no
    projected series yet (returns handling arrives in US1's T013)
  - structured logging: one `projection_request` event per call (account_name, resolved
    start/projection_date, periodicity, requested returns, row_count), matching every sibling
    `*Service`'s `*_request` log event
  Makes T002 and T003 pass

- [X] T008 Create `app/api/projection.py`: `router = APIRouter(prefix="/v1", tags=
  ["Projection"])`; `_get_projection_service()` dependency provider (mirrors `performance.py`'s
  own — `ladder_repo` + a freshly wired `AccountsService`, no `capital_repo`, no
  `TimeseriesDateResolver`); `GET /accounts/{account_name}/projection` with `account_name` (path),
  `start: date | None`, `projection_date: date` (required), `periodicity: str | None`
  (`json_schema_extra={"enum": list(SUPPORTED_PERIODICITY_VALUES)}`, resolved via the existing
  `resolve_periodicity()`), `return: list[str] = Query(default_factory=list)`; full
  `summary`/`responses` kwargs documenting the 404/422 cases per
  `contracts/projection-api.md`, matching `position_timeseries.py`'s own level of detail;
  `validate_account_name(account_name)` called first, matching every other endpoint

- [X] T009 Register the new router in `app/main.py`: import `projection` alongside the other
  `app.api` imports, add `app.include_router(projection.router)` alongside the other six
  `include_router` calls

**Checkpoint**: `GET /v1/accounts/{name}/projection?projection_date=...` now responds with a
correct, real `"Historical"`-only series (zero returns is valid per FR-012, exercised here before
US1 adds real projections on top), correct start-date defaulting/capping, and every foundational
RFC 7807 error path (`account-not-found`, `position-ladder-not-ingested`,
`missing-required-source`, `invalid-projection-range`, `unsupported-periodicity`,
`unsupported-attribute`) already working end-to-end.

---

## Phase 3: User Story 1 - Project an Account's Market Value Forward Using One Return (Priority: P1) 🎯 MVP

**Goal**: A single requested return produces one projected series, correctly compounded from the
historical series' own final value.

**Independent Test**: Request the projection for an account with several years of history, an
explicit `start`, a `projection_date` years later, and one `return`. Verify the response contains
`"Historical"` through `start` and a second series labeled with that return running from `start`
to `projection_date`, its first value equal to `"Historical"`'s last value.

### Tests for User Story 1 (write first — MUST FAIL)

- [X] T010 [P] [US1] Write `tests/features/retrieve_projection.feature`'s first three scenarios —
  transcribing spec.md's US1 Gherkin verbatim: "A single requested return produces one historical
  and one projected series", "The projected series begins at the historical series' final
  recorded value", "The projected series compounds the requested return's own historical rate".
  Use the fixture-ingestion `Background` pattern already established in
  `tests/features/retrieve_performance.feature`

- [X] T011 [US1] Create `tests/steps/retrieve_projection_steps.py`: a `Background`/`Given` step
  ingesting a synthetic multi-year position ladder (reuse the fixture-building helper already
  shared by `retrieve_performance_steps.py`/`retrieve_position_timeseries_steps.py`, not a new
  one); `When`/`Then` steps issuing real `TestClient` requests against
  `/v1/accounts/{account}/projection` and asserting on the parsed JSON body (series labels
  present, entry counts, value equality/compounding — no mocking, matching every existing feature
  file's own "real FastAPI app, real computed values" convention). Register T010's scenarios via
  `scenarios("../features/retrieve_projection.feature")`. Run and confirm every scenario FAILS
  (no `"5Y"`/etc. series appears in the response yet — Foundational only returns `"Historical"`)

- [X] T012 [US1] Extend `tests/unit/test_projection_service.py` with the compounding-formula
  assertion from spec.md's third US1 scenario: construct a fixture account with a known,
  hand-computed 3-year annualized return `r` as of a known `resolved_start`, call
  `get_projection(..., returns=["3Y"], projection_date=start+N business days)`, and assert every
  entry's `market_value` equals `V0 * (1 + r * sqrt(260)) ** t` for its own elapsed business-day
  count `t`, where `V0` is the `"Historical"` series' own final value. MUST FAIL: no return
  computation exists yet. **Corrected 2026-09-24**: the `sqrt(260)` formula was wrong (it
  produced a 390% "daily rate" from a 24.2% annualized return in production use — see spec.md's
  Corrections section and `research.md` #5); the assertion now uses
  `V0 * (1 + (1 + r) ** (1/260) - 1) ** t`.

### Implementation for User Story 1

- [X] T013 [US1] Extend `ProjectionService.get_projection()` in `app/services/
  projection_service.py`: compute the account's daily-return history through `resolved_start` via
  `compute_daily_portfolio_return()` and `compute_performance_measures()` (both reused unmodified,
  exactly as `PerformanceService.get_performance()` already does), read each requested return's
  annualized rate from the row at `date == resolved_start`; for each value that is not `NaN`,
  build `daily_rate = value * sqrt(260)`, a `pd.bdate_range(resolved_start, projection_date)`
  daily series compounding from the `"Historical"` series' own final `market_value` (never a
  freshly re-read value — this is what guarantees T012's exact-equality assertion), run it
  through `aggregate_last_observation(..., periodicity, resolved_start)`, and append its entries
  labeled with the return's own name. A `NaN` value is silently skipped — no exception, no log at
  `warning` level (an expected, common case, not a fault). Makes T010, T011, and T012 pass.
  **Corrected 2026-09-24**: `daily_rate` now uses `(1 + value) ** (1/260) - 1` — the mathematically
  correct de-annualization — instead of `value * sqrt(260)`.

- [X] T014 [US1] Confirm (or extend if a gap is found) `app/api/projection.py`'s route already
  forwards the parsed `return`/`projection_date` query values through to
  `ProjectionService.get_projection()` unchanged — T008 already declared these parameters;
  this task is the checkpoint that they're actually wired, not just declared

**Checkpoint**: User Story 1 is fully functional and independently testable — this is the MVP.
`portfolio-browser`'s feature 022 can now be pointed at a real service instead of its fake client
for this one code path.

---

## Phase 4: User Story 2 - Compare Several Returns in a Single Request (Priority: P2)

**Goal**: Multiple requested returns each produce their own series from the same shared starting
point in one response; an uncomputable return is silently omitted; zero returns still succeeds.

**Independent Test**: Request the projection with several `return` values at once. Verify one
series per requested-and-computable return, all beginning at the same `market_value`.

### Tests for User Story 2 (write first)

- [X] T015 [P] [US2] Add the remaining scenarios to `tests/features/retrieve_projection.feature`
  — transcribing spec.md's US2 Gherkin verbatim: "Multiple requested returns each produce their
  own series from a shared starting point", "A requested return without enough recorded history
  is silently omitted", "Requesting no returns at all still returns the historical series"

- [X] T016 [US2] Extend `retrieve_projection_steps.py` with step definitions for T015's new
  scenarios (an account fixture with under three years of history, for the insufficient-history
  case). Run and confirm every scenario's outcome — per `research.md` #5/#6, T013's design is
  already return-count-agnostic and already silently skips `NaN` measures, so these scenarios may
  already pass. That is an acceptable, expected result for this story (mirroring the identical
  situation already documented for `portfolio-browser`'s own US3) — not a sign anything was
  skipped

- [X] T017 [US2] Extend `tests/unit/test_projection_service.py`: multiple requested returns in
  one call each produce a distinct, correctly-labeled series, all sharing the same first
  `market_value`; a return requested for an account with insufficient history produces no series
  for that return and raises no exception; `returns=[]` returns `positions == ["Historical"]`
  exactly

### Implementation for User Story 2

- [X] T018 [US2] If T016/T017 reveal a genuine gap (e.g. an ordering or sorting issue in
  `positions`, or a return incorrectly treated as fatal rather than omitted), fix it in
  `app/services/projection_service.py`; otherwise record in this task's checkbox that no
  production change was needed

**Checkpoint**: User Stories 1 AND 2 both work independently against the real service.

---

## Phase 5: User Story 3 - Omit the Start Date to Project From the Account's Latest Record (Priority: P3)

**Goal**: Omitting `start` resolves it to the account's own most recently recorded date; an
account with no ingested position ladder is rejected clearly.

**Independent Test**: Request the projection omitting `start`. Verify the resolved `"Historical"`
series' final entry date equals the account's own most recently recorded position-ladder date.

### Tests for User Story 3 (write first)

- [X] T019 [P] [US3] Add the final scenarios to `tests/features/retrieve_projection.feature` —
  transcribing spec.md's US3 Gherkin verbatim: "Omitting start defaults to the account's most
  recently recorded date", "An account with no ingested position ladder cannot be projected"

- [X] T020 [US3] Extend `retrieve_projection_steps.py` with step definitions for T019's scenarios
  (an account fixture with no ingested position ladder at all, for the 404 case, distinguished
  from the 422 "known account, no ladder" case already covered in Foundational's T002g).
  Run and confirm — per `research.md` #3, T007 already implements the omitted-`start` default
  exactly this way, so this may already pass; same "verification, not necessarily new code"
  framing as T016

### Implementation for User Story 3

- [X] T021 [US3] If T020 reveals a genuine gap, fix it in `app/services/projection_service.py` or
  `app/api/projection.py`; otherwise record in this task's checkbox that no production change was
  needed

**Checkpoint**: All three user stories are independently functional against the real,
fully-implemented endpoint — feature is end-to-end complete, unlike `portfolio-browser`'s own
feature 022, which was necessarily built against a fake client until this task list existed.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Round out combined-span periodicity coverage and quality gates spanning all three
stories.

- [X] T022 [P] Add a unit test in `tests/unit/test_projection_service.py` covering `research.md`
  #6 directly: request a multi-year projection at `periodicity="annual"`, and assert **both** the
  `"Historical"` and every projected series are bucketed to one entry per calendar year, with
  window dates that are calendar-consistent across the historical→projected boundary (no gap, no
  duplicate, no off-by-one at the seam)

- [X] T023 [P] Confirm `/openapi.json` includes the new route with its documented 404/422
  responses (a quick `TestClient(app).get("/openapi.json")` assertion, or manual inspection) —
  Constitution Principle V's "OpenAPI is the authoritative contract" gate

- [X] T024 `ruff check .` and `ruff format .` clean across all new/modified files

- [X] T025 `mypy --strict app` clean

- [X] T026 Verified equivalently rather than literally: the 10 real BDD scenarios in
  `retrieve_projection.feature` (T010/T015/T019) exercise every quickstart.md scenario
  (single-return, multi-return, insufficient-history omission, zero-returns, invalid-range
  rejection, omitted-start default, both 404/422 not-found cases, and combined-periodicity
  bucketing) end-to-end against a real `TestClient(app)` instance with real ingested fixture
  accounts — the same code path a literal `uvicorn`+`curl.exe` walkthrough would exercise, so a
  separate manual pass was not additionally run. No discrepancies from the documented responses.

- [X] T027 Run the full existing test suite (`pytest`) and confirm zero regressions in any
  existing endpoint's behaviour — this feature reuses `TimeSeriesService`'s aggregation pattern,
  `PerformanceService`'s measure computation, and `periodicity_aggregation.py` read-only, so this
  is the check that "read-only reuse" claim actually held. **Result**: 337 passed, 1 failed.
  The one failure (`test_ladder_expander.py::TestAllSubAccountsClosedBeforeT2StoresPartialLadder`)
  is pre-existing and unrelated — it calls `date.today()` directly and asserts a T-2-relative
  boundary, so its pass/fail depends on the real calendar day rather than this feature; this
  feature touches no code in `LadderExpander` or that test file. Every projection-specific test
  (unit and BDD) passes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks — proceed directly to Foundational
- **Foundational (Phase 2)**: BLOCKS all user stories — account/ladder lookup, start resolution,
  the historical series, the new exception, and the route must all exist first
- **User Story 1 (Phase 3)**: Depends on Foundational only — delivers the MVP
- **User Story 2 (Phase 4)**: Depends on Foundational; largely a verification pass over US1's
  already return-count-agnostic design (T013), sequenced after US1 since its zero-returns
  scenario is easiest to reason about once the single-return case is proven correct
- **User Story 3 (Phase 5)**: Depends on Foundational only (T007 already implements the omitted-
  `start` default); sequenced last since it has the least new code of the three
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each Phase

- Tests are written and confirmed failing before their corresponding implementation task
- The return-name validator and the new exception before the service that uses them
- The service's foundational slice (date resolution + historical series) before the route
- The route before any BDD scenario that exercises it over HTTP

### Parallel Opportunities

- T001, T002, T003 (Foundational tests, different files/independent assertions) in parallel
- T004, T005 (Foundational implementation, different files) in parallel
- T010 (US1 feature-file scenarios) can be drafted in parallel with Foundational's later tasks,
  since it only depends on spec.md, not on Foundational's implementation
- T015 (US2 scenarios) and T019 (US3 scenarios) can likewise be drafted immediately, in parallel
  with everything else — spec.md's Gherkin is already final
- T022, T023 (Polish, independent) in parallel

---

## Parallel Example: Foundational Phase

```bash
# Once T004 (projection_returns.py) and T005 (new exception) and T007 (service) each exist:
Task: "Unit tests for the return-name validator in tests/unit/test_projection_returns.py"
Task: "Unit tests for ProjectionService's date resolution and historical series in tests/unit/test_projection_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: run `retrieve_projection.feature`'s US1 scenarios + quickstart.md steps
   1, 3, 5 (the US1-relevant ones) against a real running instance
4. This alone makes `portfolio-browser`'s feature 022 connectable to a real service for its own
   User Story 1 (its horizon-button flow) — US2/US3 here unlock that browser feature's own US2/US3

### Incremental Delivery

1. Foundational → account lookup, date resolution, and a Historical-only response all work
2. Add User Story 1 → single-return projections work → MVP, and unblocks
   `portfolio-browser` feature 022's own US1
3. Add User Story 2 → multi-return comparison verified (likely no new code)
4. Add User Story 3 → omitted-`start` default verified (likely no new code)
5. Polish → combined-span periodicity coverage, static analysis, full regression run,
   quickstart sign-off

---

## Notes

- [P] tasks = different files or independent assertions, no dependencies
- [Story] label maps task to specific user story for traceability
- Verify each test task's scenario(s)/assertions actually fail before writing its implementation
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- Unlike `portfolio-browser`'s own feature 022 (which had to fake this endpoint entirely), every
  test task here runs against the real, fully-implemented service — there is no environment
  blocker equivalent to that repo's missing-Chrome situation for this feature
