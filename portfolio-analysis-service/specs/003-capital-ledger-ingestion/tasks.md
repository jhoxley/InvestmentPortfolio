---
description: "Task list for Capital Ledger Ingestion feature"
---

# Tasks: Capital Ledger Ingestion

**Input**: Design documents from `/specs/003-capital-ledger-ingestion/`
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

**Purpose**: Project initialization and configuration scaffolding.

No tasks required. This feature introduces no new runtime dependency, no new `config.yaml`
section, and no new pytest marker — BDD scenarios reuse the existing `us1`–`us4` markers already
registered in `pyproject.toml` (from feature 001). Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required by every user story. No user story work begins until this phase is complete.

**⚠️ CRITICAL**: All user story phases depend on this phase being fully complete.

- [X] T001 [P] Add `EmptyCapitalDateRangeError(account_name: str, earliest_date: date, latest_date: date, message: str | None = None)` to `app/exceptions.py`, pre-formatting a `.message` explaining that the recorded `[earliest_date, latest_date]` range contains no business days — follow the existing `EmptyDateRangeError` pattern (data-model.md, research.md §4) but do NOT reuse or subclass `EmptyDateRangeError` itself; its semantics are "today-relative" and don't apply here
- [X] T002 [P] Create `app/models/capital.py` with `CapitalIngestionSummary` (`account_name`, `status: Literal["created", "refreshed"]`, `row_count: int = Field(ge=0)`, `from_date: date`, `to_date: date`, `ingested_at: datetime`, `links: Links = Field(alias="_links")`) and `CapitalSummary` (same fields minus `status`); both use `model_config = ConfigDict(populate_by_name=True)`; import and reuse `Links` from `app.models.ladder` rather than redefining it (data-model.md)
- [X] T003 [P] Write failing unit tests in `tests/unit/test_business_day_expansion.py` for the shared expansion helper: `test_forward_fills_across_gap_days()`, `test_filters_result_to_business_days_only()`, `test_start_equals_end_on_a_business_day_produces_one_row()`, `test_start_equals_end_on_a_weekend_produces_empty_result()`, `test_reindexes_over_full_calendar_range_before_filtering()` (confirms a weekend activity date is still captured via ffill before the business-day filter is applied, matching `LadderExpander`'s existing weekend-carry behaviour); import `expand_business_days` from `app/services/business_day_expansion.py` (fails at import until T004) — this closes the gap where the shared helper (the literal mechanism satisfying the spec's "same code/logic" instruction) previously had no isolated unit test of its own, only indirect coverage via its two callers
- [X] T004 Create `app/services/business_day_expansion.py` with `expand_business_days(df: pd.DataFrame, value_columns: list[str], start: date, end: date) -> pd.DataFrame` — extract the reindex/ffill mechanic currently inlined in `LadderExpander.expand()`'s per-sub-account loop (`app/services/ladder_expander.py`): set a `DatetimeIndex` from `df["date"]`, reindex over `pd.date_range(start, end)`, `ffill()`, filter down to `pd.bdate_range(start, end)`, restore a `date` column of `date` objects, return a DataFrame with columns `["date", *value_columns]` (research.md §1); this is a pure extraction — do not change the reindex/ffill behavior itself; depends on T003 (makes those tests pass)
- [X] T005 Refactor `app/services/ladder_expander.py`'s `LadderExpander.expand()` to call `expand_business_days()` from T004 for each sub-account group's reindex/ffill step, instead of its own inlined block; the surrounding grouping, closure-rule, and `today`-based end-date computation are unchanged; this MUST be behavior-preserving — run `pytest tests/unit/test_ladder_expander.py` and confirm it still passes unmodified (depends on T004)
- [X] T006 [P] Create `app/repositories/capital_repository.py` with `CapitalMeta` (Pydantic: `account_name: str`, `checksum: str`, `row_count: int`, `from_date: date`, `to_date: date`, `ingested_at: datetime`) and `CapitalRepository(data_dir: Path)` mirroring `LadderRepository`'s methods — `exists(account_name) -> bool`, `read_meta(account_name) -> CapitalMeta`, `write(account_name, df, meta) -> None` (atomic write via temp file + `os.replace`, writing `data_dir/{account_name}/capital.xlsx` + `data_dir/{account_name}/capital_meta.json`), `read_xlsx(account_name) -> Path`, and `write_meta(account_name, meta) -> None` (updates only `capital_meta.json`, used by the checksum-match refresh path in T012 — no XLSX rewrite); no `read_ladder_df`-equivalent method is needed (no re-enrichment step exists for this resource) (data-model.md)

