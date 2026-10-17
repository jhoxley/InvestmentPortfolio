---
description: "Task list for Position Time Series API feature"
---

# Tasks: Position Time Series API

**Input**: Design documents from `/specs/005-position-timeseries-api/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅

**Tests**: Required — Constitution Principle I mandates TDD with BDD/Gherkin. Test tasks appear
before their corresponding implementation tasks in every phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]–[US3])
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization and configuration scaffolding.

No tasks required. This feature introduces no new runtime dependency, no new `config.yaml`
section, and no new pytest marker — BDD scenarios reuse the existing `us1`–`us3` markers
already registered in `pyproject.toml` (feature 004). Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required by every user story. No user story work begins until this phase is complete.

**⚠️ CRITICAL**: All user story phases depend on this phase being fully complete.

- [X] T001 [P] Add `PositionLadderNotIngestedError(account_name: str, message: str | None = None)` to `app/exceptions.py` — pre-formats `.message` as `f"Account '{account_name}' has no ingested position ladder."` when no override is given, following the existing `AccountNotFoundError`/`EmptyCapitalDateRangeError` constructor pattern (data-model.md)
- [X] T002 [P] Create `app/models/position_timeseries.py` with: `PositionSummary` (`position: str`, `from_date: date`, `to_date: date`); `PositionsResponse` (`account_name: str`, `positions: list[PositionSummary]`, `links: dict[str, str] = Field(alias="_links")`, `model_config = ConfigDict(populate_by_name=True)`); `PositionTimeSeriesEntry` (Pydantic `BaseModel` with `model_config = ConfigDict(extra="allow")` and two declared fields `date: date`, `position: str` — additional attribute keys set dynamically per entry, mirroring `app/models/timeseries.py`'s `TimeSeriesEntry` pattern); `PositionTimeSeriesResponse` (`account_name: str`, `attributes: list[str]`, `positions: list[str]`, `from_date: date`, `to_date: date`, `entries: list[PositionTimeSeriesEntry]`, `links: dict[str, str] = Field(alias="_links")`, `model_config = ConfigDict(populate_by_name=True)`); import and reuse `AttributeDefinition`/`AttributeMetadataResponse` from `app/models/timeseries.py` as-is for the metadata endpoint — do not redefine them here (data-model.md)
- [X] T003 [P] Create `app/services/position_attributes.py` — the single source of truth for this endpoint's six supported attributes (data-model.md's Position Attribute table): a module-level `ATTRIBUTE_DEFINITIONS: list[AttributeDefinition]` (imported from `app.models.timeseries`) covering `market_value`, `income`, `book_cost`, `pnl`, `close_price`, `quantity` with their descriptions and `source="position_ladder"` for every entry; a `SUPPORTED_ATTRIBUTES: frozenset[str]` derived from it; a `COLUMN_FOR_ATTRIBUTE: dict[str, str]` mapping `market_value`→`market_value`, `income`→`total_income`, `book_cost`→`book_cost`, `close_price`→`price`, `quantity`→`quantity` (no entry for `pnl`, which is computed, not a direct column); a `validate_attributes(attributes: list[str]) -> None` that raises `NoAttributesRequestedError` if `attributes` is empty or `UnsupportedAttributeError` (naming every invalid entry, not just the first, including a request for `capital`) if any name is outside `SUPPORTED_ATTRIBUTES` — reuse `NoAttributesRequestedError`/`UnsupportedAttributeError` from `app/exceptions.py` unchanged (research.md §5)
- [X] T004 [P] Write failing unit tests in `tests/unit/test_positions_service.py`: `test_list_positions_returns_first_and_last_date_per_sub_account()` (build a small synthetic DataFrame with 2+ sub_accounts over different date ranges, assert `PositionsService.list_positions(df)` returns one `PositionSummary` per sub_account with correct min/max dates, sorted by position name); `test_resolve_effective_positions_defaults_to_all_when_none_requested()`; `test_resolve_effective_positions_intersects_and_silently_drops_unmatched()` (requested list includes one real and one fake name — assert only the real one comes back, no exception raised); `test_resolve_effective_positions_duplicate_requested_values_treated_once()`; `test_resolve_effective_positions_empty_when_all_requested_unmatched()` (assert empty list returned, not an exception); import `PositionsService` from `app/services/positions_service.py` (fails at import until T005)
- [X] T005 Implement `app/services/positions_service.py` — `PositionsService` (no constructor dependencies; operates purely on a passed-in DataFrame, per research.md §4) with `list_positions(ladder_df: pd.DataFrame) -> list[PositionSummary]` (`ladder_df.groupby("sub_account")["date"].agg(["min", "max"])`, mapped to `PositionSummary(position=name, from_date=min, to_date=max)`, sorted by `position`) and `resolve_effective_positions(ladder_df: pd.DataFrame, requested: list[str]) -> list[str]` (distinct `sub_account` values from `ladder_df`; if `requested` is empty, return all distinct values sorted; otherwise return the sorted intersection of `set(requested)` and the distinct values — silently producing an empty list if nothing matches, never raising); depends on T002 (for `PositionSummary`); run T004 tests to verify they pass

**Checkpoint**: Foundation complete — all user story phases may now proceed. T001–T003 have no ordering constraint between them; T004 depends on T002 (needs `PositionSummary`); T005 depends on T002 and T004.

---

## Phase 3: User Story 1 — Retrieve a Per-Position Time Series for One or More Positions (Priority: P1) 🎯 MVP

**Goal**: Given an account name and, optionally, one or more position names plus one or more attributes, return one JSON entry per (business day, active position), each position's own active lifecycle respected (forward-filled if still held and the ladder is stale, stopped at the real divestment date otherwise).

**Independent Test**: For an account with an ingested position ladder covering several positions, `GET /v1/accounts/{name}/position?position=Apple%20Inc&position=Nonexistent&attribute=market_value&attribute=quantity` over a known range returns 200 with entries only for "Apple Inc" (the unrecognised name silently dropped), each entry carrying both requested values.

### Tests for User Story 1 ⚠️ Write and verify FAILING before implementing

- [X] T006 [P] [US1] Write Gherkin feature file `tests/features/retrieve_position_timeseries.feature` with all thirteen US1 scenarios from `spec.md`: "Retrieve a time series for two named positions and valid attributes", "No position names supplied defaults to every position in the account", "An unrecognised position name is silently ignored, not rejected", "Position names containing spaces and symbols are correctly matched", "The \"capital\" attribute is no longer valid on this endpoint", "A known account with no ingested position ladder is rejected, but not as unknown", "Unknown account name is rejected", "Every requested position name fails to match returns zero entries, not an error", "Missing mandatory attribute is rejected", "Start date after end date is rejected", "End date in the future is rejected", "A position that was fully divested before the resolved end date has no entries after its last active date", "A still-held position is forward-filled to the resolved end date when the ladder itself is stale" — use exact Gherkin from spec; tag each `@us1`
- [X] T007 [P] [US1] Write failing unit tests in `tests/unit/test_position_timeseries_service.py`: `test_effective_positions_default_to_all_including_cash_when_none_requested()`; `test_unrecognised_position_silently_dropped_no_error()`; `test_all_requested_positions_unmatched_returns_zero_entries_not_error()` (every supplied `position` value fails to match — assert a normal `PositionTimeSeriesResponse` with `entries == []`, no exception raised); `test_entries_contain_only_requested_attribute_keys()` (no extra/null keys for unrequested attributes); `test_market_value_book_cost_income_close_price_quantity_each_sourced_from_their_own_column()` (seed a fixture where each of the five direct-mapping columns has a distinct, easily-confused-if-swapped value, request all five as separate attributes, and assert each entry's `market_value`/`book_cost`/`income`/`close_price`/`quantity` values match their respective source column exactly — not e.g. `income` accidentally reading `book_cost`); `test_pnl_equals_income_plus_market_value_minus_book_cost_per_position()`; `test_still_held_position_forward_filled_through_resolved_end()` (a position whose last row equals the ladder's own `to_date` gets entries through `resolved_end` with the last known values repeated); `test_divested_position_not_forward_filled_past_its_own_last_row()` (a position whose last row is before the ladder's own `to_date` gets no entries after that row, even when `resolved_end` is later); `test_position_bought_after_resolved_start_has_no_entries_before_its_first_row()`; `test_position_with_no_overlap_with_resolved_range_produces_zero_entries_not_an_error()`; `test_response_positions_field_excludes_a_position_skipped_for_zero_overlap()` (a requested position matches the account but has no overlap with the resolved range — assert it is absent from `response.positions` even though it was part of the effective set, per data-model.md's "actually represented in entries" contract); `test_start_before_ladders_own_earliest_date_raises_missing_required_source_error()`; `test_known_account_without_ladder_raises_position_ladder_not_ingested_error()`; `test_unknown_account_raises_account_not_found_error()`; `test_capital_attribute_rejected_as_unsupported()`; `test_no_attributes_raises_no_attributes_requested_error()`; `test_resolved_start_after_resolved_end_raises_invalid_date_range_error()`; `test_future_end_date_raises_future_end_date_error()`; use `tmp_path`-backed real `LadderRepository` with fixture data written via its `write()` method (constructing DataFrames directly, matching this codebase's existing repository-testing style — not mocks); import `PositionTimeSeriesService` from `app/services/position_timeseries_service.py` (fails at import until T008)

### Implementation for User Story 1

- [X] T008 [US1] Implement `app/services/position_timeseries_service.py` — `PositionTimeSeriesService(ladder_repo: LadderRepository, accounts_service: AccountsService, positions_service: PositionsService, date_resolver: TimeseriesDateResolver)` with `get_series(account_name: str, positions: list[str], attributes: list[str], start: date | None, end: date | None, today: date) -> PositionTimeSeriesResponse`: call `position_attributes.validate_attributes(attributes)`; call `accounts_service.get_summary(account_name)`, raising `AccountNotFoundError(account_name, message=f"No capital ledger or position ladder has been ingested for account '{account_name}'.")` if both resources are `None` (FR-002), or `PositionLadderNotIngestedError(account_name)` if `position_ladder` is `None` but `capital_ledger` is not (FR-002); `ladder_df = ladder_repo.read_full_df(account_name)`; `effective_positions = positions_service.resolve_effective_positions(ladder_df, positions)` (FR-004/FR-005); resolve dates via `date_resolver.resolve(start, end, today, required_source_earliest_dates=[summary.position_ladder.from_date])` (FR-009); if `resolved_start < summary.position_ladder.from_date`, raise `MissingRequiredSourceError(account_name=account_name, attribute=", ".join(attributes), source="position_ladder", message=f"position_ladder for account '{account_name}' has no data before {summary.position_ladder.from_date}, but the resolved start date is {resolved_start}.")` (FR-010); determine `value_columns` needed from `position_attributes.COLUMN_FOR_ATTRIBUTE` for every requested attribute other than `pnl`, plus `book_cost`/`total_income`/`market_value` unconditionally if `pnl` is requested; for each position in `effective_positions`: `subset = ladder_df[ladder_df.sub_account == position]`; `first_date, last_date = subset.date.min(), subset.date.max()`; `still_held = (last_date == summary.position_ladder.to_date)`; `expand_start = max(resolved_start, first_date)`; `expand_end = resolved_end if still_held else min(resolved_end, last_date)` (research.md §2, FR-013); skip this position (zero entries) if `expand_start > expand_end`; else `expanded = expand_business_days(subset, value_columns, expand_start, expand_end)`; if `"pnl"` requested, `expanded["pnl"] = expanded["total_income"] + expanded["market_value"] - expanded["book_cost"]`; append one `PositionTimeSeriesEntry(date=row.date, position=position, **{attr: float(row[COLUMN_FOR_ATTRIBUTE.get(attr, attr)]) for attr in attributes})` per row; sort all collected entries by `(date, position)`; set `positions=sorted({entry.position for entry in entries})` — the set of positions **actually represented in `entries`** (data-model.md), which is NOT necessarily the same as `effective_positions`: a position in the effective set that was skipped for zero date-range overlap (`expand_start > expand_end`, above) contributes no rows and MUST NOT appear in this field, even though it matched the request; return `PositionTimeSeriesResponse(account_name=account_name, attributes=attributes, positions=positions, from_date=resolved_start, to_date=resolved_end, entries=entries, _links={"self": f"/v1/accounts/{account_name}/position", "positions": f"/v1/accounts/{account_name}/positions", "attributes": "/v1/positions/attributes", "accounts": "/v1/accounts"})`; bind and log a structlog event per request (`position_timeseries_request`, with account_name, requested positions, effective positions, attributes, resolved date range, row_count), following the existing `logger.bind(...)` pattern (Constitution IV); depends on T001, T002, T003, T005; run T007 tests to verify they pass
- [X] T009 [US1] Create `app/api/position_timeseries.py` — `APIRouter(prefix="/v1", tags=["Position Timeseries"])`; `GET /accounts/{account_name}/position` handler: validate `account_name` via `app/validators/account_name.py`; accept `position: list[str] = Query(default_factory=list, description="Repeated; zero or more")`, `attribute: list[str] = Query(default_factory=list, description="Repeated; at least one required")`, `start: date | None = Query(default=None)`, `end: date | None = Query(default=None)`; call `PositionTimeSeriesService.get_series(..., today=date.today())`; return the `PositionTimeSeriesResponse`; wire `_get_position_timeseries_service(...)` via `Depends`, composing `get_ladder_repository`/`get_capital_repository` (from `app/api/dependencies.py`, unchanged), a fresh `AccountsService`, a fresh `PositionsService()`, and a fresh `TimeseriesDateResolver()`; depends on T008
- [X] T010 [US1] Register `position_timeseries.router` in `app/main.py` and add an exception handler for `PositionLadderNotIngestedError` (422, via the existing `_problem()` helper, following the pattern of `MissingRequiredSourceError`'s handler) — the other five exceptions this endpoint raises (`AccountNotFoundError`, `NoAttributesRequestedError`, `UnsupportedAttributeError`, `FutureEndDateError`, `InvalidDateRangeError`, `MissingRequiredSourceError`) already have handlers registered from feature 004 and need no changes; depends on T009, T001
- [X] T011 [US1] Write BDD step implementations in `tests/steps/retrieve_position_timeseries_steps.py` for all thirteen US1 scenarios — seed fixtures by POSTing raw sub-account ledger XLSX files to the existing `/ladder` endpoint via `app_client` (not by writing files directly, to exercise the real ingestion→expansion→enrichment→retrieval path); build a "still held" position with continuous `quantity > 0` through the ledger's latest date and a "genuinely divested" position with an explicit `quantity: 0.0` row at its closure date (per `LadderExpander._apply_closure_rule` — the closure date's row is retained, dates after it are not); since the ladder's `to_date` is always computed dynamically as `today` minus two business days (never a fixed literal date — the spec's Given clauses deliberately use relative wording, not hardcoded dates, matching feature 004's `retrieve_timeseries_steps.py` convention), derive all fixture dates and assertions from `date.today()`/`pd.bdate_range(...)`, never a hardcoded calendar date, for the two forward-fill/divestment scenarios; pass position names containing spaces/symbols as ordinary query param values (httpx/TestClient percent-encodes automatically) and assert they still match; seed a request with two unrecognised `position` values and zero recognised ones, asserting `200` with an empty `entries` list; assert response shape, entry counts, forward-filled vs. stopped-at-divestment values, silently-dropped unrecognised positions, each error status/detail (404 vs 422 distinction, including the newly-added no-attribute/start-after-end/future-end 422 scenarios), and that `_links.self`, `_links.positions`, `_links.attributes`, `_links.accounts` are all present on a successful response; run `pytest tests/features/retrieve_position_timeseries.feature -m us1` to confirm all green; depends on T010

**Checkpoint**: US1 complete — main position time series endpoint fully functional and BDD-tested independently.

---

## Phase 4: User Story 2 — Discover Valid Positions and Their Active Date Ranges (Priority: P2)

**Goal**: A caller can list every position ever recorded for an account, each with its own first/last recorded date, via a dedicated helper endpoint that takes no arguments beyond the account name.

**Independent Test**: With an account holding three positions (two active, one divested), `GET /v1/accounts/{name}/positions` returns 200 listing all three with accurate per-position first/last dates.

### Tests for User Story 2 ⚠️ Write and verify FAILING before implementing

- [X] T012 [P] [US2] Write Gherkin feature file `tests/features/list_account_positions.feature` with all three US2 scenarios from spec: "Enumerate all positions held in an account", "Unknown account name is rejected", "A known account with no ingested position ladder is rejected, but not as unknown"; tag each `@us2`

### Implementation for User Story 2

- [X] T013 [US2] Add `GET /accounts/{account_name}/positions` handler to `app/api/position_timeseries.py` — validate `account_name`; reuse the same `AccountsService.get_summary()` 404/422 validation as the main endpoint (T008's account-validation logic, factored into a small shared helper function in this same module to avoid duplicating the two `raise` branches — e.g. `_validate_ladder_ingested(summary, account_name) -> None`, called from both handlers); `ladder_df = ladder_repo.read_full_df(account_name)`; `PositionsResponse(account_name=account_name, positions=positions_service.list_positions(ladder_df), _links={"self": f"/v1/accounts/{account_name}/positions"})`; wire via a new `_get_positions_endpoint_deps(ladder_repo: LadderRepository = Depends(get_ladder_repository), capital_repo: CapitalRepository = Depends(get_capital_repository)) -> tuple[LadderRepository, AccountsService]` dependency (composing `get_ladder_repository`/`get_capital_repository` from `app/api/dependencies.py` plus a fresh `AccountsService`) rather than reusing `_get_position_timeseries_service`, since this endpoint needs no `PositionTimeSeriesService`/`TimeseriesDateResolver`/attributes at all; depends on T009 (same router file), T005
- [X] T014 [US2] Write BDD step implementations in `tests/steps/list_account_positions_steps.py` — seed one account with three positions (two still-held, one divested) via the existing `/ladder` ingestion endpoint, `GET /v1/accounts/{name}/positions`, assert all three appear with accurate first/last dates and that `_links.self` is present; seed a capital-only account (via `/capital` ingestion, no `/ladder` call) and assert `422`; assert `404` for a wholly unknown account; run `pytest tests/features/list_account_positions.feature -m us2` to confirm all green; depends on T013

**Checkpoint**: US2 complete — positions-enumeration endpoint independently tested.

---

## Phase 5: User Story 3 — Discover Which Attributes the Position Endpoint Accepts (Priority: P3)

**Goal**: A caller can discover this endpoint's six supported attribute names and their meanings without hard-coding or guessing the list, and confirm `capital` is excluded.

**Independent Test**: `GET /v1/positions/attributes` with no other setup returns 200 with exactly the six attributes User Story 1 accepts, `capital` absent.

### Tests for User Story 3 ⚠️ Write and verify FAILING before implementing

- [X] T015 [P] [US3] Write Gherkin feature file `tests/features/position_attribute_metadata.feature` with the one US3 scenario from spec: "Retrieve the list of supported position-attribute names"; tag `@us3`

### Implementation for User Story 3

- [X] T016 [US3] Add `GET /positions/attributes` handler to `app/api/position_timeseries.py` — returns `AttributeMetadataResponse` (imported from `app/models/timeseries.py`) built directly from `position_attributes.ATTRIBUTE_DEFINITIONS`, with `_links` containing only `self`; no DI beyond the module import; depends on T009 (same router file), T003
- [X] T017 [US3] Write BDD step implementations in `tests/steps/position_attribute_metadata_steps.py` — assert all six attribute names/descriptions are present, that `capital` does not appear, and that `_links.self` is present; add an explicit SC-005 cross-check assertion that the returned attribute-name set is exactly `position_attributes.SUPPORTED_ATTRIBUTES` (the same set `PositionTimeSeriesService` validates against); run `pytest tests/features/position_attribute_metadata.feature -m us3` to confirm green; depends on T016

**Checkpoint**: All three user stories complete and independently tested.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Code quality gates, contract sync, edge-case coverage, performance, and a full regression gate.

- [X] T018 [P] Run `ruff check app/ tests/` and `ruff format app/ tests/` on all new/changed files (`app/exceptions.py`, `app/models/position_timeseries.py`, `app/services/position_attributes.py`, `app/services/positions_service.py`, `app/services/position_timeseries_service.py`, `app/api/position_timeseries.py`, `app/main.py`, and all new test files); fix all reported issues including any `D` (pydocstyle) violations (Constitution III); run `mypy --strict app/`; resolve all type errors; confirm zero errors in all three checks
- [X] T019 [P] Verify OpenAPI spec accuracy: start the server, fetch `http://localhost:8000/openapi.json`, compare the generated `position`/`positions`/`positions/attributes` paths and schemas against `specs/005-position-timeseries-api/contracts/openapi.yaml`
- [X] T020 Run `quickstart.md` validation end-to-end: start the service, ingest (or reuse already-ingested) real position ladder data, execute each documented `curl` command from `specs/005-position-timeseries-api/quickstart.md`, confirm responses match the documented examples and every listed failure mode, and record/fix any discrepancies in `quickstart.md`
- [X] T021 [P] Add the remaining edge-case scenarios not already covered by US1/US2's Gherkin to the existing shared `tests/features/validation.feature` (reusing the `@validation` tag): duplicate `position` query values are treated as a single position (no duplicate entries), a valid position with zero overlap with the resolved date range produces zero entries for it without failing the whole request, position-name matching is case-sensitive (a differently-cased request value does not match), a single business day (`start == end`) request succeeds; add corresponding steps to `tests/steps/validation_steps.py`; run `pytest tests/features/validation.feature -m validation` to confirm all green
- [X] T022 [P] Add a performance smoke test to `tests/unit/test_performance.py`: ingest a synthetic account with 50 positions over a 5-year date range, then time a `GET .../position` request with no `position` filter (all 50) spanning the full range — assert completion within 10s (SC-001); time three separate rejection paths and assert each completes within 1s (SC-004): a request naming an unsupported attribute, a request for a wholly unknown account name, and a request with an invalid (start-after-end) date range
- [X] T023 Run the full test suite (`pytest -q`) and confirm zero regressions against the pre-existing baseline (including the one already-documented pre-existing timing-flaky test noted in feature 004's tasks.md, `test_idempotent_resubmit_within_1_second`, which is unrelated to this feature)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks — nothing to wait on
- **Foundational (Phase 2)**: Blocks all user stories. T001–T003 have no ordering constraint; T004 depends on T002; T005 depends on T002, T004
- **US1 (Phase 3)**: Depends on Phase 2 — MVP delivery point
- **US2 (Phase 4)**: Depends on T009 (same `app/api/position_timeseries.py` file) — otherwise only depends on Phase 2 (`PositionsService`)
- **US3 (Phase 5)**: Depends on T009 (same router file) — otherwise only depends on Phase 2 (`position_attributes.py`)
- **Polish (Phase 6)**: Depends on all three user story phases being complete

### Within Phase 3 (US1) Dependencies

- T006, T007 → parallel (write tests first; no app code needed)
- T008 → after T007 exists (makes it pass); depends on T001, T002, T003, T005
- T009 → after T008
- T010 → after T009, T001
- T011 → after T010

### Parallel Opportunities

```
Phase 2 parallel group: T001, T002, T003 (independent files)
T004 follows T002; T005 follows T002, T004

Phase 3 test-writing group: T006, T007 (both parallel; no implementation dependency between them)

Phase 4 (T012) can be written in parallel with any Phase 3 implementation task
Phase 5 (T015) can be written in parallel with any Phase 3/4 implementation task

T013 and T016 both touch app/api/position_timeseries.py (same file as T009) — sequence them
after T009 lands, but they are independent additions to that file and can be done in either
order relative to each other

Phase 6 parallel group: T018, T019, T021, T022 (independent); T020 and T023 are sequential
final gates
```

---

## Parallel Example: User Story 1

```bash
# Launch the test-writing tasks for User Story 1 together:
Task: "Write Gherkin feature file tests/features/retrieve_position_timeseries.feature"
Task: "Write failing unit tests in tests/unit/test_position_timeseries_service.py"

# T008 (PositionTimeSeriesService) depends on T005 (PositionsService) already being green,
# and on T001/T002/T003 (exception, models, attribute definitions) — all from Phase 2.
```

---

## Implementation Strategy

### MVP: User Story 1 Only

1. Complete Phase 2: Foundational (CRITICAL — blocks everything; Phase 1 has no tasks)
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**:
   - `pytest tests/unit/test_positions_service.py tests/unit/test_position_timeseries_service.py tests/features/retrieve_position_timeseries.feature -m us1`
   - `GET` a real position time series for a known account via curl; verify entries, per-position forward-fill/divestment behaviour, and `pnl` arithmetic
4. Proceed to Phase 4 (US2) and Phase 5 (US3) once US1 is green — both may proceed in parallel

### Incremental Delivery

1. Phase 2 → Foundation ready
2. Phase 3 (US1) → per-position time series works end-to-end → **demo-able MVP**
3. Phase 4 (US2) → position enumeration works
4. Phase 5 (US3) → attribute discovery works
5. Phase 6 → code quality gates pass, OpenAPI/quickstart verified, edge cases and
   performance covered, full-suite regression gate passes

---

## Notes

- `[P]` = parallelisable (different files, no blocking dependency)
- `[Story]` maps task to user story for traceability
- BDD test tasks MUST be written and verified to FAIL before implementation tasks begin
- Use `pytest -m us1` / `-m us2` / `-m us3` to run one story's tests in isolation; the
  `us1`–`us4` markers registered in `pyproject.toml` (feature 004) are reused here — no new
  marker registration needed
- Commit after each checkpoint (end of each user story phase)
- `data/` and `logs/` remain gitignored — never commit runtime artefacts
- This feature requires zero changes to any existing file other than `app/main.py` (router
  registration + one new exception handler) — `AccountsService`, `TimeseriesDateResolver`,
  `expand_business_days()`, and `LadderRepository.read_full_df()` are all reused unmodified
  (plan.md, research.md)
- T008's `still_held = (last_date == summary.position_ladder.to_date)` check is the crux of
  this feature's most subtle behaviour (FR-013, resolved via a mid-planning clarification —
  see spec.md's Clarifications section); T007's two dedicated tests
  (`test_still_held_position_forward_filled_through_resolved_end` /
  `test_divested_position_not_forward_filled_past_its_own_last_row`) are the regression guard
  for it and MUST both be green before T008 is considered done
