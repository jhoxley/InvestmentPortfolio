# Tasks: Projection Start Alignment

**Input**: Design documents from `specs/010-projection-start-alignment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/projection-api-delta.md
**Tests**: REQUIRED (Constitution Principle I — tests written first and seen failing before implementation)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 from spec.md

## Phase 1: Setup

- [X] T001 Run the baseline `.venv/Scripts/python -m pytest tests/unit/test_projection_service.py tests/steps/retrieve_projection_steps.py` and record that it is green before any change

*No foundational phase: no new dependencies, models or infrastructure.*

## Phase 2: User Story 1 — Regular projection points for non-daily periodicity (Priority: P1) 🎯 MVP

**Goal**: For non-daily periodicity with an off-boundary start, projected series begin at the next window start and end at the last window start on or before `projection_date`.

**Independent Test**: Monthly request with mid-month start → projected series has no start-date row and first row is the next month's first business day (spec SC-002).

### Tests for User Story 1 (write first; MUST FAIL before T007)

- [X] T002 [P] [US1] Add Gherkin scenarios to `tests/features/retrieve_projection.feature` (tag `@us1`, start dates chosen mid-period on the existing `proj-portfolio` fixture): (a) monthly with mid-month start omits the start-date row and first row is the next month start; (b) historical series still ends at its final data point / start date; (c) quarterly begins at next quarter start; (d) weekly with a mid-week start begins at the next Monday; (e) off-boundary `projection_date` yields no row at `projection_date` and last row is the last window start on or before it
- [X] T003 [US1] Add matching step definitions to `tests/steps/retrieve_projection_steps.py` (new `When` step taking a periodicity, and `Then` steps asserting first/last date of a series and absence of a given date); reuse existing steps where possible (depends on T002)
- [X] T004 [P] [US1] Add unit tests to `tests/unit/test_projection_service.py` for `ProjectionService.get_projection` with `Periodicity.MONTH`, `QUARTER`, `WEEK`, `ANNUAL` and an off-boundary start: assert no projected row dated `resolved_start`, first row equals the next window-start business day, dates are consecutive window starts, and projected values equal the pre-change values on the retained dates (FR-007, compute expected via the daily compounding formula)
- [X] T005 [P] [US1] Add unit test in `tests/unit/test_projection_service.py` for the empty case: monthly, `projection_date` earlier than the next window start → `get_projection` returns no rows for the return and the return name is absent from `positions`
- [X] T006 [US1] Update `TestPeriodicityIsAppliedToBothHistoricalAndProjectedLegs` in `tests/unit/test_projection_service.py` (~line 452) so its overlap assertion no longer permits the start date to appear in the projected series for `ANNUAL` when the start is mid-year. Confirm T002–T006 fail for the expected reason (extra start-date row) before continuing

### Implementation for User Story 1

- [X] T007 [US1] In `app/services/projection_service.py`, add a fully typed, docstringed private helper (e.g. `_starts_on_window_boundary(resolved_start, periodicity) -> bool`) that returns True for `Periodicity.DAY`, otherwise compares `resolved_start` with the first business day on or after `pd.Period(resolved_start, PERIOD_ALIAS[periodicity]).start_time.date()`
- [X] T008 [US1] In `ProjectionService._build_projected_series` (`app/services/projection_service.py`), after `aggregate_last_observation`, drop rows with `date <= resolved_start` when `_starts_on_window_boundary` is False; update the method docstring to describe the trim. Do NOT modify `app/services/periodicity_aggregation.py`
- [X] T009 [US1] Run T002–T006 tests and confirm they now pass; confirm `tests/unit` tests for time series, position time series and performance are unaffected

**Checkpoint**: The reference request (monthly, start 2026-09-22, projection_date 2026-12-31) returns `3Y` starting 2026-10-01.

## Phase 3: User Story 2 — Boundary start or daily periodicity unchanged (Priority: P2)

**Goal**: No regression when the start is on a boundary or periodicity is `day`.

**Independent Test**: Monthly with start on a month's first business day, and daily with any start, still begin at the start date.

### Tests for User Story 2

- [X] T010 [P] [US2] Add Gherkin scenarios to `tests/features/retrieve_projection.feature` (tag `@us2`): (a) monthly with start on the first business day of a month retains the start-date row; (b) daily periodicity retains the start-date row; (c) monthly with a start on a Monday whose month began on the preceding weekend retains the start-date row; add any needed steps in `tests/steps/retrieve_projection_steps.py`
- [X] T011 [P] [US2] Add unit tests in `tests/unit/test_projection_service.py` for the same three cases plus weekly with a Monday start, asserting `projected_entries[0].date == resolved_start`

*These should pass against the T008 implementation (they guard the trim condition); if any fail, fix `_starts_on_window_boundary` in `app/services/projection_service.py`.*

**Checkpoint**: All US1 and US2 scenarios pass.

## Phase 4: Polish & Cross-Cutting

- [X] T012 [P] Update the endpoint's OpenAPI description in `app/api/projection.py` with the start/end alignment rule from `contracts/projection-api-delta.md`; verify it renders in `/docs`
- [X] T013 [P] Append a short note to `specs/009-projection-endpoint/contracts/projection-api.md` (or link) pointing to `specs/010-projection-start-alignment/contracts/projection-api-delta.md`
- [X] T014 Run `.venv/Scripts/python -m ruff check .`, `-m ruff format --check .`, `-m mypy --strict app`, then the full `-m pytest`; all must be clean
- [ ] T015 Execute `quickstart.md` manually against the running service and confirm the three expected outcomes (monthly off-boundary, daily, on-boundary)

## Dependencies & Execution Order

- T001 → all others
- US1: T002/T004/T005 parallel; T003 after T002; T006 after T004; failing-test check (end of T006) → T007 → T008 → T009
- US2 tests (T010, T011) can be written in parallel with US1 tests; they are verified after T008
- Polish (T012–T015) after T009 and T010/T011 pass; T012 and T013 parallel; T014 then T015 last

## Parallel Example

```text
Together: T002 (feature file), T004 (unit tests), T005 (unit tests, different class) , T010, T011
Then sequential: T007 → T008
```

## Implementation Strategy

1. **MVP = US1** (T001–T009): fixes the reported defect.
2. Add US2 guards (T010–T011) to lock in unchanged behaviour.
3. Polish (docs, lint, types, manual check).

FR coverage: FR-001/002/005 → T002–T004, T008; FR-003/004 → T010–T011; FR-006 → T002(b); FR-007 → T004; FR-008 → T004 (multiple returns); FR-009 → T002(e); empty edge case → T005.