**Checkpoint**: Foundation complete — all user story phases may now proceed. Note: T003 → T004 → T005 is a strict chain (write the failing test, then the helper, then the refactor that consumes it); T001, T002, T003, T006 have no ordering constraint between them.

---

## Phase 3: User Story 1 — Submit a New Capital Ledger for Processing (Priority: P1) 🎯 MVP

**Goal**: Accept, validate, expand, and persist a new capital ledger; return an ingestion summary with a download link.

**Independent Test**: `POST /v1/accounts/test-portfolio/capital` with a valid XLSX (columns `date`, `capital`, `income`, `book_value`) → 201 Created with JSON summary; `data/test-portfolio/capital.xlsx` exists with one row per business day from the earliest through latest recorded date; `data/test-portfolio/capital_meta.json` contains a matching checksum.

### Tests for User Story 1 ⚠️ Write and verify FAILING before implementing

- [X] T007 [P] [US1] Write Gherkin feature file `tests/features/ingest_capital.feature` containing only the three US1 scenarios from `spec.md`: "Successful ingestion of a new capital ledger", "Capital values forward-fill across days with no recorded observation", "Expansion range is bounded by the recorded data, not by today's date" — use exact Gherkin from spec; tag each `@us1`
- [X] T008 [P] [US1] Write failing unit tests in `tests/unit/test_capital_ledger_validator.py`: `test_valid_file_passes()`, `test_missing_column_raises()` (each of the 4 required columns: `date`, `capital`, `income`, `book_value`), `test_non_numeric_value_raises()` (each of `capital`, `income`, `book_value`), `test_unparseable_date_raises()`, `test_empty_dataframe_raises()`, `test_recorded_range_with_no_business_days_raises_empty_capital_date_range_error()` (e.g. a single row whose only date is a Saturday); import `CapitalLedgerValidator` from `app/validators/capital_ledger.py` (fails at import until T010)
- [X] T009 [P] [US1] Write failing unit tests in `tests/unit/test_capital_ledger_expander.py`: `test_forward_fill_across_gap_days()`, `test_business_days_only_in_output()`, `test_range_bounded_to_min_and_max_recorded_date()` (asserts the expansion does NOT extend past `max(date)`, contrasting with `LadderExpander`'s `today`-based ceiling), `test_single_recorded_date_on_a_business_day_produces_one_row()`, `test_no_grouping_or_closure_rule_applied()` (asserts output has no `sub_account`-like column and no rows are ever dropped for a zero-valued column, unlike `LadderExpander`'s Cash/equity closure rule); import `CapitalLedgerExpander` from `app/services/capital_ledger_expander.py` (fails at import until T011)

### Implementation for User Story 1

