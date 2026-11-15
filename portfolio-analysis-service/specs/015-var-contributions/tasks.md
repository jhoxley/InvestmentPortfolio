---

description: "Task list for 015 — VaR Contributions (Marginal Risk) Endpoint"
---

# Tasks: VaR Contributions (Marginal Risk) Endpoint

**Input**: Design documents from `/specs/015-var-contributions/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md
**Methodology**: `docs/proposals/value-at-risk.md` §8

**Tests**: REQUIRED. The constitution's Principle I makes TDD non-negotiable. Every test task must
be written and **seen to fail** before its implementation task starts. BDD scenarios come from
spec.md's Gherkin blocks and go in `tests/features/var_contributions.feature` with steps in
`tests/steps/var_contributions_steps.py` (naming follows the existing `var_calculation_runs.feature` /
`var_series_backtest_api.feature` convention — no numeric prefix).

**Organization**: Tasks are grouped by user story. Paths are relative to
`portfolio-analysis-service/` unless prefixed with `(repo root)`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story from spec.md (US1, US2, US3)

## Conventions every task must follow

- Full type annotations; docstrings on every public symbol; `mypy --strict app/` and
  `ruff check app/ tests/` clean; `ruff format`.
- Never modify the behaviour of existing `estimate()` callers (feature 012's run loop) or the
  existing `VarSeriesService`/`VarBacktestService` — this feature only adds a new read path.
- Confidence levels are integer basis points internally (9500/9750/9900), matching the rest of the
  VaR code; this endpoint's `confidence` query parameter accepts exactly one value (not repeatable),
  per contracts/openapi.yaml — distinct from the series/backtest endpoints' repeatable parameter.
  There is no "headline confidence" setting (only `headline_lookback`): the single-confidence
  default is the first entry of `settings.confidence_levels_bp` (spec.md FR-001).
- `group_by` is `"position"` or `"theme"`; an unresolvable theme is the reserved `"Unclassified"`.
- Cash is always its own group (key `"Cash"`, `identifier=None`) with all four risk measures `0.0`.
- An invalid `lookback`, `confidence` or `group_by` is always rejected with the existing
  `InvalidVarQueryError` / `invalid-var-query` problem type (`fields` names the bad parameter) —
  there is no separate `invalid-group-by`/`invalid-var-lookback`/`invalid-confidence-level` type
  (spec.md FR-011–013, research.md §3).
- A group's `actual_mv_pct`/`proxied_mv_pct`/`rescaled_mv_pct` come from the per-scenario-day
  provenance codes in `ScenarioMatrix` (data-model.md), not from `instruments.csv`'s coarser
  per-identifier "worst treatment" label.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Model/schema additions and empty test scaffolding that later phases fill in.

- [ ] T001 Create empty test modules `tests/unit/test_var_contributions_engine.py`,
  `tests/unit/test_var_contributions_service.py`, `tests/unit/test_var_repository_scenario_returns.py`,
  `tests/unit/test_risk_var_contributions_openapi.py`, `tests/features/var_contributions.feature`
  (Feature header only) and `tests/steps/var_contributions_steps.py` (binds the feature file via
  `scenarios(...)`, as the other step modules do). Create the module skeletons
  `app/services/var/contributions.py` and `app/services/var/var_contributions_service.py`
  (module docstring only, per research.md §1/§6/§7 and data-model.md).
- [ ] T002 [P] Add `theme: str | None = Field(default=None, ...)` to `IdentifierMappingEntry` in
  `app/models/market_data.py` (data-model.md) — a genuinely new field added by this feature (it does
  not exist anywhere in this service today, including under any other name). Add a unit test (new
  `tests/unit/test_identifier_mapping_entry_theme.py`, or extend `test_var_settings.py`) proving an
  entry with no `theme` key still validates with `theme is None`, and that an entry with
  `"theme": "Global Equity"` round-trips. Extend `FakeIdentifierMappingRepository.set_entry(...)` in
  `tests/conftest.py` to accept an optional `theme` keyword argument.
- [ ] T003 [P] Add `ContributionGroupEntry` and `VarContributionsResponse` Pydantic models to
  `app/models/var_series.py` per data-model.md's "API response model" section (same
  `ConfigDict(populate_by_name=True)` / `_links` alias pattern as `VarSeriesResponse`).

**Checkpoint**: `mypy --strict app/` passes; new empty test files collect without error.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The scenario-matrix refactor, the persisted snapshot store, and the route/service
skeleton every user story's tests exercise.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write first, must fail)

- [ ] T004 [P] Write `tests/unit/test_var_repository_scenario_returns.py` against a `tmp_path`.
  Cover: (a) `read_scenario_returns` returns an empty/`None`-equivalent snapshot when nothing has
  been committed; (b) `commit_scenario_returns(account, panel)` persists `scenario_returns.csv`,
  `scenario_observed.csv` and `scenario_returns_meta.json`, round-tripping through
  `read_scenario_returns` back into a `ReturnPanel`-equivalent shape; (c) a second commit with an
  overlapping-but-different date range and an extra new identifier **outer-joins** onto the first —
  previously-stored dates/identifiers outside the second commit's range are preserved, cells inside
  both commits' overlap take the second commit's value, and the new identifier's earlier dates read
  back as unknown (not zero); (d) a commit failure partway through (monkeypatch the second file's
  write to raise) leaves all three files exactly as they were before the call, matching
  `VarRepository.commit`'s existing temp-file/`os.replace` all-or-none behaviour.
- [ ] T005 [P] Add a regression test to `tests/unit/test_var_engine.py`: for a hand-built `Exposure`
  and `ReturnPanel` (reuse an existing test's fixtures), `build_scenario_matrix(...)` followed by
  `scenario_pnl(matrix.effective_returns[matrix.included], matrix.values)` equals the
  `scenario_pnls` that `estimate()` returns for the identical inputs — proving the extraction changes
  nothing about `estimate()`'s existing, already-tested output. Also assert `matrix.provenance`'s
  shape matches `matrix.effective_returns` and that, summed (market-value-weighted) over
  `matrix.included` rows, it reproduces the same `actual_mv_pct`/`proxied_mv_pct`/`rescaled_mv_pct`
  that `EstimateResult` already reports for the same inputs — proving the carried-through provenance
  is sufficient to rederive the account-wide figures, which US1 (T012/T015) relies on at group level.

### Implementation

- [ ] T006 Implement `VarRepository.commit_scenario_returns(account_name, panel: ReturnPanel)` and
  `read_scenario_returns(account_name) -> ReturnPanel | None` in `app/repositories/var_repository.py`
  (research.md §2, data-model.md "ScenarioReturnsSnapshot"): two wide CSVs (`scenario_returns.csv`,
  `scenario_observed.csv`, one column per identifier) plus `scenario_returns_meta.json`
  (`first_observed_date` per identifier, `updated_at`), written via the same temp-file + `os.replace`
  all-or-none pattern `commit()` already uses, with new dates/identifiers outer-joined onto whatever
  is already stored (latest commit wins on overlap). Makes T004 pass.
- [ ] T007 Refactor `app/services/var/engine.py`: add the `ScenarioMatrix` dataclass (data-model.md),
  now including a `provenance: np.ndarray` field (window_len x m, the existing `_ACTUAL`/`_PROXY`/
  `_RESCALED` codes), and extract `build_scenario_matrix(exposure, panel, as_of_row, lookback_days,
  settings, proxy_configs) -> ScenarioMatrix` from the matrix-building block currently inline in
  `estimate()` (research.md §1). `estimate()` calls this builder, then proceeds exactly as today.
  Run the full existing `tests/unit/test_var_engine.py` suite (pre-existing tests, unmodified) plus
  T005 — all must pass with zero behavioural change.
- [ ] T008 Extend `VarRunService._execute_body` in `app/services/var/var_run_service.py` to call
  `self._var_repo.commit_scenario_returns(account_name, panel)` as part of the same successful run
  that commits estimates/outcomes/instruments, logging a `var_contributions_snapshot_persisted`
  structured event (identifier_count, grid_days). Add/extend a test in
  `tests/unit/test_var_run_service.py` asserting that two successive runs over different,
  non-identical date ranges leave the persisted snapshot covering the **union** of both runs' grids
  (not just the second run's).
- [ ] T009 Add `GET /v1/accounts/{account_name}/risk/var/contributions` to `app/api/risk_var.py`,
  backed by a new `_get_var_contributions_service` dependency provider and a currently-minimal
  `VarContributionsService.get_contributions(...)` in `app/services/var/var_contributions_service.py`
  that only resolves the account/date/lookback and returns the "not computed" empty
  `VarContributionsResponse` shape (`date=None`, `groups=[]`, `_links` with `self`/`status`/`runs`) —
  the full computation and the insufficient-quality/validation branches are filled in by US1/US2/US3
  below. Write `tests/unit/test_risk_var_contributions_openapi.py` (mirroring
  `test_risk_var_series_openapi.py`) asserting the new path and `VarContributionsResponse` schema
  appear in `/openapi.json`, and that it passes against this minimal implementation.

**Checkpoint**: Full existing test suite plus all Foundational tests pass; the route exists and
always returns a valid (empty) response.

---

## Phase 3: User Story 1 - See which positions drive an account's risk on a given date (Priority: P1) 🎯 MVP

**Goal**: For an account/date/lookback/confidence that already has a completed, sufficient-quality
VaR estimate, return standalone VaR, incremental VaR, component ES and marginal VaR per position or
per theme (including Cash), with component ES summing to the account's total ES.

**Independent Test**: Seed a ladder + observed prices for a handful of positions on one date, run a
full VaR calculation (feature 012), then call the contributions endpoint grouped by position and by
theme and verify the component ES sums match the stored total ES within 0.5%.

### Tests for User Story 1 (write first, must fail) ⚠️

- [ ] T010 [P] [US1] Write `tests/unit/test_var_contributions_engine.py` for
  `app/services/var/contributions.py`, using small hand-built scenario matrices (reuse the mini
  example from `docs/proposals/value-at-risk.md` §3.4: A £60,000, B £30,000, Cash £10,000):
  - `standalone_var(group_pnl, p_bp)` equals `var_es(-group_pnl, p_bp).var` for a single column in
    isolation;
  - `incremental_var(total_losses, group_pnl, p_bp)` equals
    `var_es(total_losses, p_bp).var - var_es(-(total_pnl - group_pnl), p_bp).var`, where
    `total_pnl = -total_losses`, i.e. VaR(portfolio) − VaR(portfolio without this group);
  - `tail_weights`/`component_es` reproduce the exact Acerbi–Tasche split `var_es` already uses, and
    summing `component_es` over a full partition of columns equals the portfolio's total ES exactly
    (to floating-point precision, not just within a tolerance);
  - `marginal_var(component_es, market_value)` is `component_es / market_value`, and is `0.0` by
    definition for a group whose `component_es` is `0.0` regardless of `market_value` (the Cash
    case: market_value > 0, component_es == 0.0 → marginal == 0.0, never a division producing NaN).
- [ ] T011 [P] [US1] Add US1 scenarios to `tests/features/var_contributions.feature` (from spec.md:
  "Contributions grouped by position for a fully computed date", "Contributions grouped by theme")
  and implement their steps in `tests/steps/var_contributions_steps.py`: seed a ladder and observed
  prices for 2–3 positions plus Cash (reusing the seeding helpers from
  `tests/steps/var_calculation_runs_steps.py`), set a `theme` on at least one
  `IdentifierMappingEntry` via the fake repository, trigger a full run via
  `POST /v1/accounts/{a}/risk/var/runs {"mode": "full"}` (executed inline in tests), then call
  `GET /v1/accounts/{a}/risk/var/contributions?...&group_by=position` and `...&group_by=theme` and
  assert: one group per position/theme including `"Cash"`; `sum(component_es_gbp)` across groups
  equals the account's stored total ES at that date/lookback/confidence within 0.5% relative
  tolerance (SC-001); a theme with no `theme` configured is folded into `"Unclassified"`. Also
  assert the fake market-data client's call count is unchanged (`0` new calls) after the
  contributions request — the fixture already records calls for the preceding run, so capture the
  count immediately after the run completes and compare it to the count after the contributions
  call (FR-007, SC-002).
- [ ] T012 [P] [US1] Write direct (non-HTTP) unit tests in `tests/unit/test_var_contributions_service.py`
  for `VarContributionsService.get_contributions(...)`'s "computed, sufficient/degraded quality"
  path, constructing its collaborators (`LadderRepository`, `VarRepository`,
  `IdentifierMappingRepository`) against `tmp_path`/fakes directly rather than through the full API —
  faster and more isolated than T011's BDD round trip. Cover: grouping by position and by theme
  produces the expected group keys and market values; a group's `actual_mv_pct`/`proxied_mv_pct`/
  `rescaled_mv_pct` are correctly derived from `ScenarioMatrix.provenance` (not from
  `instruments.csv`'s coarser per-identifier label) for a case where a position was proxied on some
  but not all scenario days; the Cash group's measures are exactly `0.0`.

### Implementation for User Story 1

- [ ] T013 [P] [US1] Implement `app/services/var/contributions.py`: `standalone_var`,
  `incremental_var`, `tail_weights` (reusing `var_es`'s existing `Fraction`-based tail split rather
  than re-deriving it — research.md §6), `component_es`, `marginal_var`, each a small, fully
  type-annotated, docstringed pure function over numpy arrays. Makes T010 pass.
- [ ] T014 [US1] Add a theme-resolution helper (e.g. `resolve_theme(identifier, mapping_lookup) ->
  str` returning the mapped `theme` or `"Unclassified"`) alongside `app/services/var/exposures.py`,
  and a grouping helper that partitions `ScenarioMatrix` columns (including its `provenance` codes)
  by either `sub_account` (`group_by=position`) or resolved theme (`group_by=theme`, market-value-
  weighted provenance across the theme's constituent columns), always adding a synthetic `"Cash"`
  group (key `"Cash"`, `identifier=None`, `market_value=exposure.cash_value`, all four risk measures
  `0.0`, coverage 100%/0%/0%) regardless of grouping mode.
- [ ] T015 [US1] Implement `VarContributionsService.get_contributions(...)` fully for the
  "computed, sufficient/degraded quality" case in
  `app/services/var/var_contributions_service.py`: look up the stored estimate row (date, lookback,
  confidence) via `VarRepository.read_estimates`; reconstruct `Exposure` for that date via
  `LadderRepository.read_full_df` + `build_exposures`; reconstruct the `ReturnPanel` via
  `VarRepository.read_scenario_returns`; call `build_scenario_matrix(...)` for the requested
  look-back/confidence; group columns (and their provenance) per T014; call the T013 functions per
  group; derive each group's coverage/quality percentages from the grouped provenance (T014); and
  assemble `ContributionGroupEntry` rows into a populated `VarContributionsResponse`. Makes T012
  pass.
- [ ] T016 [US1] Wire a `var_contributions_request` structured log event (account_name, date,
  lookback_code, confidence_bp, group_by, group_count) into the route in `app/api/risk_var.py`,
  mirroring `var_series_request`.

**Checkpoint**: User Story 1 is fully functional and independently testable for the "computed, good
quality" path.

---

## Phase 4: User Story 2 - Understand risk when data for the request is missing or degraded (Priority: P2)

**Goal**: Requests for a never-computed account/date/lookback, or a date whose stored quality is
`insufficient`, return a clear, non-error, non-fabricated 200 response.

**Independent Test**: Call the endpoint for an account with no VaR run at all, and separately for a
date known to be `insufficient` quality (per `docs/proposals/value-at-risk.md` §4.5), and confirm
each returns the documented shape rather than an error or invented figures.

### Tests for User Story 2 (write first, must fail) ⚠️

- [ ] T017 [P] [US2] Write direct (non-HTTP) unit tests in `tests/unit/test_var_contributions_service.py`
  for `VarContributionsService.get_contributions(...)`'s two gating branches, calling the service
  directly (not through T018's full API round trip): (a) no estimate row exists for the resolved
  account/date/lookback → the "not computed" response shape; (b) a stored estimate row with
  `quality == "insufficient"` → `groups=[]`, `quality="insufficient"`, `quality_reason` populated,
  `total_value_gbp` still populated. Neither branch should construct a `ScenarioMatrix` or call any
  `contributions.py` function — assert this directly (e.g. via a spy/mock on
  `build_scenario_matrix`).
- [ ] T018 [P] [US2] Add US2 scenarios to `tests/features/var_contributions.feature` (from spec.md:
  "No VaR run has ever covered the requested account and lookback", "The requested date's VaR
  quality is insufficient") and implement their steps in `tests/steps/var_contributions_steps.py`:
  one scenario against an account with no run at all; one scenario seeded so a requested date/lookback
  combination's stored `quality` is `"insufficient"` (a short, sparse history is the simplest way to
  force this, per the engine's existing quality thresholds). Assert, respectively: `200`,
  `"groups": []`, `"date": null`, `_links` containing `status` and `runs`; and `200`,
  `"quality": "insufficient"`, `"groups": []`, `total_value_gbp` still populated, no `500`/`422`
  in either case.

### Implementation for User Story 2

- [ ] T019 [US2] In `VarContributionsService.get_contributions(...)`, branch before T015's
  computation: if no estimate row exists for the resolved account/date/lookback, return the
  "not computed" `VarContributionsResponse` (as already stubbed in T009, now reachable for every
  account, not only ones with zero runs); if the stored row's `quality == "insufficient"`, return
  `groups=[]` with `quality="insufficient"`, `quality_reason` copied from the stored row, and
  `total_value_gbp` populated from the stored outcome/estimate row — without calling
  `build_scenario_matrix` or any T013 function. Makes T017 and T018 pass.

**Checkpoint**: User Stories 1 and 2 both work independently; no request ever 4xx/5xxs purely because
of missing or low-quality data.

---

## Phase 5: User Story 3 - Reject malformed requests clearly (Priority: P3)

**Goal**: An invalid `lookback`, `confidence` or `group_by` value is rejected with a clear, structured
RFC 7807 error, consistent with the series/backtest endpoints.

**Independent Test**: Send a request with `group_by=sector` and confirm a `422` with problem type
`invalid-var-query` and `fields: ["group_by"]`-style detail; confirm an invalid `lookback` is
rejected the same way it already is on the series endpoint.

### Tests for User Story 3 (write first, must fail) ⚠️

- [ ] T020 [P] [US3] Add US3 scenarios to `tests/features/var_contributions.feature` (from spec.md:
  "Invalid group_by value", "Invalid lookback value reuses the existing problem type") and implement
  their steps in `tests/steps/var_contributions_steps.py`, asserting `422`,
  `type == "https://portfolio-analysis/errors/invalid-var-query"`, and the invalid field name is
  present in the problem detail/fields for each case. Add a unit test case to
  `tests/unit/test_risk_var_contributions_openapi.py` or a new
  `tests/unit/test_var_contributions_query_validation.py` for an invalid `confidence` value (one not
  among the account's configured levels) and confirm it is rejected the same way.

### Implementation for User Story 3

- [ ] T021 [US3] Add `_resolve_group_by(group_by: str | None) -> Literal["position", "theme"]` to
  `app/api/risk_var.py`, raising `InvalidVarQueryError(message=..., fields=["group_by"])` for any
  value other than `"position"`/`"theme"` (default `"position"`), matching the style of the existing
  `_resolve_lookback`/`_resolve_pnl_basis`.
- [ ] T022 [US3] Add `_resolve_single_confidence(confidence: str | None, settings: VarSettings) ->
  int` to `app/api/risk_var.py` — distinct from the existing repeatable `_resolve_confidence_levels`,
  since this endpoint's `confidence` parameter takes exactly one value (contracts/openapi.yaml):
  defaults to the first entry of `settings.confidence_levels_bp` when omitted (spec.md FR-001 — there
  is no separate "headline confidence" setting), and raises
  `InvalidVarQueryError(fields=["confidence"])` for anything not in `settings.confidence_levels_bp`.
  Wire both resolvers into the route from T009/T015, ahead of any computation or store lookup. Makes
  T020 pass.

**Checkpoint**: All three user stories are independently functional; malformed requests never reach
the computation or store-lookup code paths.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency and documentation pass.

- [ ] T023 [P] Run `ruff check app/ tests/`, `ruff format`, and `mypy --strict app/` across every file
  touched by this feature; fix any findings.
- [ ] T024 [P] Run `docs/proposals/value-at-risk.md`'s §11-E delivery-plan row update: mark the PAS
  contributions feature's status, following the same "Status: implemented" note style §11-B already
  carries for feature 012, recording the actual feature number (015) and branch
  (`015-var-contributions`), and listing any deviations found during implementation (e.g. the `theme`
  field addition and the `invalid-var-query` reuse from research.md §3/§4).
- [ ] T025 Run `specs/015-var-contributions/quickstart.md` steps 1–7 end to end against a real local
  run; fix any discrepancy between the documented behaviour and the implementation before calling the
  feature done.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3–5)**: All depend on Foundational phase completion.
  - US1 (T010–T016) has no dependency on US2/US3.
  - US2 (T017–T019) only needs the route/service skeleton from Foundational (T009) — it does not
    depend on US1's computation path, though both branches live in the same `get_contributions()`
    method, so implement US2's branch as an early-return before US1's computation block.
  - US3 (T020–T022) only needs the route from Foundational (T009) — it validates query parameters
    before either US1's or US2's branch runs.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests MUST be written and seen to fail before their implementation task starts (constitution
  Principle I).
- Pure math (T013) and the grouping helper (T014) before the service that calls them (T015).
- Service logic (T015/T019) before route wiring/logging (T016) and before query validation that
  gates entry to it (T021/T022).

### Parallel Opportunities

- T002 and T003 (Setup) can run in parallel — different files.
- T004 and T005 (Foundational tests) can run in parallel — different files.
- T010, T011 and T012 (US1 tests) can all run in parallel — different files/approaches (pure-math
  unit tests, full BDD round trip, direct service unit tests).
- T013 (US1 pure math) can be implemented in parallel with T014 (theme/grouping helper) — different
  files, both needed by T015.
- T017 (US2 direct unit tests) and T020 (US3 BDD) can be developed in parallel by different people
  once Foundational is done, since both are early-return branches that don't depend on each other or
  on US1's computation.

---

## Parallel Example: User Story 1

```bash
# Launch all three US1 test tasks together:
Task: "Write tests/unit/test_var_contributions_engine.py for the four decomposition functions"
Task: "Add US1 Gherkin scenarios + steps to tests/features/var_contributions.feature"
Task: "Write direct unit tests for VarContributionsService's computed-path grouping/quality logic"

