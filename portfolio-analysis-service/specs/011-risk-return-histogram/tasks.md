---
description: "Task list for Risk Endpoints — Daily Return Histogram feature"
---

# Tasks: Risk Endpoints — Daily Return Histogram

**Input**: Design documents from `/specs/011-risk-return-histogram/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅, quickstart.md ✅

**Tests**: Required — Constitution Principle I mandates TDD with BDD/Gherkin. Test tasks appear
before their corresponding implementation tasks in every phase; each test MUST be run and seen to
fail before its implementation task begins.

**Organization**: Tasks are grouped by user story. Foundational work (the shared
`DailyReturnSeriesLoader` extraction) blocks every story because the endpoint cannot exist without
it. Statistics (US2) extend the response model created in US1, so US2 depends on US1.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]–[US4])
- Exact file paths included in all descriptions
- Every new function/class needs full type annotations and a docstring; every implementation
  task ends with `ruff check`, `ruff format`, and `mypy --strict` clean on the touched files.

---

## Phase 1: Setup

**Purpose**: Project initialization.

No tasks required. No new dependency, config section, or pytest marker is introduced; BDD scenarios
reuse the `us1`–`us4` markers already registered in `pyproject.toml`, scoped per file via
`scenarios("return_histogram.feature")`. Proceed to Phase 2.

- [X] T001 Confirm baseline is green before any change: run `.venv/Scripts/python -m pytest tests/unit/test_performance_service.py tests/unit/test_daily_portfolio_return.py tests/features/retrieve_performance.feature` and record that all pass (regression baseline for the shared refactor)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extract the account/date/series acquisition logic from `PerformanceService` into a
shared `DailyReturnSeriesLoader` so the performance and risk endpoints cannot diverge (FR-002,
FR-003, User Story 3).

**⚠️ CRITICAL**: All user story phases depend on this phase being complete, with the T001
baseline tests still green.

- [X] T002 [P] Write failing unit tests for the loader in `tests/unit/test_daily_return_series_loader.py`: (a) returns resolved `(start, end)` and a full `[date, daily_return]` DataFrame from `from_date` through resolved end; (b) raises `AccountNotFoundError` when neither ledger nor ladder exists; (c) raises `MissingRequiredSourceError` (with the caller-supplied attribute label in the message) when only a capital ledger exists; (d) raises `MissingRequiredSourceError` when the resolved start is before the ladder's first date; (e) propagates `FutureEndDateError` and `InvalidDateRangeError` from `TimeseriesDateResolver`; (f) zero-fills business days with no ladder rows (mirrors `compute_daily_portfolio_return`). Reuse the ladder-writing helpers/pattern from `tests/unit/test_performance_service.py`
- [X] T003 Implement `DailyReturnSeriesLoader` in `app/services/daily_return_series_loader.py`: constructor takes `LadderRepository`, `AccountsService`, `TimeseriesDateResolver`; method `load(account_name: str, start: date | None, end: date | None, today: date, attribute_label: str) -> LoadedDailyReturns` where `LoadedDailyReturns` is a small frozen dataclass `(resolved_start: date, resolved_end: date, daily_returns: pd.DataFrame)`. Move the logic verbatim from `PerformanceService.get_performance` (account/source checks, `resolve(...)`, start-before-ladder check, `read_full_df`, `compute_daily_portfolio_return`). Make T002 pass
- [X] T004 Refactor `app/services/performance_service.py` so `PerformanceService.__init__` keeps its existing three-argument signature (`ladder_repo`, `accounts_service`, `date_resolver`) — `tests/unit/test_performance_service.py` and `app/api/performance.py` must NOT need changes — and builds a `DailyReturnSeriesLoader` from those arguments internally; then `get_performance` calls `loader.load(..., attribute_label=attributes[0])` for steps after attribute validation. Behaviour MUST be unchanged
- [X] T005 Re-run the T001 regression baseline plus `tests/unit/test_performance.py` and confirm everything still passes; fix any regression in T003/T004 (do not edit existing tests to make them pass unless a constructor signature change is unavoidable, and note any such edit in the commit message)

**Checkpoint**: Shared loader exists; performance endpoints behave exactly as before.

---

## Phase 3: User Story 1 — Retrieve a Daily Return Histogram (Priority: P1) 🎯 MVP

**Goal**: `GET /v1/accounts/{account_name}/risk/return-histogram` returns the sparse, ascending
histogram of rounded basis-point buckets with counts (statistics block added in US2).

**Independent Test**: For an account with known daily returns, every bucket count equals the number
of days whose return × 10,000 rounds (half away from zero) to that bucket; empty buckets absent;
sorted ascending.

### Tests for User Story 1 (write first, verify they FAIL)

- [X] T006 [P] [US1] Write failing unit tests in `tests/unit/test_return_histogram.py` for `round_half_away_from_zero`, `to_basis_points` and `build_histogram`: `round_half_away_from_zero` on exact values (0.5→1, -0.5→-1, 1.5→2, 2.5→3, -2.5→-3, 0.4→0) — never banker's rounding; `to_basis_points` on ordinary values (0.0010→10, 0.00104→10, 0.0011→11, -0.0025→-25) and on decimal-half returns that suffer floating-point noise (0.00005→1, 0.00015→2, 0.00025→3, -0.00025→-3); tiny +/− values → bucket 0; example from spec (`[(-25,1),(10,3),(11,1)]`); zero-count buckets omitted; output sorted ascending regardless of input order; empty input → `[]`; counts are `int` and buckets are `int`
- [X] T007 [P] [US1] Write failing unit tests in `tests/unit/test_risk_service.py` for `RiskService.get_return_histogram` histogram behaviour: only dates within `[resolved_start, resolved_end]` contribute (FR-012, use a ladder with dates outside the window); portfolio return is the sum of `weighted_position_return` across sub-accounts (spec example 0.011 + −0.0045 → bucket 65); response echoes `account_name`, `from_date`, `to_date`; `_links` contains `self` and `accounts`. Use a fake/real `LadderRepository` in `tmp_path` following `tests/unit/test_performance_service.py`
- [X] T008 [P] [US1] Write Gherkin scenarios in `tests/features/return_histogram.feature` (tag `@us1`) for the four User Story 1 scenarios from spec.md: rounded buckets, omitted empty buckets, ascending order, sum of weighted position returns
- [X] T009 [US1] Write step definitions in `tests/steps/return_histogram_steps.py` (`scenarios("return_histogram.feature")`): for the bucket/statistics scenarios write stored ladders directly through `LadderRepository` (as in `tests/unit/test_performance_service.py`) with controlled `weighted_position_return` values so exact buckets can be asserted — ingest-derived returns depend on market data and are not deterministic enough; use the existing app_client/ladder-upload pattern from `tests/steps/retrieve_performance_steps.py` only for the US3 comparison against the performance endpoint. Issue `GET /v1/accounts/{name}/risk/return-histogram?start=&end=`, assert the `histogram` array. Verify the feature file FAILS (404 route) before implementation

### Implementation for User Story 1

- [X] T010 [P] [US1] Create Pydantic models in `app/models/risk.py`: `ReturnHistogramResponse` (`account_name`, `from_date`, `to_date`, `histogram: list[tuple[int, int]]`, `links: dict[str, str]` with `alias="_links"`, `populate_by_name=True`) — `statistics` is added in US2. Match the style of `app/models/performance.py`
- [X] T011 [US1] Implement `round_half_away_from_zero(bps: pd.Series) -> pd.Series` (`np.sign(x) * np.floor(np.abs(x) + 0.5)`, int), `to_basis_points(daily_returns: pd.Series) -> pd.Series` (`(x * 10_000).round(9)` then `round_half_away_from_zero`, per research.md §4), and `build_histogram(bps: pd.Series) -> list[tuple[int, int]]` (value_counts → sorted ascending → plain Python ints) in `app/services/return_histogram.py`. Make T006 pass
- [X] T012 [US1] Implement `RiskService` in `app/services/risk_service.py`: constructor takes a `DailyReturnSeriesLoader`; `get_return_histogram(account_name, start, end, today) -> ReturnHistogramResponse` calls `loader.load(..., attribute_label="return-histogram")`, slices `daily_returns` to `[resolved_start, resolved_end]`, applies `to_basis_points` + `build_histogram`, emits a structlog `return_histogram_request` event (account_name, from_date, to_date, observation count, bucket count), and builds `_links` (`self` = `/v1/accounts/{account_name}/risk/return-histogram`, `accounts` = `/v1/accounts`). Make T007 pass
- [X] T013 [US1] Implement the router in `app/api/risk.py` (`APIRouter(prefix="/v1", tags=["Risk"])`): dependency `_get_risk_service` wiring `LadderRepository`, `CapitalRepository`, `AccountsService`, `TimeseriesDateResolver`, `DailyReturnSeriesLoader` (mirror `_get_performance_service` in `app/api/performance.py`); route `GET /accounts/{account_name}/risk/return-histogram` with optional `start`/`end` `date` query params, `validate_account_name`, `date.today()`, `JSONResponse(model_dump(by_alias=True, mode="json"))`, and 404/422 response docs
- [X] T014 [US1] Register the router in `app/main.py` (`from app.api import risk`; `app.include_router(risk.router)` alongside `performance.router`). Run T007, T009 and the whole `tests/features/return_histogram.feature` — all US1 scenarios pass

**Checkpoint**: MVP — histogram endpoint works end to end.

---

## Phase 4: User Story 2 — Distribution Statistics (Priority: P1)

**Goal**: The response carries a `statistics` block: count, mean, median, mode, minimum, maximum,
sample `std_dev`, `std_dev_bands` (σ multiple + lower/upper edges for 1, 2, 3), skewness, excess
kurtosis — with `null` for undefined values.

**Independent Test**: For a small hand-computable data set, each statistic matches an
independently calculated value; `count` equals the sum of histogram counts.

### Tests for User Story 2 (write first, verify they FAIL)

- [X] T015 [P] [US2] Write failing unit tests in `tests/unit/test_return_histogram.py` for `compute_statistics(bps: pd.Series) -> HistogramStatistics`: spec example `[-10, 0, 0, 10, 20]` → count 5, min −10, max 20, mean 4, median 0, mode 0, sample std_dev `√(((−14)²+(−4)²+(−4)²+6²+16²)/4) = √(520/4)`, bands `multiple = k·σ`, `lower = mean − k·σ`, `upper = mean + k·σ` for k = 1, 2, 3 (order 1, 2, 3); skewness and excess kurtosis against hand-computed pandas-equivalent values (`Series.skew()`, `Series.kurt()`); mode tie → smallest bucket; n = 0 → count 0, everything else `None`, `std_dev_bands == []`; n = 1 → `std_dev` `None`, bands `[]`, skewness/kurtosis `None`; n = 2 → std_dev defined, skewness `None`; n = 3 → skewness defined, kurtosis `None`; constant series (n ≥ 4) → `std_dev == 0`, bands collapse to the mean, skewness/kurtosis `None`; no `NaN`/`inf` ever appear in output
- [X] T016 [P] [US2] Extend `tests/unit/test_risk_service.py`: response `statistics.count` equals the sum of histogram counts; empty window → `histogram == []` and `statistics.count == 0` with `None` values (zero-observation handling itself is unit-tested in T015; see T024 note); statistics are computed on rounded bps observations (two days each returning 0.00104 → bucket 10 twice, so `mean == 10.0`, whereas the unrounded mean would be 10.4)
- [X] T017 [P] [US2] Add `@us2` scenarios to `tests/features/return_histogram.feature` for the two User Story 2 scenarios (statistics describe the same observations; count matches the histogram) and extend `tests/steps/return_histogram_steps.py` with the needed steps, including a check that every `std_dev_bands` entry satisfies `lower = mean − multiple` and `upper = mean + multiple`. Verify they FAIL

### Implementation for User Story 2

- [X] T018 [US2] Add `StdDevBand` and `HistogramStatistics` models to `app/models/risk.py` per `data-model.md` (nullable numeric fields as `float | None` / `int | None`; `std_dev_bands: list[StdDevBand]`) and add `statistics: HistogramStatistics` to `ReturnHistogramResponse`
- [X] T019 [US2] Implement `compute_statistics` in `app/services/return_histogram.py` per the table in `research.md` §5 (`Series.mean/median/std(ddof=1)/skew/kurt`, mode = smallest most-frequent bucket, null thresholds n<2 / n<3 / n<4 and zero-variance rule, convert numpy scalars to Python `int`/`float`, `NaN → None`). Make T015 pass
- [X] T020 [US2] Wire `compute_statistics` into `RiskService.get_return_histogram` in `app/services/risk_service.py`. Make T016 and the US2 scenarios (T017) pass; confirm the US1 scenarios still pass

**Checkpoint**: Full success response (histogram + statistics) matches `contracts/openapi.yaml`.

---

## Phase 5: User Story 3 — Shared Data Source with Performance (Priority: P2)

**Goal**: Prove the histogram and performance endpoints use the identical daily-return series and
date handling.

**Independent Test**: For the same account and window, histogram observation count equals the
number of business days the performance endpoints produce entries for, and default start/end
resolve identically.

### Tests for User Story 3 (write first)

- [X] T021 [P] [US3] Add an `@us3` scenario to `tests/features/return_histogram.feature` ("Histogram and performance use the same daily returns") plus a second scenario asserting default `start`/`end` resolve to the same `from_date`/`to_date` as `/v1/accounts/{name}/performance?attribute=ITD` with no dates; add steps in `tests/steps/return_histogram_steps.py` that call both endpoints and compare `statistics.count` with `len(entries)` and the resolved dates
- [X] T022 [P] [US3] Add a unit test in `tests/unit/test_risk_service.py` that `RiskService` and `PerformanceService` built over the same repositories resolve the same `(from_date, to_date)` for identical inputs, and that a business day with no ladder rows counts as one observation in bucket 0 (spec edge case; zero-fill inherited from `compute_daily_portfolio_return`)

### Implementation for User Story 3

- [X] T023 [US3] Run T021/T022; they should pass with no new production code because both services use `DailyReturnSeriesLoader` (Phase 2). If either fails, fix the divergence in `app/services/daily_return_series_loader.py` (not in the tests) and re-run the Phase 2 regression baseline (T001)

---

## Phase 6: User Story 4 — Invalid or Empty Requests (Priority: P2)

**Goal**: Predictable RFC 7807 errors for bad input and a clean 200 for a single-day window.

**Independent Test**: Start after end → 422; unknown account → 404; ladder missing → 422; future end
→ 422; single-day window → 200 with one observation and null dispersion statistics.

### Tests for User Story 4 (write first)

- [X] T024 [P] [US4] Add `@us4` scenarios to `tests/features/return_histogram.feature` (start after end; unknown account; invalid account name; future end date; capital-ledger-only account; weekend end date resolving to the following Monday, matching the performance endpoint's `to_date`; single-day window) and matching steps in `tests/steps/return_histogram_steps.py`. Assert `Content-Type: application/problem+json` for errors, and for the single-day window assert one bucket with count 1, `statistics.count == 1`, `mean` defined, and null `std_dev/skewness/kurtosis`. (An empty window is unreachable through the API — the resolved range always holds at least one business day — so zero-observation handling is covered only by the `compute_statistics` unit tests in T015.)
- [X] T025 [P] [US4] Add endpoint-level unit tests in `tests/unit/test_risk_service.py` for `RiskService` error propagation (`AccountNotFoundError`, `MissingRequiredSourceError`, `FutureEndDateError`, `InvalidDateRangeError`) — these come from the loader, so assert they surface unchanged

### Implementation for User Story 4

- [X] T026 [US4] Run T024/T025. Existing exception handlers in `app/main.py` already map every error; add no new handlers. Fix only genuine gaps (e.g. an empty-window path in `RiskService` that raises instead of returning an empty histogram — `compute_statistics` must handle an empty series per T015)

**Checkpoint**: All four user stories pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T027 [P] Add a test in `tests/unit/test_periodicity_openapi.py`-style (or a new `tests/unit/test_risk_openapi.py`) asserting `/openapi.json` contains `/v1/accounts/{account_name}/risk/return-histogram` with `start`/`end` parameters and the `ReturnHistogramResponse` schema, and that its `histogram` items are two-integer arrays
- [X] T028 [P] Add a performance sanity test in `tests/unit/test_return_histogram.py`: `to_basis_points` + `build_histogram` + `compute_statistics` over 2,600 synthetic daily returns complete well under 1 second (SC-004 guard; no I/O)
- [X] T029 Update `README.md` (endpoint list / API section) with the new risk endpoint, path, parameters, and a short example from `quickstart.md`
- [X] T030 Run the full quality gate: `.venv/Scripts/python -m pytest`, `ruff check app tests`, `ruff format --check app tests`, `mypy --strict app`; fix any findings
- [X] T031 Walk through `specs/011-risk-return-histogram/quickstart.md` against a running service (`uvicorn app.main:app`) with a real ingested account and confirm the histogram count matches the performance endpoint's entry count for the same window

---

## Dependencies & Execution Order

- **Phase 1 (T001)** → **Phase 2 (T002–T005)** → all stories.
- **US1 (Phase 3)** depends on Phase 2. It is the MVP.
- **US2 (Phase 4)** depends on US1 (extends its model, service and feature file).
- **US3 (Phase 5)** and **US4 (Phase 6)** depend on US1 and US2 (they assert against the complete response); they are independent of each other and can run in parallel.
- **Polish (Phase 7)** depends on all stories.

Within each story: tests → models → pure functions → service → router → verification.

## Parallel Opportunities

- Phase 2: T002 (tests) alone first; T003 then T004 sequential (same behaviour chain).
- US1: T006, T007, T008 in parallel (three different files); T010 in parallel with T011 (different files).
- US2: T015, T016, T017 in parallel.
- US3 tests (T021, T022) in parallel; US4 tests (T024, T025) in parallel; US3 and US4 phases can run concurrently by different developers.
- Polish: T027, T028 in parallel.

### Parallel Example: User Story 1

```text
Task: "Write unit tests for to_basis_points/build_histogram in tests/unit/test_return_histogram.py"   (T006)
Task: "Write unit tests for RiskService histogram behaviour in tests/unit/test_risk_service.py"        (T007)
Task: "Write Gherkin scenarios in tests/features/return_histogram.feature"                            (T008)
```

## Implementation Strategy

1. **MVP first**: Phases 1–3 deliver a working histogram endpoint (US1) on top of the shared loader.
2. **Increment 2**: Phase 4 adds statistics — the response now matches the full contract.
3. **Increment 3**: Phases 5–6 lock in consistency with performance and robust error handling.
4. **Finish**: Phase 7 documentation, OpenAPI check and the full quality gate.

At every checkpoint the performance regression baseline from T001 must remain green.

## Notes

- 31 tasks: Setup 1, Foundational 4, US1 9, US2 6, US3 3, US4 3, Polish 5.
- Statistics use pandas built-ins only — no scipy or other new dependency.
- `[P]` tasks touch different files; tasks that extend the same file (`return_histogram.feature`,
  `test_risk_service.py`, `return_histogram_steps.py`) are sequenced by story, not marked `[P]`
  against each other within a phase unless they only append independent scenarios.