- [X] T010 [US1] Implement `app/validators/capital_ledger.py` — `CapitalLedgerValidator` class with `validate(df: pd.DataFrame, account_name: str) -> None` (no `today` parameter — contrast with `LedgerValidator`): check required columns `["date", "capital", "income", "book_value"]` present (raise `SchemaValidationError` listing missing), check at least one data row (raise `SchemaValidationError`), check `date` parseable via `pd.to_datetime` (raise `SchemaValidationError`), check `capital`/`income`/`book_value` numeric via `pd.to_numeric(..., errors="coerce")` (raise `SchemaValidationError` listing offending columns), compute `min(date)`/`max(date)` and raise `EmptyCapitalDateRangeError(account_name, earliest_date, latest_date)` if `pd.bdate_range(min_date, max_date)` is empty; depends on T001; run T008 tests to verify they pass
- [X] T011 [US1] Implement `app/services/capital_ledger_expander.py` — `CapitalLedgerExpander` class with `expand(df: pd.DataFrame) -> pd.DataFrame` (no `today` parameter): compute `min_date = df["date"].min()`, `max_date = df["date"].max()` directly from the input, call `expand_business_days(df, ["capital", "income", "book_value"], min_date, max_date)` from T004/T005, return the result sorted by `date` with columns `["date", "capital", "income", "book_value"]`; no grouping key, no closure rule; depends on T004/T005; run T009 tests to verify they pass
- [X] T012 [US1] Implement `app/services/capital_ingestion_service.py` — `CapitalIngestionService(repository: CapitalRepository, validator: CapitalLedgerValidator, expander: CapitalLedgerExpander)` with `ingest(account_name: str, file_bytes: bytes) -> CapitalIngestionSummary`: compute SHA-256 hex digest of `file_bytes`; if the account already has a stored capital ledger: on checksum match, do NOT rewrite `capital.xlsx` — call `repository.write_meta()` with `meta.model_copy(update={"ingested_at": datetime.now(UTC)})` only, leaving the XLSX file's bytes and mtime untouched, and return `status="refreshed"` with the existing `row_count`/`from_date`/`to_date` (this is the definitive behavior — no XLSX rewrite ever occurs on a checksum match, since the data is provably unchanged); on checksum mismatch, raise `MergeNotSupportedError(account_name=account_name, message=f"A capital ledger already exists for '{account_name}' with a different checksum. Merging updated capital ledgers is not currently supported.")`; if new: `pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")` (wrap parse failures in `SchemaValidationError`, matching `IngestionService`'s pattern), validate via `CapitalLedgerValidator`, expand via `CapitalLedgerExpander`, build `CapitalMeta` (`row_count`, `from_date`, `to_date`, `ingested_at=datetime.now(UTC)`), `repository.write()`, return `status="created"`; bind and log a structlog event for each branch (`capital_ingest_start`, `capital_ingest_refresh`, `capital_ingest_conflict`, `capital_ingest_complete`), following `ingestion_service.py`'s `logger.bind(...)` pattern (Constitution IV); depends on T002, T006, T010, T011
- [X] T013 [US1] Create `app/api/capital.py` — `APIRouter(prefix="/v1/accounts", tags=["Capital"])`; account-name validation (`^[A-Za-z0-9_-]{1,64}$`, raising `InvalidAccountNameError`) duplicated from `app/api/ladder.py`'s existing pattern (kept as a small, independent duplicate per plan.md — no shared extraction planned for this feature); `_get_capital_repository(settings: Settings = Depends(get_settings)) -> CapitalRepository`; `_get_capital_ingestion_service(...)` wiring `CapitalRepository`, `CapitalLedgerValidator()`, `CapitalLedgerExpander()`; `POST /{account_name}/capital` handler reading `UploadFile` bytes, calling `CapitalIngestionService.ingest()`, returning 201 for `created` / 200 for `refreshed` with `CapitalIngestionSummary` (including `_links.self`/`_links.download` pointing at `/v1/accounts/{account_name}/capital` and `/v1/accounts/{account_name}/capital/download`); depends on T012
- [X] T014 [US1] Register the capital router and a new `EmptyCapitalDateRangeError` handler in `app/main.py`: `app.include_router(capital.router)`; `@app.exception_handler(EmptyCapitalDateRangeError)` returning a 422 `ProblemDetail` via the existing `_problem()` helper, following the pattern of the existing `EmptyDateRangeError` handler; depends on T013, T001
- [X] T015 [US1] Write BDD step implementations in `tests/steps/ingest_capital_steps.py` for the three US1 scenarios in `ingest_capital.feature` — build a sample capital-ledger DataFrame/XLSX-bytes fixture (columns `date`, `capital`, `income`, `book_value`, cumulative values, a gap of a few days between two recorded dates, latest date well before today) either inline or as new fixtures in `tests/conftest.py`; use the existing `app_client` fixture to `POST` and assert response status/JSON shape, and use `pandas.read_excel` on the stored file to assert row counts and forward-filled values and that no row exists after `max(date)`; run `pytest tests/features/ingest_capital.feature tests/unit/test_capital_ledger_validator.py tests/unit/test_capital_ledger_expander.py -m us1` to confirm all green; depends on T014

**Checkpoint**: US1 complete — capital ledger creation fully functional and BDD-tested independently. (The `refreshed`/conflict branches built in T012 have no Gherkin coverage yet — that's added in Phases 5–6, mirroring feature 001's structure.)

---

## Phase 4: User Story 2 — Retrieve a Previously Processed Capital Ledger (Priority: P2)

**Goal**: Return a JSON summary of a stored capital ledger; provide the XLSX binary via a download endpoint.

**Independent Test**: After ingesting, `GET /v1/accounts/test-portfolio/capital` → 200 with summary JSON + `_links`; `GET /v1/accounts/test-portfolio/capital/download` → 200 binary XLSX with correct `Content-Disposition`; both return 404 for an unknown account.

### Tests for User Story 2 ⚠️ Write and verify FAILING before implementing