# Launch the two independent US1 implementation modules together:
Task: "Implement app/services/var/contributions.py pure functions"
Task: "Implement the theme-resolution and grouping helper alongside app/services/var/exposures.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run `tests/features/var_contributions.feature`'s US1 scenarios and
   quickstart.md steps 1–3 independently.
5. Deploy/demo if ready — this alone delivers the headline "which positions drive this account's
   risk" value, assuming every request happens to hit an already-computed, good-quality date.

### Incremental Delivery

1. Setup + Foundational → the route exists, always returns a valid (if empty) response, and the
   snapshot store accumulates with every VaR run.
2. Add US1 → the happy path (computed, sufficient quality) returns real contributions (MVP).
3. Add US2 → missing/insufficient data is handled gracefully instead of (previously, pre-US2) falling
   through to an unhandled exception.
4. Add US3 → malformed requests are rejected clearly instead of (previously) reaching the
   computation code with an unvalidated value.
5. Polish → type/lint clean, full regression pass, quickstart validated end-to-end.

---

## Notes

- [P] tasks touch different files with no uncompleted dependency between them.
- [Story] labels map each task to spec.md's US1/US2/US3 for traceability.
- Per Constitution Principle I, every test task listed above must be written and observed to fail
  before its paired implementation task is started — do not implement first and backfill tests.
- Commit after each task or logical group, per repository convention.
