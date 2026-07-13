---
description: "Task list for Account Time Series API feature"
---

# Tasks: Account Time Series API

**Input**: Design documents from `/specs/004-account-timeseries-api/`
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
section, and no new pytest marker — BDD scenarios reuse the existing `us1`–`us4` markers
already registered in `pyproject.toml`. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required by every user story. No user story work begins until this phase is complete.

**⚠️ CRITICAL**: All user story phases depend on this phase being fully complete.

- [X] T001 [P] Create `app/validators/account_name.py` with `ACCOUNT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")` and `validate_account_name(account_name: str) -> None` (raises `InvalidAccountNameError`), extracted verbatim from `app/api/ladder.py`'s existing `_ACCOUNT_NAME_PATTERN`/`_validate_account_name`; refactor `app/api/ladder.py` and `app/api/capital.py` to import and use this shared module, deleting their local copies (research.md §4); this MUST be behavior-preserving — run `pytest tests/steps/ingest_ladder_steps.py tests/steps/retrieve_ladder_steps.py tests/steps/ingest_capital_steps.py tests/steps/retrieve_capital_steps.py tests/features/validation.feature -q` and confirm all still pass unmodified
- [X] T002 [P] Create `app/api/dependencies.py` with `get_ladder_repository(settings: Settings = Depends(get_settings)) -> LadderRepository` and `get_capital_repository(settings: Settings = Depends(get_settings)) -> CapitalRepository`, extracted verbatim from `app/api/ladder.py`'s `_get_repository` and `app/api/capital.py`'s `_get_capital_repository`; refactor both files to import and use these shared providers, deleting their local copies (research.md §4); this MUST be behavior-preserving — run the same test command as T001 and confirm all still pass unmodified
- [X] T003 [P] Add five new exception classes to `app/exceptions.py`: `NoAttributesRequestedError(message: str | None = None)`; `UnsupportedAttributeError(requested: list[str], supported: list[str], message: str | None = None)`; `FutureEndDateError(end: date, today: date, message: str | None = None)`; `InvalidDateRangeError(start: date, end: date, message: str | None = None)`; `MissingRequiredSourceError(account_name: str, attribute: str, source: str, message: str | None = None)` — each pre-formats a descriptive `.message` in `__init__`, following the existing `EmptyCapitalDateRangeError` pattern (data-model.md)
- [X] T004 [P] Create `app/models/timeseries.py` with: `TimeSeriesEntry` (Pydantic `BaseModel` with `model_config = ConfigDict(extra="allow")` and a single declared field `date: date` — additional attribute keys are set dynamically per entry, research.md §5); `TimeSeriesResponse` (`account_name: str`, `attributes: list[str]`, `from_date: date`, `to_date: date`, `entries: list[TimeSeriesEntry]`, `links: dict[str, str] = Field(alias="_links")`); `AttributeDefinition` (`name: str`, `description: str`, `source: str`); `AttributeMetadataResponse` (`attributes: list[AttributeDefinition]`, `links: dict[str, str] = Field(alias="_links")`); `AccountResourceRange` (`from_date: date`, `to_date: date`); `AccountSummary` (`account_name: str`, `capital_ledger: AccountResourceRange | None`, `position_ladder: AccountResourceRange | None`); `AccountsResponse` (`accounts: list[AccountSummary]`, `links: dict[str, str] = Field(alias="_links")`); all response models use `model_config = ConfigDict(populate_by_name=True)` matching `app/models/ladder.py`'s existing convention (data-model.md)
- [X] T005 [P] Create `app/services/timeseries_attributes.py` — the single source of truth for the five supported attributes (data-model.md's Attribute table): a module-level `ATTRIBUTE_DEFINITIONS: list[AttributeDefinition]` (imported from `app.models.timeseries`) covering `capital`, `income`, `book_cost`, `market_value`, `pnl` with their descriptions and `source` strings; a `SUPPORTED_ATTRIBUTES: frozenset[str]` derived from it; a `requires_capital_ledger(attribute: str) -> bool` and `requires_position_ladder(attribute: str) -> bool` helper pair; a `validate_attributes(attributes: list[str]) -> None` that raises `NoAttributesRequestedError` if `attributes` is empty or `UnsupportedAttributeError` (naming every invalid entry, not just the first) if any name is outside `SUPPORTED_ATTRIBUTES`
- [X] T006 [P] Add `read_full_df(account_name: str) -> pd.DataFrame` (reads `ladder.xlsx` and returns every stored column, including `market_value` — a new method, since the existing `read_ladder_df` deliberately drops enrichment columns for the refresh path and must not be changed) and `list_accounts(self) -> list[str]` (scans `data_dir` for immediate subdirectories containing `meta.json`, returning their names) to `app/repositories/ladder_repository.py`
- [X] T007 [P] Add `read_df(account_name: str) -> pd.DataFrame` (reads `capital.xlsx` and returns `[date, capital, income, book_value]`) and `list_accounts(self) -> list[str]` (scans `data_dir` for immediate subdirectories containing `capital_meta.json`, returning their names) to `app/repositories/capital_repository.py`
- [X] T008 [P] Write failing unit tests in `tests/unit/test_accounts_service.py`: `test_list_known_accounts_is_union_of_both_repositories()`, `test_get_summary_includes_both_resources_when_both_ingested()`, `test_get_summary_has_none_capital_ledger_when_only_ladder_ingested()`, `test_get_summary_has_none_position_ladder_when_only_capital_ingested()`, `test_list_summaries_covers_every_known_account()`; use `tmp_path`-backed real `LadderRepository`/`CapitalRepository` instances with manually-ingested fixture data (via their `write()` methods) rather than mocks, matching this codebase's existing repository-testing style; import `AccountsService` from `app/services/accounts_service.py` (fails at import until T009)
- [X] T009 Implement `app/services/accounts_service.py` — `AccountsService(ladder_repo: LadderRepository, capital_repo: CapitalRepository)` with `list_known_accounts() -> list[str]` (sorted union of both repositories' `list_accounts()`), `get_summary(account_name: str) -> AccountSummary` (reads each repository's meta if `exists()`, else `None` for that resource), `list_summaries() -> list[AccountSummary]` (one `get_summary()` per `list_known_accounts()` entry); depends on T004, T006, T007; run T008 tests to verify they pass

**Checkpoint**: Foundation complete — all user story phases may now proceed. T001–T007 have no ordering constraint between them; T008 depends on T004/T006/T007 (needs the models and `list_accounts()`/`read_df` methods to build realistic fixtures); T009 depends on T008 existing (makes it pass).

---

## Phase 3: User Story 1 — Retrieve a Multi-Attribute Time Series for an Account (Priority: P1) 🎯 MVP

**Goal**: Given an account name and one or more attributes, return one JSON entry per business day joining the capital ledger and position ladder, forward-filled to today where needed.

**Independent Test**: For an account with both resources ingested, `GET /v1/accounts/{name}/timeseries?attribute=capital&attribute=market_value&attribute=pnl` over a known range returns 200 with one entry per business day, each carrying exactly the three requested values, `pnl` arithmetically consistent with the other two.

### Tests for User Story 1 ⚠️ Write and verify FAILING before implementing

- [X] T010 [P] [US1] Write Gherkin feature file `tests/features/retrieve_timeseries.feature` with all eight US1 scenarios from `spec.md`: "Retrieve a time series for a known account and valid attributes", "Underlying data older than today is forward-filled, not treated as an error", "Requesting an attribute whose required source was never ingested is rejected", "Missing mandatory attribute is rejected", "Unknown account name is rejected", "Start date after end date is rejected", "End date in the future is rejected", "Non-business-day start and end dates are silently adjusted" — use exact Gherkin from spec; tag each `@us1`
- [X] T011 [P] [US1] Write failing unit tests in `tests/unit/test_timeseries_date_resolver.py`: `test_business_day_input_unchanged()`, `test_weekend_start_adjusts_forward_to_monday()`, `test_weekend_end_adjusts_forward_capped_at_today_when_today_is_a_weekend()` (inject a Saturday as `today` directly — do NOT call `date.today()` inside the resolver; it MUST accept `today` as an explicit parameter so this case is deterministically testable, avoiding the live-`date.today()` flakiness pattern already fixed once in this codebase), `test_default_end_is_the_business_day_before_today()`, `test_default_start_is_the_later_of_multiple_required_sources_earliest_dates()`, `test_resolved_start_after_resolved_end_raises_invalid_date_range_error()`; import `TimeseriesDateResolver` from `app/services/timeseries_date_resolver.py` (fails at import until T013)
- [X] T012 [P] [US1] Write failing unit tests in `tests/unit/test_timeseries_service.py`: `test_joins_capital_and_market_value_by_date()`, `test_pnl_equals_income_plus_market_value_minus_book_cost()`, `test_forward_fills_past_capital_ledgers_own_latest_date()`, `test_forward_fills_past_ladders_own_latest_date()`, `test_market_value_requested_on_ladder_only_account_succeeds()` (positive case — capital ledger not required), `test_capital_requested_on_ladder_only_account_raises_missing_required_source_error()`, `test_pnl_requested_with_only_one_source_raises_missing_required_source_error()`, `test_start_before_required_sources_earliest_date_raises_missing_required_source_error()`, `test_response_entries_contain_only_requested_attribute_keys()` (no null/extra keys for unrequested attributes); use `tmp_path`-backed real repositories with fixture data written via their `write()` methods; import `TimeSeriesService` from `app/services/timeseries_service.py` (fails at import until T014)

### Implementation for User Story 1

- [X] T013 [US1] Implement `app/services/timeseries_date_resolver.py` — `TimeseriesDateResolver` with a method resolving `(raw_start: date | None, raw_end: date | None, today: date, required_source_earliest_dates: list[date]) -> tuple[date, date]`: raise `FutureEndDateError` if `raw_end` is supplied and > `today`; default `end = raw_end or pd.bdate_range(end=today, periods=2)[0].date()` (FR-007); default `start = raw_start or max(required_source_earliest_dates)` (FR-006); adjust both via `pd.bdate_range(start=d, periods=1)[0].date()`, capping back to `pd.bdate_range(end=today, periods=1)[0].date()` if that adjustment exceeds `today` (FR-008, research.md §3); raise `InvalidDateRangeError` if resolved start > resolved end (FR-009); depends on T003; run T011 tests to verify they pass
- [X] T014 [US1] Implement `app/services/timeseries_service.py` — `TimeSeriesService(ladder_repo: LadderRepository, capital_repo: CapitalRepository, accounts_service: AccountsService, date_resolver: TimeseriesDateResolver)` with `get_series(account_name: str, attributes: list[str], start: date | None, end: date | None, today: date) -> TimeSeriesResponse`: call `timeseries_attributes.validate_attributes(attributes)`; determine required sources via `requires_capital_ledger`/`requires_position_ladder` across all requested attributes; call `accounts_service.get_summary(account_name)`, raising `AccountNotFoundError(account_name, message=f"No capital ledger or position ladder has been ingested for account '{account_name}'.")` if both resources are `None` (FR-002); for each required source not present in the summary, raise `MissingRequiredSourceError`; resolve dates via `TimeseriesDateResolver` using each required source's own `from_date` (FR-006); for each required source, raise `MissingRequiredSourceError` if the resolved start precedes that source's own `from_date` (FR-015); if capital ledger required, `capital_repo.read_df()` then `expand_business_days(df, ["capital","income","book_value"], resolved_start, resolved_end)`; if position ladder required, `ladder_repo.read_full_df()`, `.groupby("date", as_index=False)["market_value"].sum()`, then `expand_business_days(agg, ["market_value"], resolved_start, resolved_end)` (research.md §1–§2); if BOTH sources are required, join the two expanded frames on `date`; if only ONE source is required (e.g. `market_value` alone on a ladder-only account, or `capital`/`income`/`book_cost` alone with no ladder involvement at all — both explicitly covered by T012's tests), build entries directly from that single expanded frame — there is nothing to join; compute `pnl = income + market_value - book_cost` per row if requested (only reachable when both sources were required, per FR-014); build one `TimeSeriesEntry` per row containing only the requested attribute keys plus `date`; return a populated `TimeSeriesResponse` with `_links` (`self`, `attributes` → `/v1/timeseries/attributes`, `accounts` → `/v1/accounts`); bind and log a structlog event per request (`timeseries_request`, with account_name, attributes, resolved date range, row_count, outcome), following the existing `logger.bind(...)` pattern (Constitution IV); depends on T004, T005, T009, T013; run T012 tests to verify they pass
- [X] T015 [US1] Create `app/api/timeseries.py` — `APIRouter(prefix="/v1", tags=["Timeseries"])`; `GET /accounts/{account_name}/timeseries` handler: validate `account_name` via `app/validators/account_name.py`, accept `attribute: list[str] = Query(...)`, `start: date | None = Query(default=None)`, `end: date | None = Query(default=None)`, call `TimeSeriesService.get_series(..., today=date.today())`, return the `TimeSeriesResponse`; wire `_get_timeseries_service(...)` via `Depends`, composing `get_ladder_repository`/`get_capital_repository` (from `app/api/dependencies.py`), a fresh `AccountsService`, and a fresh `TimeseriesDateResolver`; depends on T014
- [X] T016 [US1] Register `timeseries.router` and exception handlers for `NoAttributesRequestedError`, `UnsupportedAttributeError`, `FutureEndDateError`, `InvalidDateRangeError`, `MissingRequiredSourceError` (all 422, via the existing `_problem()` helper, following the pattern of `EmptyCapitalDateRangeError`'s handler) in `app/main.py`; depends on T015, T003
- [X] T017 [US1] Write BDD step implementations in `tests/steps/retrieve_timeseries_steps.py` for all eight US1 scenarios — seed fixtures by POSTing to the existing `/ladder` and `/capital` ingestion endpoints via `app_client` (not by writing files directly, to exercise the real ingestion→retrieval path), then `GET` the timeseries endpoint; assert response shape, entry counts, forward-filled values, each error status/detail, and (per FR-016, spec.md's first scenario) that `_links.self`, `_links.attributes`, and `_links.accounts` are all present on a successful response; run `pytest tests/features/retrieve_timeseries.feature -m us1` to confirm all green; depends on T016

**Checkpoint**: US1 complete — main time series endpoint fully functional and BDD-tested independently.

---

## Phase 4: User Story 2 — Discover Available Attributes via Metadata (Priority: P2)

**Goal**: A caller can discover the five supported attribute names, their meanings, and their sources without external documentation.

**Independent Test**: `GET /v1/timeseries/attributes` with no other setup returns 200 with exactly the five attributes User Story 1 accepts, each with a description.

### Tests for User Story 2 ⚠️ Write and verify FAILING before implementing

- [X] T018 [P] [US2] Write Gherkin feature file `tests/features/timeseries_attribute_metadata.feature` with the one US2 scenario from spec: "Retrieve the list of supported time series attributes"; tag `@us2`

### Implementation for User Story 2

- [X] T019 [US2] Add `GET /timeseries/attributes` handler to `app/api/timeseries.py` — returns `AttributeMetadataResponse` built directly from `timeseries_attributes.ATTRIBUTE_DEFINITIONS`, with `_links` containing only `self`; depends on T015 (same router file)
- [X] T020 [US2] Write BDD step implementations in `tests/steps/timeseries_attribute_metadata_steps.py` — assert all five attribute names/descriptions are present, and (per FR-017, spec.md's scenario) that `_links.self` is present; add an explicit SC-004 cross-check assertion that the returned attribute-name set is exactly `timeseries_attributes.SUPPORTED_ATTRIBUTES` (the same set `TimeSeriesService` validates against); run `pytest tests/features/timeseries_attribute_metadata.feature -m us2` to confirm green; depends on T019

**Checkpoint**: US2 complete — metadata endpoint independently tested.

---

## Phase 5: User Story 3 — Enumerate Ingested Accounts and Their Date Ranges (Priority: P2)

**Goal**: A caller can list every account with at least one ingested resource, with accurate per-resource date ranges.

**Independent Test**: With one account fully ingested (both resources) and one capital-only account, `GET /v1/accounts` lists both, the capital-only account showing `position_ladder: null`.

### Tests for User Story 3 ⚠️ Write and verify FAILING before implementing

- [X] T021 [P] [US3] Write Gherkin feature file `tests/features/list_accounts.feature` with both US3 scenarios from spec: "Enumerate accounts with both resources ingested", "Enumerate an account with only one resource ingested"; tag each `@us3`

### Implementation for User Story 3

- [X] T022 [US3] Create `app/api/accounts.py` — `APIRouter(prefix="/v1", tags=["Accounts"])`; `GET /accounts` handler returning `AccountsResponse` built from `AccountsService.list_summaries()`, with `_links` containing only `self`; wire `AccountsService` via `Depends`, composing `get_ladder_repository`/`get_capital_repository`; depends on T009
- [X] T023 [US3] Register `accounts.router` in `app/main.py`; depends on T022
- [X] T024 [US3] Write BDD step implementations in `tests/steps/list_accounts_steps.py` — seed one dual-resource account and one capital-only account via the existing ingestion endpoints, `GET /v1/accounts`, assert both appear with accurate date ranges, that the capital-only account's `position_ladder` is `null`, and (per FR-018, spec.md's first scenario) that `_links.self` is present; run `pytest tests/features/list_accounts.feature -m us3` to confirm green; depends on T023

**Checkpoint**: All three user stories complete and independently tested.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Code quality gates, contract sync, edge-case coverage, performance, and a full regression gate on the shared-module refactor.

- [X] T025 [P] Run `ruff check app/ tests/` and `ruff format app/ tests/` on all new/changed files (`app/exceptions.py`, `app/models/timeseries.py`, `app/services/timeseries_attributes.py`, `app/services/timeseries_date_resolver.py`, `app/services/accounts_service.py`, `app/services/timeseries_service.py`, `app/repositories/ladder_repository.py`, `app/repositories/capital_repository.py`, `app/validators/account_name.py`, `app/api/dependencies.py`, `app/api/timeseries.py`, `app/api/accounts.py`, `app/api/ladder.py`, `app/api/capital.py`, `app/main.py`, and all new test files); fix all reported issues including any `D` (pydocstyle) violations (Constitution III); run `mypy --strict app/`; resolve all type errors; confirm zero errors in all three checks
- [X] T026 [P] Verify OpenAPI spec accuracy: start the server, fetch `http://localhost:8000/openapi.json`, compare the generated `timeseries`/`accounts` paths and schemas against `specs/004-account-timeseries-api/contracts/openapi.yaml`; no project-root `openapi.yaml` exists to update (confirmed absent in feature 003)
- [X] T027 Run `quickstart.md` validation end-to-end: start the service, ingest (or reuse already-ingested) real `HL-SIPP`/`HL-ISA` data, execute each documented `curl` command from `specs/004-account-timeseries-api/quickstart.md`, confirm responses match the documented examples and every listed failure mode, and record/fix any discrepancies in `quickstart.md`
- [X] T028 [P] Add the remaining edge-case scenarios not already covered by US1's Gherkin to the existing shared `tests/features/validation.feature` (reusing the `@validation` tag): `market_value` requested on a ladder-only account succeeds (positive case), a `start` earlier than a required source's earliest recorded date is rejected, `pnl` requested with only one source ingested is rejected, an unsupported attribute name is rejected, a single business day (`start == end`) request succeeds with exactly one entry; add corresponding steps to `tests/steps/validation_steps.py`; run `pytest tests/features/validation.feature -m validation` to confirm all green
- [X] T029 [P] Add performance smoke tests to `tests/unit/test_performance.py`: ingest a synthetic ~10-year capital ledger and position ladder, then time a `GET .../timeseries` request spanning the full range — assert completion within 5s (SC-001); time a request naming an unsupported attribute — assert rejection within 1s (SC-003)
- [X] T030 Run the full test suite (`pytest -q`) and confirm zero regressions beyond the one pre-existing, already-documented timing-flaky test (`test_idempotent_resubmit_within_1_second`) — this is the final regression gate on the T001/T002 shared-module extraction affecting `ladder.py`/`capital.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks — nothing to wait on
- **Foundational (Phase 2)**: Blocks all user stories. T001–T007 have no ordering constraint; T008 depends on T004/T006/T007; T009 depends on T008
- **US1 (Phase 3)**: Depends on Phase 2 — MVP delivery point
- **US2 (Phase 4)**: Depends on T015 (same `app/api/timeseries.py` file) — otherwise only depends on Phase 2 (`timeseries_attributes.py`)
- **US3 (Phase 5)**: Depends on T009 only — independent of US1/US2, could proceed in parallel with Phase 3 once Phase 2 is done
- **Polish (Phase 6)**: Depends on all three user story phases being complete

### Within Phase 3 (US1) Dependencies

- T010, T011, T012 → parallel (write tests first; no app code needed)
- T013 → after T011 exists (makes it pass); depends on T003
- T014 → after T012 exists (makes it pass); depends on T004, T005, T009, T013
- T015 → after T014
- T016 → after T015, T003
- T017 → after T016

### Parallel Opportunities

```
Phase 2 parallel group: T001, T002, T003, T004, T005, T006, T007 (all independent files)
T008 follows T004/T006/T007; T009 follows T008

Phase 3 test-writing group: T010, T011, T012 (all parallel)
Phase 3: T013 and T014 are NOT parallel with each other's prerequisites — T013 must precede
T014 (TimeSeriesService depends on TimeseriesDateResolver)

Phase 4 (T018) can be written in parallel with any Phase 3 implementation task
Phase 5 (T021) can be written in parallel with any Phase 3/4 implementation task; T022–T024
only depend on Phase 2 (T009), so Phase 5 can proceed fully in parallel with Phase 3/4 if
staffed separately

Phase 6 parallel group: T025, T026, T028, T029 (independent); T027 and T030 are sequential
final gates
```

---

## Parallel Example: User Story 1

```bash
# Launch the test-writing tasks for User Story 1 together:
Task: "Write Gherkin feature file tests/features/retrieve_timeseries.feature"
Task: "Write failing unit tests in tests/unit/test_timeseries_date_resolver.py"
Task: "Write failing unit tests in tests/unit/test_timeseries_service.py"

# T013 (TimeseriesDateResolver) must land before T014 (TimeSeriesService) starts, since
# TimeSeriesService depends on it directly.
```

---

## Implementation Strategy

### MVP: User Story 1 Only

1. Complete Phase 2: Foundational (CRITICAL — blocks everything; Phase 1 has no tasks)
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**:
   - `pytest tests/unit/test_timeseries_date_resolver.py tests/unit/test_timeseries_service.py tests/unit/test_accounts_service.py tests/features/retrieve_timeseries.feature -m us1`
   - `GET` a real timeseries for `HL-SIPP` via curl; verify entries, forward-fill, and `pnl` arithmetic
4. Proceed to Phase 4 (US2) and Phase 5 (US3) once US1 is green — both may proceed in parallel

### Incremental Delivery

1. Phase 2 → Foundation ready (including the `ladder.py`/`capital.py` refactor, verified non-regressive)
2. Phase 3 (US1) → time series joins work end-to-end → **demo-able MVP**
3. Phase 4 (US2) → attribute discovery works
4. Phase 5 (US3) → account enumeration works
5. Phase 6 → code quality gates pass, OpenAPI/quickstart verified, edge cases and performance
   covered, full-suite regression gate passes

---

## Notes

- `[P]` = parallelisable (different files, no blocking dependency)
- `[Story]` maps task to user story for traceability
- BDD test tasks MUST be written and verified to FAIL before implementation tasks begin
- Use `pytest -m us1` / `-m us2` / `-m us3` to run one story's tests in isolation; the
  `us1`–`us4` markers registered in `pyproject.toml` are reused here — no new marker
  registration needed
- Commit after each checkpoint (end of each user story phase)
- `data/` and `logs/` remain gitignored — never commit runtime artefacts
- T001/T002 are the two behaviour-preserving refactors this feature requires (research.md §4);
  both carry an explicit regression command in their own task description, and T030 re-runs the
  full suite as a final gate
- T013/T014's `today: date` parameter (never `date.today()` called internally) is what makes
  the weekend-adjustment edge case in T011 deterministically testable — this directly avoids
  repeating the live-`date.today()` flakiness pattern already found and fixed once in this
  codebase (`test_equity_excluded_after_quantity_zero`, feature 003 implementation)