- [X] T016 [P] [US2] Write Gherkin feature file `tests/features/retrieve_capital.feature` with the four US2 scenarios from spec: "Retrieve summary of an existing capital ledger", "Retrieve a capital ledger summary for an unknown account", "Download XLSX binary for a known account", "Download a capital ledger for an unknown account"; tag each `@us2`

### Implementation for User Story 2

- [X] T017 [US2] Add `GET /{account_name}/capital` and `GET /{account_name}/capital/download` handlers to `app/api/capital.py` — summary handler validates the account name, calls `CapitalRepository.read_meta()` (raising `AccountNotFoundError(account_name=account_name, message=f"No capital ledger found for account '{account_name}'.")` if not found), returns `CapitalSummary` with `_links`; download handler validates the account name, calls `CapitalRepository.read_xlsx()` (same `AccountNotFoundError` override on miss), returns a `FileResponse` with `media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"` and `Content-Disposition: attachment; filename="{account_name}-capital.xlsx"`; depends on T013 (same router file)
- [X] T018 [US2] Write BDD step implementations in `tests/steps/retrieve_capital_steps.py` for `retrieve_capital.feature` — verify JSON summary fields (`row_count`, `from_date`, `to_date`, `ingested_at`), `_links.self`/`_links.download` presence, the 404 problem-detail body for an unknown account on both summary and download, and the download response's content type and `Content-Disposition` header; run `pytest tests/features/retrieve_capital.feature -m us2` to confirm all green; depends on T017

**Checkpoint**: US2 complete — retrieval and download endpoints independently tested.

---

## Phase 5: User Story 3 — Re-submit an Unchanged Capital Ledger (Idempotent) (Priority: P2)

**Goal**: Re-submitting the same file for an existing account returns 200 with `status: "refreshed"`; the stored row count and date range are unchanged.

**Independent Test**: Ingest a file; record the stored ledger's row count, date range, and the XLSX file's mtime/checksum; re-submit the exact same file; verify 200, `status: "refreshed"`, identical row count/date range, an unchanged XLSX mtime (per T012's no-rewrite behavior), and a working `_links.download`.

**Note**: The refreshed (checksum-match) path is already implemented in `CapitalIngestionService.ingest()` (T012). This phase adds Gherkin coverage and step wiring only.

### Tests for User Story 3 ⚠️ Write and verify FAILING before implementing

- [X] T019 [P] [US3] Append the `@us3` scenario "Re-submitting the same file confirms the ledger is current" to `tests/features/ingest_capital.feature` — matches the scenario from spec.md exactly; verifies `status: "refreshed"`, unchanged row count/date range, and `_links.download` presence

### Implementation for User Story 3

- [X] T020 [US3] Add step implementations for the US3 scenario to `tests/steps/ingest_capital_steps.py` — reuse the existing ingestion `when` step; add `then` steps asserting `status == "refreshed"`, that `row_count`/`from_date`/`to_date` match the first ingestion's values, that the stored `capital.xlsx`'s mtime is unchanged (confirms T012's no-rewrite behavior), and that `_links.download` is present; run `pytest tests/features/ingest_capital.feature -m us3` to confirm green; depends on T019, T015

**Checkpoint**: US3 complete — idempotency verified via BDD.

---

## Phase 6: User Story 4 — Submit a Changed Capital Ledger (Merge Not Supported) (Priority: P3)

**Goal**: Submitting a changed file for an account that already has a stored capital ledger returns 409 with a clear error; the existing stored ledger is untouched.

**Independent Test**: Ingest file A; re-submit a modified file B for the same account; verify a 409 problem-detail response naming the merge-not-supported condition, and that `data/test-portfolio/capital.xlsx`/`capital_meta.json` are byte-for-byte unchanged.

**Note**: The 409 conflict path is already implemented in `CapitalIngestionService.ingest()` (T012). This phase adds Gherkin coverage and step wiring only.

### Tests for User Story 4 ⚠️ Write and verify FAILING before implementing

- [X] T021 [P] [US4] Append the `@us4` scenario "Submitting a changed file returns a merge-not-supported error" to `tests/features/ingest_capital.feature` — matches the scenario from spec.md exactly

### Implementation for User Story 4

- [X] T022 [US4] Add step implementations for the US4 scenario to `tests/steps/ingest_capital_steps.py` — submit a modified capital-ledger XLSX (e.g. an added row) for an account that already has a stored ledger; assert the 409 response, that `ProblemDetail.detail` states merging is not supported, and that the stored file's SHA-256 is unchanged before/after; run `pytest tests/features/ingest_capital.feature -m us4` to confirm green; depends on T021, T015

**Checkpoint**: All four user stories complete and independently tested.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Code quality gates, contract sync, edge-case coverage, cross-resource assurance, and end-to-end validation.

- [X] T023 [P] Run `ruff check app/ tests/` and `ruff format app/ tests/` on all new/changed files (`app/exceptions.py`, `app/models/capital.py`, `app/services/business_day_expansion.py`, `app/services/ladder_expander.py`, `app/services/capital_ledger_expander.py`, `app/validators/capital_ledger.py`, `app/repositories/capital_repository.py`, `app/services/capital_ingestion_service.py`, `app/api/capital.py`, `app/main.py`, and all new test files); fix all reported issues including any `D` (pydocstyle) violations (Constitution III); run `mypy --strict app/`; resolve all type errors; confirm zero errors in all three checks
- [X] T024 [P] Verify OpenAPI spec accuracy: start the server, fetch `http://localhost:8000/openapi.json`, compare the generated `capital` paths/schemas against `specs/003-capital-ledger-ingestion/contracts/openapi.yaml`; update the project-root `openapi.yaml` if any discrepancies exist
- [X] T025 Run `quickstart.md` validation end-to-end: start the service, execute each documented `curl` command from `specs/003-capital-ledger-ingestion/quickstart.md` against the real `HL_SIPP_Capital_Ledger.xlsx` reference file, confirm responses match the documented examples, and record/fix any discrepancies in `quickstart.md`
- [X] T026 [P] Add capital-specific edge-case scenarios to the existing shared `tests/features/validation.feature` (reusing the `@validation` tag): non-XLSX upload to the capital endpoint, missing required column, non-numeric value in `capital`/`income`/`book_value`, a recorded date range with zero business days (422 `EmptyCapitalDateRangeError`), and an invalid account name on the capital endpoint; add corresponding steps to `tests/steps/validation_steps.py`; run `pytest tests/features/validation.feature -m validation` to confirm all green
- [X] T027 [P] Add performance smoke tests to `tests/unit/test_performance.py`: using `time.perf_counter`, time a `POST` of a synthetic 5,000-row capital ledger XLSX (generated programmatically) — assert completion within 10s (SC-001); time an idempotent re-submit of the same file — assert within 1s (SC-002); time a `POST` of an intentionally invalid-schema capital file — assert rejection within 1s (SC-003)
- [X] T028 [P] Write Gherkin feature file `tests/features/capital_ladder_independence.feature` covering FR-011's cross-resource independence guarantee, tagged `@validation`: "Ingesting a capital ledger does not affect an existing position ladder for the same account" and "Ingesting a position ladder does not affect an existing capital ledger for the same account"
- [X] T029 Write BDD step implementations in `tests/steps/capital_ladder_independence_steps.py` for `capital_ladder_independence.feature` — for each scenario: ingest one resource type (`POST .../ladder` or `POST .../capital`) for an account, record the other resource's stored file (if any) as absent, then ingest the other resource type for the same account and assert the first resource's stored XLSX bytes/checksum and metadata are completely unaffected (still absent if never created, or byte-for-byte unchanged if pre-existing); additionally re-ingest (checksum-match refresh) one resource and assert the other's stored file/mtime is untouched; run `pytest tests/features/capital_ladder_independence.feature -m validation` to confirm all green; depends on T017 (capital retrieval/read path), T015 (capital ingestion steps established)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks — nothing to wait on
- **Foundational (Phase 2)**: Blocks all user stories. Within Phase 2, T003 → T004 → T005 is a strict chain; T001, T002, T003, T006 have no ordering constraint
- **US1 (Phase 3)**: Depends on Phase 2 — MVP delivery point
- **US2 (Phase 4)**: Depends on T013 (same `app/api/capital.py` file) — may otherwise proceed once Phase 2 is done
- **US3 (Phase 5)**: Depends on US1 (T012 provides the refreshed-path implementation; T015 provides the steps file US3's task appends to)
- **US4 (Phase 6)**: Depends on US1 (T012 provides the 409-path implementation; T015 provides the steps file US4's task appends to)
- **Polish (Phase 7)**: Depends on all four user story phases being complete. T028/T029 additionally depend on both the ladder feature (001, pre-existing) and T017 (capital retrieval)

### Within Phase 2 (Foundational) Dependencies

- T003 → T004 (implementation makes the failing test pass) → T005 (refactor consumes T004)
- T001, T002, T006 have no dependency on T003/T004/T005 or each other

### Within Phase 3 (US1) Dependencies

- T007, T008, T009 → parallel (write tests first; no app code needed)
- T010 → after T008 exists (makes it pass); depends on T001
- T011 → after T009 exists (makes it pass); depends on T004, T005
- T012 → after T010, T011; depends on T002, T006
- T013 → after T012
- T014 → after T013, T001
- T015 → after T014

### Within Phase 4 (US2) Dependencies

- T016 → parallel with any Phase 3 implementation task (Gherkin only, no app code)
- T017 → after T013 (same `capital.py` file)
- T018 → after T017

### Parallel Opportunities

```
Phase 2 parallel group: T001, T002, T003, T006 (T004 must follow T003; T005 must follow T004)

Phase 3 test-writing group: T007, T008, T009 (all parallel)
Phase 3: T010 and T011 can run in parallel with each other (independent modules); both must
follow their respective failing tests (T008, T009)
Phase 3: T012 is NOT parallel — it must follow both T010 and T011

Phase 4: T016 can be written in parallel with any Phase 3 implementation task

Phase 5/6 test-writing: T019 and T021 can both be written in parallel with each other and with
Phase 4 (all append to the same file, but as documentation-only edits with no shared mutable
state — coordinate merge order if working in parallel)

Phase 7 parallel group: T023, T024, T026, T027, T028 (independent; T029 must follow T028)
```

---

## Parallel Example: User Story 1

```bash
# Launch the test-writing tasks for User Story 1 together:
Task: "Write Gherkin feature file tests/features/ingest_capital.feature"
Task: "Write failing unit tests in tests/unit/test_capital_ledger_validator.py"
Task: "Write failing unit tests in tests/unit/test_capital_ledger_expander.py"

# T010 and T011 can then proceed in parallel (different modules) once their respective tests
# exist and fail. T012 (CapitalIngestionService) must NOT start until both are green.
```

---

## Implementation Strategy

### MVP: User Story 1 Only

1. Complete Phase 2: Foundational (CRITICAL — blocks everything; Phase 1 has no tasks)
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**:
   - `pytest tests/unit/test_business_day_expansion.py tests/unit/test_capital_ledger_validator.py tests/unit/test_capital_ledger_expander.py tests/features/ingest_capital.feature -m us1`
   - `POST` the real `HL_SIPP_Capital_Ledger.xlsx` reference file via curl; verify the stored XLSX in `data/` has one row per business day between its earliest and latest recorded date
4. Proceed to Phase 4 (US2) once US1 is green

### Incremental Delivery

1. Phase 2 → Foundation ready
2. Phase 3 (US1) → capital ledger creation works end-to-end → **demo-able MVP**
3. Phase 4 (US2) → GET summary + download work → consumers can retrieve the stored ledger
4. Phase 5 (US3) → idempotency verified with tests
5. Phase 6 (US4) → conflict path covered
6. Phase 7 → code quality gates pass, OpenAPI/quickstart verified, edge cases, cross-resource
   independence, and performance covered

---

## Notes

- `[P]` = parallelisable (different files, no blocking dependency)
- `[Story]` maps task to user story for traceability
- BDD test tasks MUST be written and verified to FAIL before implementation tasks begin
- Use `pytest -m us1` / `-m us2` etc. to run one story's tests in isolation (Gherkin `@usN` tags
  map to pytest marks — filter with `-m`, not `-k`); the `us1`–`us4` markers registered in
  `pyproject.toml` (from feature 001) are reused here — no new marker registration needed
- Commit after each checkpoint (end of each user story phase)
- `data/` and `logs/` remain gitignored — never commit runtime artefacts
- T003/T004/T005 and T006 (repository) are the two pieces of genuine cross-feature code reuse the
  spec explicitly calls for (research.md §1) and independent storage (research.md §5) —
  everything else in Phase 2 is new, capital-only code
- T012's checksum-match ("refreshed") path is defined to never rewrite `capital.xlsx` — only
  `capital_meta.json`'s `ingested_at` changes. This was left as an either/or choice in an earlier
  draft of this task list; it is now a definitive behavior (no ambiguity) so that the stored
  file's mtime is a reliable "content last changed" signal for downstream consumers
- T028/T029 close a coverage gap surfaced by `/speckit-analyze`: FR-011's independence guarantee
  (a capital ledger and a position ladder for the same account never affect one another) had no
  dedicated test before this addition
